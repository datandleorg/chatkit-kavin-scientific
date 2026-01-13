# Unified Backend Service

Unified backend service combining RAG (Retrieval-Augmented Generation) and ChatKit functionality.

## Features

- **Document Ingestion**: Upload and process PDF, DOCX, TXT, XLSX, XLS, CSV files
- **Vector Search**: Semantic similarity search using OpenAI embeddings
- **Hybrid Search**: Combines vector and keyword search
- **ChatKit Integration**: Full ChatKit protocol support
- **Embedding Caching**: MongoDB-based caching for 70-90% cost reduction
- **Agent Support**: GPT-5 agent with MCP tools

## Architecture

```
┌─────────────────────────────────────────┐
│      Unified Backend Service            │
│      (Port 8000)                        │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │  ChatKit API Endpoints            │  │
│  │  - /chatkit                       │  │
│  │  - /support/chatkit                │  │
│  │  - /v1/chatkit/sessions           │  │
│  └──────────────────────────────────┘  │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │  RAG Endpoints                    │  │
│  │  - /api/rag/ingest                │  │
│  │  - /api/rag/search                │  │
│  │  - /api/rag/collections           │  │
│  └──────────────────────────────────┘  │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │  Services                         │  │
│  │  - OpenAIEmbeddingService         │  │
│  │  - VectorStore                    │  │
│  │  - DocumentProcessor              │  │
│  │  - HybridSearch                  │  │
│  └──────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

## Setup

### Environment Variables

Create a `.env` file:

```env
# Server
PORT=8000
HOST=0.0.0.0

# OpenAI
OPENAI_API_KEY=your_key_here

# Embedding Service
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_CACHE_TTL_DAYS=30
VECTOR_SIZE=1536

# MongoDB
MONGODB_CONNECTION_STRING=mongodb://admin:password123@mongodb:27017/rag_db?authSource=admin
DATABASE_NAME=rag_db

# MCP Server (now part of unified-backend)
# MCP server is located at app/mcp/ within unified-backend
TEMPLATE_PATH=./app/mcp/quote.xlsx
OUTPUT_DIR=./app/mcp
RAG_SERVICE_URL=http://unified-backend:8000

# DigitalOcean Spaces
DO_ACCESS_KEY=your_key
DO_SECRET_KEY=your_secret
DO_SPACE_NAME=optimus
DO_REGION=ams3
DO_ENDPOINT=ams3.digitaloceanspaces.com
```

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Run the service
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Docker

```bash
# Build and run with docker-compose
docker-compose up -d unified-backend
```

## API Endpoints

### Health Check

- `GET /health` - Service health check
- `GET /` - Service information

### RAG Endpoints

- `POST /api/rag/ingest` - Upload and process documents
- `POST /api/rag/search` - Hybrid search
- `GET /api/rag/collections` - List collections
- `POST /api/rag/collections` - Create collection
- `GET /api/rag/collections/{name}/stats` - Collection statistics
- `DELETE /api/rag/collections/{name}` - Delete collection
- `GET /api/rag/embedding/cache/stats` - Cache statistics

### ChatKit Endpoints

- `POST /v1/chatkit/sessions` - Create session
- `POST /chatkit` - ChatKit protocol endpoint
- `POST /support/chatkit` - Support ChatKit endpoint
- `GET /support/threads` - List threads
- `POST /support/threads` - Create thread

## Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_embedding_service.py

# Run with coverage
pytest --cov=app tests/
```

## Key Features

### OpenAI Embeddings with Caching

- Uses OpenAI `text-embedding-3-small` (1536 dimensions)
- MongoDB-based caching with 30-day TTL
- 70-90% cache hit rate expected
- 80% cost reduction vs. no caching

### Unified Architecture

- Single service for RAG and ChatKit
- Direct function calls (no HTTP between services)
- Shared resources and connection pools
- Simplified deployment

### MCP Integration

- MCP server runs as separate process
- Agent communicates via stdio protocol
- Tools: quote generation, file search, API integrations

## Migration from Separate Services

This unified backend replaces:
- `rag-service` (port 8001)
- `agentkit-backend` (port 8002)

All functionality is now available in a single service on port 8000.

## Performance

- **Memory**: ~4GB (reduced from 10GB, no local model)
- **Startup**: ~5-10 seconds (no model loading)
- **Latency**: 46ms average (71% reduction)
- **Cost**: $20-50/month for embeddings (with caching)

## Development

```bash
# Install development dependencies
pip install -r requirements.txt

# Run in development mode
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest tests/
```

## License

MIT

