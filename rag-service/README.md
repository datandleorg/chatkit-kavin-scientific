# RAG Service - Document Ingestion and Hybrid Search

A FastAPI-based service for document ingestion and hybrid search using Docling for PDF processing and MongoDB for vector storage and text search.

## Features

- **Document Processing**: Extract text from PDF, DOCX, TXT, Markdown (MD), HTML, Excel, and CSV files using Docling, openpyxl, and pandas
- **Multimodal RAG**: Process markdown files with embedded images (base64 data URIs) using vision-language models (CLIP)
- **Vector Search**: Semantic similarity search using sentence transformers
- **Text Search**: Full-text search using MongoDB's text search capabilities
- **Hybrid Search**: Combines vector and text search with configurable weights
- **Multimodal Fusion**: Fuses text and image embeddings for comprehensive document understanding
- **RESTful API**: Clean FastAPI endpoints for all operations
- **Admin Endpoints:** Reset database and manage collections
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

### Health and Status

- **GET** `/`  – Simple root health check
- **GET** `/health` – Detailed health check (Mongo, service status)

### Document Ingestion

- **POST** `/ingest`
  - Upload and process documents (PDF, DOCX, TXT, MD, XLSX, XLS, CSV, HTML). Markdown files with embedded base64 images are supported.
  - Parameters:
    - `file` (required): Document file (multipart/form-data)
    - `collection_name`: MongoDB collection name (default: "documents")
    - `chunk_size`: Text chunk size (default: 1000)
    - `chunk_overlap`: Overlap between chunks (default: 200)

**Examples:**

Ingest a markdown file (basic):
```bash
curl -X POST "http://localhost:8000/ingest" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@document.md" \
  -F "collection_name=my_docs"
```

**Response:**
```json
{
  "document_id": "abc123-def456-ghi789",
  "filename": "docs_with_images.md",
  "chunks_count": 12,
  "collection_name": "my_docs",
  "status": "success",
  "metadata": { /* ... */ }
}
```

**Metadata Information:**
- **PDF:** `pages_count`, `total_elements`, `document_info`, `extraction_method`
- **Markdown:** `image_count`, `has_images`, `images[]`, `char_count`, `line_count`, `extraction_method`
- **Excel:** `total_sheets`, `sheet_names`, `total_rows`, `total_cells`, `sheets_data`
- **CSV:** `total_rows`, `total_columns`, `column_names`, `non_empty_cells`
- **DOCX:** `paragraphs_count`, `tables_count`, `extraction_method`
- **TXT/HTML/Other:** `char_count`, `line_count`, `extraction_method`

### Search Operations

#### **POST** `/search` – Hybrid Search
- Combines vector similarity and keyword matching
- **Multimodal support**: Uses text and image (vision) embeddings for markdown with embedded images (if CLIP is available)
- Parameters:
  - JSON body (`SearchRequest`): `{ "query": string, "filters": {...} }`
  - `collection_name`: Query param
  - `limit`: Query param (default: 10)
  - `score_threshold`: Query param (float: 0.0–1.0)
  - `document_id`: Query param (optional, filter to a specific document)
  - `result_type`: Query param (text, image, or omitted for both)
  - `text_only`: Query param (if true, return concatenated results text)
  - `llm_format`: Query param (if true, use LLM to summarize/format)
  - `llm_provider`: Query param (default: "openai")
- **Note**: "filters" in body allows advanced filtering on metadata, e.g. `{ "filename": "docs_with_images.md" }`

#### **POST** `/search/vector` – Vector-Only Search
- Semantic vector similarity (same params as above, but no keyword/LLM integration)

#### **POST** `/search/keyword` – Keyword-Only Search
- Full-text search using MongoDB's text indexes (same params, but ignores vector search)

#### **POST** `/documents/{document_id}/search`
- Search within a specific document (same options as `/search` but requires the document ID in the route and in filters)

#### **GET** `/documents/{document_id}`
- Returns document metadata and all text chunks by document ID

#### **Output Schema for Search Results**
- Search results include `text`, `chunk_index`, `score`, `vision_score` (if multimodal), images metadata (base64, alt, etc.), and detailed chunk/file metadata for context/citation.
- If `text_only` or `llm_format` is set, response will have a `text` field aggregating content or formatted output.

#### Example Hybrid Search with Filters
```bash
curl -X POST "http://localhost:8000/search?collection_name=my_docs&limit=5" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "system architecture diagram",
    "filters": {"filename": "docs_with_images.md"}
  }'
```

### Collection Management

- **POST** `/collections` – Create collection
- **GET** `/collections` – List collections
- **GET** `/collections/{name}/stats` – Stats for a collection
- **DELETE** `/collections/{name}` – Delete collection

**Example:**
```bash
curl -X POST "http://localhost:8000/collections?collection_name=my_new_collection"
```

### Admin Operations

- **DELETE** `/admin/reset` – Clears all data (removes all collections)
- **DELETE** `/admin/collections/{collection_name}` – Deletes a specific collection

### Health Endpoints

- **GET** `/`              – Root health check
- **GET** `/health`        – Detailed database/service health

---

## Configuration

### Environment Variables

- `MONGODB_CONNECTION_STRING`: MongoDB connection string (required)
- `DATABASE_NAME`: MongoDB database name (default: `rag_db`)
- `VECTOR_SIZE`: Embedding vector size (default: 384)

Environment variables are loaded from `config.env`, environment, or Docker Compose. You can override these for dev or production deployments.

### MongoDB Connection
- Host: localhost (or container name if using Docker Compose)
- Port: 27017
- Database: rag_db (or as configured)
- Authentication: admin/password123 (Docker setup example)

## Document Processing

### Supported Formats

- **PDF**: Docling with fallback to PyPDF
- **DOCX**: python-docx
- **TXT**: Direct text read
- **HTML**: Basic text read
- **Markdown (MD)**: markdown-it-py parsing, base64 image extraction + vision embeddings with CLIP if available
- **XLSX/XLS**: openpyxl, multi-sheet, formulas
- **CSV**: pandas, encoding auto-detect, delimiter handling

### Text Chunking
- Chunked by sentence/paragraph boundaries when possible, with overlap
- Supports LangChain chunker if present, fallback to internal chunker

### Embeddings
- **Text:** all-MiniLM-L6-v2 (384d)
- **Vision:** clip-ViT-B-32 (512d). Used for markdown with base64 images when available.

---

## Multimodal RAG (Text + Image)

- Markdown with base64 images: Extracts both text and images, creates both text and vision embeddings.
- Multimodal search: When enabled, queries match on both visual/semantic content.
- Images metadata (alt text, format, position, base64) included in returned results.

---

## Development & Project Structure

```
rag-service/
├── main.py                 # FastAPI application
├── requirements.txt        # Python dependencies
├── Dockerfile              # Container configuration
├── docker-compose.yml      # Multi-service setup
├── mongo-init.js           # MongoDB initialization
├── models/
│   └── schemas.py          # Pydantic models
└── services/
    ├── document_processor.py   # Docling & file parsing
    ├── vector_store.py         # MongoDB, embedding logic
    └── hybrid_search.py        # Hybrid search algorithm
```

---

## Running Tests

```bash
pytest tests/
```

## Code Quality

```bash
# Format code
black .
# Lint code
flake8 .
# Type checking
mypy .
```

## Troubleshooting

### Common Issues
- MongoDB Connection Failed: Check DB network/credentials, ensure DB is running
- Document Processing Errors: Check dependencies, file type support, Docling install
- Search Returns No Results: Check documents are ingested, verify collection name/query, ensure proper filters

### Logs
- View service logs:
  ```bash
  docker-compose logs -f rag_service
  ```
- View MongoDB logs:
  ```bash
  docker-compose logs -f mongodb
  ```

---

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
