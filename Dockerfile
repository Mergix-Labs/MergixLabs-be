# Taking Python as the base image
FROM python:3.11-slim

# Setting the working directory
WORKDIR /app

# Installing system libraries
RUN apt-get update && apt-get install -y \
    gcc libpq-dev --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copying requirements file first to leverage Docker caching
COPY requirements.txt /app/

# Installing Python dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt --verbose

# Copying the rest of the project files
COPY . /app/

# Copying start.sh to a different directory to avoid volume overwrite
COPY .scripts/start.sh /start.sh

# Give execute permissions to start.sh
RUN chmod +x /start.sh

# Exposing the port for the app
EXPOSE 8000

# Command to run migrations and start the server
CMD ["sh", "/start.sh"]