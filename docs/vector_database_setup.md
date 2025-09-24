# Vector Database Setup

This document describes the setup and configuration of the vector database using PostgreSQL with pgvector extension.

## Configuration Overview

The system is configured to use PostgreSQL with the pgvector extension for efficient vector storage and similarity search operations.

## Docker Configuration

The `docker-compose.yml` file is configured to use the `pgvector/pgvector:pg16` image which includes the pgvector extension pre-installed.

Key configuration elements:
- Uses the official pgvector image
- Maps port 5432 for database access
- Mounts the initialization script directory
- Includes health checks for database readiness

## Environment Configuration

The `.env` file has been updated to include all necessary PostgreSQL configuration variables:
- `POSTGRES_HOST=postgresql` (matches the service name in docker-compose)
- `POSTGRES_PORT=5432`
- `POSTGRES_USER=postgres`
- `POSTGRES_PASSWORD=postgres`
- `POSTGRES_DB=oasm-assistant`

## Database Schema

The database models have been updated to use the proper vector types:

### Conversation Model
- Uses `Vector(1536)` type for embeddings when pgvector is available
- Falls back to `ARRAY(Float)` when pgvector is not available

### Message Model
- Uses `Vector(1536)` type for embeddings when pgvector is available
- Falls back to `ARRAY(Float)` when pgvector is not available

## Vector Store Implementation

A custom `PgVectorStore` class has been implemented with the following features:
- Automatic enabling of the pgvector extension
- Support for creating HNSW indexes for efficient similarity search
- Methods for storing vectors with metadata
- Similarity search using L2 distance
- Cosine similarity search

## Requirements

The `requirements.txt` file has been updated to include the `pgvector` package which provides Python bindings for the pgvector extension.

## Usage Examples

See `examples/vector_store_example.py` for a complete example of how to use the vector store implementation.

## Testing

See `tests/test_vector_store.py` for unit tests of the vector store functionality.