import os
import uuid
import logging
from pypdf import PdfReader
from pinecone import Pinecone, ServerlessSpec
import google.generativeai as genai
from django.conf import settings
from .models import KnowledgeDocument, DocumentChunk

logger = logging.getLogger("samaira_ai")

# ─── API Setup ──────────────────────────────────────────────────────────────────
def _setup_apis():
    """Ensure Gemini and Pinecone are configured."""
    gemini_key = getattr(settings, "GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
    if gemini_key:
        genai.configure(api_key=gemini_key)
    
    pinecone_key = getattr(settings, "PINECONE_API_KEY", "") or os.getenv("PINECONE_API_KEY", "")
    return gemini_key, pinecone_key


def _get_pinecone_index():
    """Retrieve Pinecone index, creating it if it does not exist."""
    _, pinecone_key = _setup_apis()
    if not pinecone_key:
        raise ValueError("PINECONE_API_KEY is not configured in settings/environment.")

    index_name = getattr(settings, "PINECONE_INDEX_NAME", "") or os.getenv("PINECONE_INDEX_NAME", "samaira-rag")
    pc = Pinecone(api_key=pinecone_key)

    # Automatically create the index if it doesn't exist
    existing_indexes = [idx.name for idx in pc.list_indexes()]
    if index_name not in existing_indexes:
        logger.info(f"Pinecone index '{index_name}' not found. Creating a new serverless index...")
        pc.create_index(
            name=index_name,
            dimension=1536,  # gemini-embedding-001 with output_dimensionality=1536
            metric="cosine",
            spec=ServerlessSpec(
                cloud="aws",
                region="us-east-1"
            )
        )
    return pc.Index(index_name)


# ─── Vertical / Layout-Aware Extraction ─────────────────────────────────────────
def extract_text_by_pages(file_path: str) -> list[dict]:
    """
    Extracts text page-by-page. For PDFs, it uses layout-aware mode
    to preserve vertical columns and tabular structure.
    """
    pages = []
    _, ext = os.path.splitext(file_path.lower())

    if ext == ".pdf":
        reader = PdfReader(file_path)
        for idx, page in enumerate(reader.pages):
            # Attempt layout extraction to read multi-column text vertically/correctly
            try:
                text = page.extract_text(extraction_mode="layout")
            except Exception:
                text = page.extract_text()
            
            if text and text.strip():
                pages.append({
                    "page_number": idx + 1,
                    "text": text.strip()
                })
    else:
        # Fallback to general plain text reading
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            full_text = f.read().strip()
            if full_text:
                pages.append({
                    "page_number": 1,
                    "text": full_text
                })
    return pages


# ─── Hierarchical Chunking ──────────────────────────────────────────────────────
def chunk_text_hierarchically(pages: list[dict], chunk_size_words=250, chunk_overlap_words=50) -> list[dict]:
    """
    Generates smaller child chunks from page-level parent contexts.
    Keeps parent context attached to each child.
    """
    chunks = []
    for page in pages:
        parent_text = page["text"]
        page_number = page["page_number"]
        words = parent_text.split()

        if not words:
            continue

        # If text is shorter than chunk size, it becomes a single chunk
        if len(words) <= chunk_size_words:
            chunks.append({
                "text": parent_text,
                "parent_text": parent_text,
                "page_number": page_number
            })
            continue

        # Slide window across words
        i = 0
        while i < len(words):
            chunk_words = words[i : i + chunk_size_words]
            child_text = " ".join(chunk_words)
            chunks.append({
                "text": child_text,
                "parent_text": parent_text,
                "page_number": page_number
            })
            i += (chunk_size_words - chunk_overlap_words)
            
            # Prevent infinite loop if overlap is larger than chunk size
            if chunk_size_words <= chunk_overlap_words:
                break
                
    return chunks


# ─── Embedding Generation ───────────────────────────────────────────────────────
def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate dense vectors using Gemini's text-embedding-004."""
    _setup_apis()
    embeddings = []
    
    # Gemini API supports embedding lists up to 100 items
    batch_size = 50
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        try:
            response = genai.embed_content(
                model="models/gemini-embedding-001",
                content=batch,
                task_type="retrieval_document",
                output_dimensionality=
1536
            )
            batch_embeddings = response.get("embedding", [])
            embeddings.extend(batch_embeddings)
        except Exception as e:
            logger.error(f"Error calling Gemini Embedding API: {e}")
            raise e
            
    return embeddings


# ─── Ingestion Manager ──────────────────────────────────────────────────────────
def ingest_knowledge_document(doc_id: int) -> bool:
    """
    Complete ingestion pipeline for a single KnowledgeDocument.
    Fetches the file, extracts pages, chunks hierarchically, generates embeddings,
    and upserts vectors to Pinecone.
    """
    try:
        doc = KnowledgeDocument.objects.get(id=doc_id)
    except KnowledgeDocument.DoesNotExist:
        logger.error(f"KnowledgeDocument {doc_id} not found.")
        return False

    try:
        # 1. Clean existing records in database and Pinecone for idempotency
        delete_document_from_pinecone(doc_id)
        doc.chunks.all().delete()

        file_path = doc.file.path
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Uploaded file not found on disk at: {file_path}")

        # 2. Extract layout-aware page texts
        pages = extract_text_by_pages(file_path)
        if not pages:
            raise ValueError("No text could be extracted from this document.")

        # 3. Create hierarchical child chunks
        chunks = chunk_text_hierarchically(pages)
        if not chunks:
            raise ValueError("Hierarchical chunking returned no content.")

        # 4. Generate embeddings for child texts
        child_texts = [c["text"] for c in chunks]
        embeddings = generate_embeddings(child_texts)

        # 5. Prepare vectors for Pinecone and database records
        index = _get_pinecone_index()
        vectors_to_upsert = []
        chunks_to_create = []

        for idx, chunk in enumerate(chunks):
            embedding = embeddings[idx]
            # Generate a unique chunk ID
            chunk_uuid = str(uuid.uuid4())
            vector_id = f"doc_{doc_id}_chunk_{chunk_uuid}"

            vectors_to_upsert.append({
                "id": vector_id,
                "values": embedding,
                "metadata": {
                    "document_id": doc_id,
                    "text": chunk["text"],
                    "parent_text": chunk["parent_text"],
                    "page_number": chunk["page_number"]
                }
            })

            chunks_to_create.append(DocumentChunk(
                document=doc,
                chunk_id=vector_id,
                text=chunk["text"],
                parent_text=chunk["parent_text"],
                page_number=chunk["page_number"]
            ))

        # 6. Bulk upload vectors to Pinecone
        batch_size = 100
        for i in range(0, len(vectors_to_upsert), batch_size):
            batch = vectors_to_upsert[i : i + batch_size]
            index.upsert(vectors=batch)

        # 7. Save chunks to local database
        DocumentChunk.objects.bulk_create(chunks_to_create)

        # 8. Mark document as successfully processed
        doc.is_processed = True
        doc.error_log = None
        doc.save(update_fields=["is_processed", "error_log"])
        logger.info(f"Successfully processed KnowledgeDocument: {doc.title} (ID: {doc_id})")
        return True

    except Exception as e:
        error_msg = f"Ingestion failed: {str(e)}"
        logger.exception(error_msg)
        doc.is_processed = False
        doc.error_log = error_msg
        doc.save(update_fields=["is_processed", "error_log"])
        return False


def delete_document_from_pinecone(doc_id: int):
    """Delete all chunks for a document from Pinecone."""
    try:
        index = _get_pinecone_index()
        # Delete using metadata filter
        index.delete(filter={"document_id": {"$eq": doc_id}})
        logger.info(f"Cleaned Pinecone vectors for Document ID: {doc_id}")
    except Exception as e:
        # If the index is empty or API key is wrong, log warning but don't crash
        logger.warning(f"Could not clean Pinecone vectors for doc {doc_id}: {e}")
