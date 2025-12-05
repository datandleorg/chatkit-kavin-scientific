## RAG Service – Technical Documentation

### Overview
The RAG Service is a FastAPI application that ingests documents and performs hybrid search over both text and images. It integrates:
- Docling-based parsing with robust fallbacks (pypdf, python-docx, openpyxl, pandas)
- MongoDB for storage, text search, and metadata
- Semantic vector embeddings (text + optional vision) with a vector store abstraction
- A hybrid search strategy that fuses vector similarity, keyword search, and image (vision) search
- Optional LLM post-formatting of search results

Primary use case: grounded answers and citations for furniture/design documentation (PDF, DOCX, TXT, MD, HTML, XLS/XLSX, CSV).

### Architecture
```
┌──────────────┐      ┌────────────────────┐      ┌──────────────────────┐
│  FastAPI     │      │  Services          │      │   MongoDB            │
│  (main.py)   │──►──►│  - DocumentProcessor│───►──│  Collections + Indexes│
│  Endpoints   │◄──◄──│  - VectorStore      │◄───►│  Text + Vectors       │
│              │      │  - HybridSearch     │      │                      │
│              │      │  - LLMService       │      │                      │
└──────────────┘      └────────────────────┘      └──────────────────────┘
```

### Key Components
- main.py
  - Initializes `DocumentProcessor`, `VectorStore`, `HybridSearch`, and `LLMService`
  - Defines public REST endpoints for health, ingestion, search, collections, and admin
  - CORS enabled for all origins (dev-friendly)

- services/document_processor.py
  - Supported formats: .pdf, .docx, .txt, .md, .html, .xlsx, .xls, .csv
  - PDF: docling-parse with fallback to pypdf
  - Markdown: markdown-it parsing, extraction of embedded base64 images, placeholders in text
  - Excel: openpyxl with merged-cell handling; computes totals and per-sheet stats
  - CSV: pandas with encoding fallbacks; computes column metadata
  - TXT/HTML/Other: direct read fallback where applicable
  - Chunking:
    - Prefers LangChain `RecursiveCharacterTextSplitter`; falls back to an internal splitter
    - Adds per-chunk metadata: page estimation, char ranges, file metadata
    - Writes chunk debug files into `chunks_debug/` for verification

- services/hybrid_search.py
  - Orchestrates parallel searches: vector, keyword, and vision (image)
  - Combines and normalizes results, applies score threshold, and limits output
  - Formats output into uniform structures (text vs image) with citations
  - Supports vector-only and keyword-only variants

- services/vector_store.py
  - Abstracts MongoDB storage, retrieval, indexing, and search across text, vectors, and images
  - Provides methods used by `HybridSearch`:
    - `search_similar` (vectors)
    - `search_text` (keywords)
    - `search_images` (vision)
  - Handles document persistence and collection management

- services/llm_service.py
  - Optional post-processing of search results into summaries/LLM-friendly formats

- models/schemas.py
  - `DocumentResponse`, `SearchRequest`, `SearchResponse`, and `SearchResult` schemas

### Data Flow
1) Ingestion (`POST /ingest`)
   - FastAPI receives the file, writes it to `uploads/`
   - `DocumentProcessor` parses content and constructs chunks with metadata
   - `VectorStore` stores chunks + embeddings + metadata in MongoDB (and vision data if applicable)
   - Returns `document_id`, `chunks_count`, `metadata`

2) Search (`POST /search`)
   - Validates query params (limit, score_threshold, result_type)
   - If `document_id` is provided, restricts search scope
   - `HybridSearch` runs vector, keyword, and vision searches in parallel via `VectorStore`
   - Fuses results and applies thresholding and limit
   - Optionally formats results with `LLMService` when `llm_format=true` or returns concatenated `text_only`
   - Returns uniform results with citations and metadata

### Storage and Indexing (MongoDB)
- Collections:
  - Default: `documents` (configurable via query params)
  - Stores chunked text with associated metadata and embeddings
- Indexing:
  - Text indexes for keyword queries
  - Vector representation for semantic similarity (implementation in `VectorStore`)
- Metadata:
  - filename, file_type, ingestion date, page/chunk indices, image info (for markdown), and other extraction details

### API Endpoints
- Health
  - GET `/` – Root health
  - GET `/health` – Detailed health, includes Mongo readiness

- Ingestion
  - POST `/ingest` (multipart/form-data)
    - file: required
    - query params: `collection_name` (default: documents), `chunk_size` (1000), `chunk_overlap` (200)
    - response: `DocumentResponse` with `document_id`, `chunks_count`, `metadata`

- Search (Hybrid)
  - POST `/search` (JSON body `SearchRequest`)
    - query params: `collection_name`, `limit=10`, `score_threshold=0.0..1.0`, `document_id?`, `result_type?` in {text,image}, `text_only?`, `llm_format?`, `llm_provider=openai`
    - returns `SearchResponse` or `{ text, total_results, ... }` for `text_only`

- Search (Vector-only)
  - POST `/search/vector`
    - `collection_name`, `limit`

- Search (Keyword-only)
  - POST `/search/keyword`
    - `collection_name`, `limit`

- Document by ID
  - GET `/documents/{document_id}` – returns stored metadata and chunks
  - POST `/documents/{document_id}/search` – like hybrid search, scoped to one document

- Collections
  - POST `/collections` – create
  - GET `/collections` – list
  - GET `/collections/{collection_name}/stats` – statistics
  - DELETE `/collections/{collection_name}` – delete

- Admin
  - DELETE `/admin/reset` – remove all collections
  - DELETE `/admin/collections/{collection_name}` – delete specific collection

### Schemas (selected)
- SearchRequest
```json
{
  "query": "string",
  "filters": { "filename": "optional or custom keys" }
}
```

- SearchResponse (hybrid/vector/keyword)
```json
{
  "query": "string",
  "results": [
    {
      "type": "text" | "image",
      "document_id": "string",
      "chunk_index": 0,
      "text": "...",
      "score": 0.87,
      "vector_score": 0.82,
      "keyword_score": 0.76,
      "vision_score": 0.66,
      "citation": {
        "document_id": "...",
        "filename": "...",
        "chunk_index": 3,
        "image_index": 1
      },
      "image_data": { "alt_text": "...", "base64_data": "..." }
    }
  ],
  "total_results": 10,
  "collection_name": "documents",
  "search_type": "hybrid",
  "formatting_applied": false
}
```

### Environment and Configuration
- Environment variables (via `config.env`/Docker):
  - `MONGODB_CONNECTION_STRING` – required
  - `DATABASE_NAME` – default `rag_db`
  - `VECTOR_SIZE` – default `384` (text embeddings)
- Uploads directory: `uploads/` (mounted in Docker)
- Chunking defaults: `chunk_size=1000`, `chunk_overlap=200`

### Deployment
- Docker Compose (recommended)
  - MongoDB exposed on 27017
  - RAG service exposed on 8000 and started with:
    ```
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
    ```
  - See `docker-compose.yml` for volumes and env wiring

- Local (manual)
  - `pip install -r requirements.txt`
  - Start MongoDB (e.g., `docker run -p 27017:27017 mongo:7.0`)
  - `uvicorn main:app --host 0.0.0.0 --port 8001 --reload` (or 8000 if desired)

### Operational Notes
- Logs
  - Application logs via Uvicorn/FastAPI
  - Chunk debug artifacts in `chunks_debug/` for verification
- Error handling
  - Robust try/except around processing and search; HTTP errors with clear messages
  - Health endpoint returns 503 when dependencies are down
- Security
  - CORS is permissive by default for development; restrict in production
  - Validate `collection_name` and parameters in endpoints

### Extensibility
- Embeddings/Vector Store
  - Swap out embedding models or backends in `VectorStore`
- Additional Parsers
  - Extend `DocumentProcessor` to support new formats
- Ranking/Fusion
  - Adjust combination logic in `HybridSearch._combine_search_results`
- LLM Post-processing
  - Enhance `LLMService` to support providers or richer summarization

### Example Requests
- Ingest (Markdown):
```bash
curl -X POST "http://localhost:8000/ingest" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@document.md" \
  -F "collection_name=my_docs"
```

- Hybrid Search:
```bash
curl -X POST "http://localhost:8000/search?collection_name=my_docs&limit=5&score_threshold=0.2" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "system architecture diagram",
    "filters": {"filename": "docs_with_images.md"}
  }'
```


