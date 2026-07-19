from celery import shared_task
from .ingestion import ingest_knowledge_document, delete_document_from_pinecone

@shared_task
def ingest_document_task(doc_id):
    """Asynchronously process document text extraction, chunking, embedding, and Pinecone upsert."""
    ingest_knowledge_document(doc_id)


@shared_task
def delete_document_task(doc_id):
    """Asynchronously clean up vectors in Pinecone for deleted documents."""
    delete_document_from_pinecone(doc_id)
