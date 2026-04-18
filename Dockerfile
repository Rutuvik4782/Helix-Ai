# Use an official Python base image
# We use 3.11 for production stability, as 3.14 is still experimental
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PORT 8000

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
# We explicitly install the compatible starlette version we found earlier
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir "starlette<1.0.0"

# Copy the rest of the application code
COPY . .

# Create necessary directories for data storage
RUN mkdir -p data logs

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
# We use uvicorn directly. For Render, we'll bind to 0.0.0.0 and the $PORT env var
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
