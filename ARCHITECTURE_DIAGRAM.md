# Architecture Diagram - Revised Plan

## Current Architecture

```
┌─────────────────┐
│   Frontend      │
│  (Port 8081)    │
└────────┬────────┘
         │ HTTP
         ▼
┌─────────────────┐      HTTP      ┌─────────────────┐
│ agentkit-backend│ ──────────────►│   rag-service   │
│  (Port 8002)    │                │  (Port 8001)    │
│                 │                │                 │
│ - ChatKit API   │                │ - Document      │
│ - Agent         │                │   Ingestion     │
│ - MCP (stdio)   │                │ - Search        │
│                 │                │ - Sentence      │
│                 │                │   Transformers   │
└─────────────────┘                └─────────────────┘
         │ stdio                           │
         ▼                                 ▼
┌─────────────────┐                ┌─────────────────┐
│   MCP Server    │                │    MongoDB      │
│  (Subprocess)   │                │   (Port 27017)  │
└─────────────────┘                └─────────────────┘
```

## Proposed Architecture

```
┌─────────────────┐
│   Frontend      │
│  (Port 8081)    │
└────────┬────────┘
         │ HTTP
         ▼
┌─────────────────────────────────────────┐
│      Unified Backend Service            │
│      (Port 8000)                        │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │  FastAPI Application              │  │
│  │                                    │  │
│  │  Routes:                           │  │
│  │  - /chatkit                        │  │
│  │  - /support/chatkit                │  │
│  │  - /v1/chatkit/sessions           │  │
│  │  - /ingest                         │  │
│  │  - /search                         │  │
│  │  - /collections                    │  │
│  │  - /health                         │  │
│  └──────────────────────────────────┘  │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │  Services (Internal)              │  │
│  │                                    │  │
│  │  - VectorStore                    │  │
│  │    └─► OpenAIEmbeddingService     │  │
│  │        └─► Cache (MongoDB)        │  │
│  │  - DocumentProcessor              │  │
│  │  - HybridSearch                   │  │
│  │  - Agent (with MCP stdio)         │  │
│  └──────────────────────────────────┘  │
└─────────────────────────────────────────┘
         │                                    │
         │ stdio                              │ MongoDB
         ▼                                    ▼
┌─────────────────┐                    ┌─────────────────┐
│   MCP Server    │                    │    MongoDB      │
│  (Separate      │                    │   (Port 27017)  │
│   Process)      │                    │                 │
│                 │                    │  - Documents    │
│  Tools:         │                    │  - Embeddings   │
│  - Quote Gen    │                    │  - Cache        │
│  - File Search  │                    └─────────────────┘
│  - API Tools    │
└─────────────────┘
```

## Data Flow: Document Ingestion

```
1. User uploads document
   │
   ▼
2. Unified Backend receives file
   │
   ▼
3. DocumentProcessor processes (Docling)
   │
   ▼
4. Text chunks created
   │
   ▼
5. OpenAIEmbeddingService.embed_batch()
   │
   ├─► Check cache (MongoDB)
   │   ├─► Cache HIT: Use cached embedding
   │   └─► Cache MISS: Call OpenAI API
   │       └─► Save to cache
   │
   ▼
6. VectorStore stores chunks + embeddings
   │
   ▼
7. MongoDB: Documents collection
```

## Data Flow: Search Query

```
1. User sends query
   │
   ▼
2. Unified Backend receives query
   │
   ▼
3. OpenAIEmbeddingService.embed_text(query)
   │
   ├─► Check cache
   │   ├─► Cache HIT: Use cached
   │   └─► Cache MISS: Call OpenAI API
   │
   ▼
4. HybridSearch.search()
   │
   ├─► Vector search (MongoDB aggregation)
   └─► Keyword search (MongoDB text index)
   │
   ▼
5. Combine results
   │
   ▼
6. Return to user
```

## Data Flow: Agent with MCP

```
1. User sends message via ChatKit
   │
   ▼
2. Unified Backend ChatKit endpoint
   │
   ▼
3. Agent processes message
   │
   ▼
4. Agent needs tool (e.g., file_search)
   │
   ▼
5. Agent calls MCP via stdio
   │
   ▼
6. MCP Server receives tool call
   │
   ├─► file_search: Calls unified backend /search (HTTP)
   ├─► generate_quote: Generates Excel file
   └─► API tools: Calls external APIs
   │
   ▼
7. MCP returns result to agent
   │
   ▼
8. Agent continues processing
   │
   ▼
9. Response streamed to frontend
```

## Component Details

### Unified Backend Service

**Responsibilities**:
- ChatKit protocol handling
- Document ingestion
- Vector search
- Agent orchestration
- MCP stdio subprocess management

**Key Services**:
- `OpenAIEmbeddingService`: Embeddings with caching
- `VectorStore`: MongoDB vector operations
- `DocumentProcessor`: Document parsing
- `HybridSearch`: Search logic
- `Agent`: LLM agent with tools

### MCP Server

**Responsibilities**:
- Tool implementations
- Quote generation
- External API integrations
- RAG service wrapper

**Communication**:
- **Input**: stdio from agent
- **Output**: stdio to agent
- **Internal**: HTTP calls to unified backend

### MongoDB

**Collections**:
- `documents`: Document chunks with embeddings
- `embedding_cache`: Cached embeddings (TTL: 30 days)
- Other collections as needed

## Benefits Visualization

### Before (Current)
```
Memory Usage:
- agentkit-backend: ~500MB
- rag-service: ~1.5GB (sentence-transformers model)
- MCP: ~200MB
Total: ~2.2GB

Latency:
- Frontend → agentkit-backend: 10ms
- agentkit-backend → rag-service: 50ms (HTTP)
- rag-service → embeddings: 100ms (local model)
Total: ~160ms
```

### After (Proposed)
```
Memory Usage:
- unified-backend: ~800MB (no local model)
- MCP: ~200MB
Total: ~1GB (54% reduction)

Latency:
- Frontend → unified-backend: 10ms
- unified-backend → embeddings: 20ms (cached) / 150ms (API)
- Cache hit rate: 80%
- Average: 10 + (0.8 * 20 + 0.2 * 150) = 46ms
Total: ~46ms (71% reduction)
```

## Cost Analysis

### Embedding Costs (Monthly Estimate)

**Scenario**: 10,000 documents, 100K chunks, 1M queries/month

**Without Caching**:
- Ingestion: 100K chunks × $0.0001 = $10
- Queries: 1M queries × $0.0001 = $100
- **Total: $110/month**

**With Caching (80% hit rate)**:
- Ingestion: 100K chunks × $0.0001 = $10
- Queries: 1M queries × (0.2 × $0.0001) = $20
- **Total: $30/month (73% savings)**

**Compute Savings**:
- No local model: ~1GB RAM saved
- No GPU needed: $0 GPU costs
- Faster processing: 71% latency reduction

