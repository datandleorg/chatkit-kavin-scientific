# RAG Service - Document Ingestion and Hybrid Search

A FastAPI-based service for document ingestion and hybrid search using Docling for PDF processing and MongoDB for vector storage and text search.

## Features

- **Document Processing**: Extract text from PDF, DOCX, and TXT files using Docling
- **Vector Search**: Semantic similarity search using sentence transformers
- **Text Search**: Full-text search using MongoDB's text search capabilities
- **Hybrid Search**: Combines vector and text search with configurable weights
- **RESTful API**: Clean FastAPI endpoints for all operations
- **Docker Support**: Complete containerization with Docker Compose
- **Scalable**: Built with async/await for high performance

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   FastAPI App   │────│  Document        │────│   MongoDB       │
│                 │    │  Processor       │    │   (Vector +     │
│  - /ingest      │    │  (Docling)       │    │    Text Search) │
│  - /search      │    │                  │    │                 │
│  - /health      │    └──────────────────┘    └─────────────────┘
└─────────────────┘
```

## Quick Start

### Using Docker Compose (Recommended)

1. **Clone and navigate to the service directory:**
   ```bash
   cd rag-service
   ```

2. **Start the services:**
   ```bash
   docker-compose up -d
   ```

3. **Check service health:**
   ```bash
   curl http://localhost:8000/health
   ```

4. **Access the API documentation:**
   - Open http://localhost:8000/docs in your browser

### Manual Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Start MongoDB:**
   ```bash
   docker run -d -p 27017:27017 --name mongodb mongo:7.0
   ```

3. **Run the service:**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

## API Endpoints

### Document Ingestion

**POST** `/ingest`
- Upload and process documents (PDF, DOCX, TXT)
- Parameters:
  - `file`: Document file
  - `collection_name`: MongoDB collection name (default: "documents")
  - `chunk_size`: Text chunk size (default: 1000)
  - `chunk_overlap`: Overlap between chunks (default: 200)

**Example:**
```bash
curl -X POST "http://localhost:8000/ingest" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@document.pdf" \
  -F "collection_name=my_docs"
```

### Search Operations

**POST** `/search` - Hybrid Search
- Combines vector similarity and keyword matching
- Parameters:
  - `query`: Search query
  - `collection_name`: Collection to search
  - `limit`: Maximum results (default: 10)
  - `hybrid_weight`: Vector search weight (0.0-1.0, default: 0.7)

**POST** `/search/vector` - Vector-Only Search
- Semantic similarity search using embeddings

**POST** `/search/keyword` - Keyword-Only Search
- Full-text search using MongoDB text search

**Example:**
```bash
curl -X POST "http://localhost:8000/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "machine learning algorithms",
    "filters": {"filename": "research_paper.pdf"}
  }'
```

### Collection Management

**GET** `/collections` - List all collections
**GET** `/collections/{name}/stats` - Get collection statistics
**DELETE** `/collections/{name}` - Delete a collection

### Document Management

**GET** `/documents/{document_id}` - Get document by ID
**GET** `/health` - Service health check

## Configuration

### Environment Variables

- `MONGODB_CONNECTION_STRING`: MongoDB connection string
- `DATABASE_NAME`: MongoDB database name
- `VECTOR_SIZE`: Embedding vector size (default: 384)

### MongoDB Connection

The service connects to MongoDB using the following default configuration:
- Host: localhost
- Port: 27017
- Database: rag_db
- Authentication: admin/password123 (Docker setup)

## Document Processing

### Supported Formats

- **PDF**: Processed using Docling for high-quality text extraction
- **DOCX**: Processed using python-docx
- **TXT**: Direct text reading

### Text Chunking

Documents are automatically chunked into smaller pieces for better search performance:
- Default chunk size: 1000 characters
- Default overlap: 200 characters
- Chunks are created at sentence boundaries when possible

### Embeddings

- Model: `all-MiniLM-L6-v2` (384 dimensions)
- Generated for each text chunk
- Stored in MongoDB for vector similarity search

## Search Types

### 1. Vector Search
- Uses semantic similarity
- Good for conceptual queries
- Handles synonyms and related concepts

### 2. Text Search
- Uses MongoDB's full-text search
- Good for exact keyword matching
- Fast and efficient for specific terms

### 3. Hybrid Search
- Combines both approaches
- Configurable weights for each method
- Provides comprehensive results

## Development

### Project Structure

```
rag-service/
├── main.py                 # FastAPI application
├── requirements.txt        # Python dependencies
├── Dockerfile             # Container configuration
├── docker-compose.yml     # Multi-service setup
├── mongo-init.js          # MongoDB initialization
├── models/
│   └── schemas.py         # Pydantic models
└── services/
    ├── document_processor.py  # Docling integration
    ├── vector_store.py        # MongoDB operations
    └── hybrid_search.py       # Search logic
```

### Running Tests

```bash
pytest tests/
```

### Code Quality

```bash
# Format code
black .

# Lint code
flake8 .

# Type checking
mypy .
```

## Performance Considerations

### MongoDB Indexes

The service creates several indexes for optimal performance:
- Text index on `text` and `filename` fields
- Compound index on `document_id` and `chunk_index`
- Index on `filename` and `created_at` for filtering

### Vector Search Optimization

- Embeddings are pre-computed and stored
- Cosine similarity calculation optimized for MongoDB
- Configurable score thresholds

### Scaling

- Async/await throughout for high concurrency
- MongoDB sharding support
- Horizontal scaling with multiple service instances

## Troubleshooting

### Common Issues

1. **MongoDB Connection Failed**
   - Check if MongoDB is running
   - Verify connection string
   - Check network connectivity

2. **Document Processing Errors**
   - Ensure file format is supported
   - Check file permissions
   - Verify Docling installation

3. **Search Returns No Results**
   - Check if documents are ingested
   - Verify collection name
   - Check search query format

### Logs

View service logs:
```bash
docker-compose logs -f rag_service
```

View MongoDB logs:
```bash
docker-compose logs -f mongodb
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
- Create an issue in the repository
- Check the API documentation at `/docs`
- Review the logs for error details
