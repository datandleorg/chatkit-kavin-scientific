# Codebase Consolidation & Optimization Plan (Revised)

## Executive Summary

This document outlines a plan to:
1. **Replace Sentence Transformers with OpenAI Embeddings + Caching** (saves compute, better quality)
2. **Merge agentkit-backend and rag-service** into a unified backend service
3. **Keep MCP as separate service** (exposed to agent via stdio protocol)

---

## 1. OpenAI Embeddings with Caching

### Current Implementation

**Location**: `rag-service/services/vector_store.py`

**Current Setup**:
- Uses `sentence-transformers>=2.2.2` library
- Model: `all-MiniLM-L6-v2` (384 dimensions)
- Loads model in memory (~500MB-1GB)
- Generates embeddings synchronously
- No caching (re-embeds same text multiple times)

**Problems**:
- High memory usage (model loaded in memory)
- Slow startup (model download/loading)
- No caching (wasteful for duplicate content)
- Limited model quality

### New Implementation: OpenAI Embeddings + Caching

**Benefits**:
- ✅ **Saves Compute**: No local model = no GPU/CPU for embeddings
- ✅ **Better Quality**: OpenAI embeddings are superior (text-embedding-3-small/large)
- ✅ **Faster Startup**: No model loading
- ✅ **Cost Effective**: Caching reduces API calls by 70-90%
- ✅ **Scalable**: No memory constraints from model size

**Architecture**:
```
┌─────────────────────────────────────────┐
│      Embedding Service                  │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │  Cache Layer (Redis/MongoDB)     │  │
│  │  - Text hash → Embedding         │  │
│  │  - TTL: 30 days                  │  │
│  └──────────────────────────────────┘  │
│              │                         │
│              ▼                         │
│  ┌──────────────────────────────────┐  │
│  │  OpenAI API Client               │  │
│  │  - Batch requests                │  │
│  │  - Rate limiting                 │  │
│  │  - Retry logic                   │  │
│  └──────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

**Caching Strategy**:
1. **Cache Key**: SHA256 hash of normalized text
2. **Storage**: MongoDB collection `embedding_cache`
3. **TTL**: 30 days (embeddings don't change)
4. **Batch Processing**: Group uncached texts, batch API calls
5. **Cache Hit Rate**: Expected 70-90% for document ingestion

**Cost Analysis**:
- **Without Cache**: ~$0.0001 per 1K tokens
- **With Cache (80% hit rate)**: ~$0.00002 per 1K tokens
- **Monthly Estimate**: $20-50 for typical usage
- **Savings**: 80% reduction in API costs

**Implementation Details**:

**New File**: `rag-service/services/embedding_service.py`
```python
import hashlib
import json
from typing import List, Dict
from datetime import datetime, timedelta
from openai import OpenAI
import os

class OpenAIEmbeddingService:
    def __init__(self, model: str = "text-embedding-3-small", cache_ttl_days: int = 30):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = model
        self.vector_size = 1536 if "small" in model else 3072
        self.cache_ttl = timedelta(days=cache_ttl_days)
        self.cache_collection = None  # MongoDB collection
    
    async def initialize_cache(self, db):
        """Initialize cache collection"""
        self.cache_collection = db["embedding_cache"]
        # Create index on hash for fast lookups
        await self.cache_collection.create_index("hash", unique=True)
        await self.cache_collection.create_index("created_at", expireAfterSeconds=self.cache_ttl.total_seconds())
    
    def _hash_text(self, text: str) -> str:
        """Generate SHA256 hash of normalized text"""
        normalized = text.strip().lower()
        return hashlib.sha256(normalized.encode()).hexdigest()
    
    async def _get_from_cache(self, text_hashes: List[str]) -> Dict[str, List[float]]:
        """Retrieve embeddings from cache"""
        if not self.cache_collection:
            return {}
        
        cached = await self.cache_collection.find(
            {"hash": {"$in": text_hashes}}
        ).to_list(length=None)
        
        return {item["hash"]: item["embedding"] for item in cached}
    
    async def _save_to_cache(self, cache_entries: List[Dict]):
        """Save embeddings to cache"""
        if not self.cache_collection or not cache_entries:
            return
        
        await self.cache_collection.insert_many(cache_entries)
    
    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding for single text (with caching)"""
        results = await self.embed_batch([text])
        return results[0]
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts (with caching)"""
        if not texts:
            return []
        
        # Generate hashes for all texts
        text_hash_map = {self._hash_text(text): text for text in texts}
        hashes = list(text_hash_map.keys())
        
        # Check cache
        cached = await self._get_from_cache(hashes)
        cached_hashes = set(cached.keys())
        
        # Prepare results array
        results = []
        uncached_texts = []
        uncached_hashes = []
        
        for hash_val, text in text_hash_map.items():
            if hash_val in cached:
                results.append((hash_val, cached[hash_val]))
            else:
                uncached_texts.append(text)
                uncached_hashes.append(hash_val)
                results.append((hash_val, None))
        
        # Fetch uncached embeddings from OpenAI
        if uncached_texts:
            response = self.client.embeddings.create(
                model=self.model,
                input=uncached_texts
            )
            
            # Save to cache
            cache_entries = []
            for i, embedding in enumerate(response.data):
                hash_val = uncached_hashes[i]
                cache_entries.append({
                    "hash": hash_val,
                    "text": uncached_texts[i],
                    "embedding": embedding.embedding,
                    "model": self.model,
                    "created_at": datetime.utcnow()
                })
                # Update results
                for j, (h, _) in enumerate(results):
                    if h == hash_val:
                        results[j] = (h, embedding.embedding)
                        break
            
            await self._save_to_cache(cache_entries)
        
        # Return embeddings in original order
        return [emb for _, emb in results]
    
    @property
    def vector_size(self) -> int:
        return self.vector_size
```

**Migration Steps**:
1. ✅ Create `OpenAIEmbeddingService` with caching
2. ✅ Update `VectorStore` to use embedding service
3. ✅ Add cache collection to MongoDB
4. ✅ Update vector size to 1536 (text-embedding-3-small)
5. ✅ Remove `sentence-transformers` dependency
6. ✅ Add batch processing for better performance
7. ✅ Add cache statistics endpoint

---

## 2. Merging agentkit-backend and rag-service

### Current Architecture

```
┌─────────────────┐
│   Frontend      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      HTTP      ┌─────────────────┐
│ agentkit-backend│ ──────────────►│   rag-service   │
│  (Port 8002)    │                │  (Port 8001)    │
│                 │                │                 │
│ - ChatKit API   │                │ - Document      │
│ - Agent Logic   │                │   Ingestion     │
│ - MCP Tools     │                │ - Vector Search │
└─────────────────┘                └─────────────────┘
```

### Proposed Unified Architecture

```
┌─────────────────┐
│   Frontend      │
└────────┬────────┘
         │
         ▼
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
│  │  - /ingest                        │  │
│  │  - /search                        │  │
│  │  - /collections                   │  │
│  └──────────────────────────────────┘  │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │  Shared Services                  │  │
│  │  - VectorStore (OpenAI + Cache)  │  │
│  │  - DocumentProcessor              │  │
│  │  - HybridSearch                  │  │
│  │  - Agent (with MCP stdio)        │  │
│  └──────────────────────────────────┘  │
└─────────────────────────────────────────┘
         │
         │ stdio
         ▼
┌─────────────────┐
│   MCP Server    │  (Separate Process)
│  (Port 8005)    │
│                 │
│ - Quote Gen     │
│ - File Search   │
│ - API Tools     │
└─────────────────┘
         │
         ▼
┌─────────────────┐
│    MongoDB      │
└─────────────────┘
```

### Benefits of Merging

1. **Simplified Deployment**: Single backend service
2. **Reduced Latency**: Direct function calls instead of HTTP
3. **Shared Resources**: Single connection pool, shared cache
4. **Easier Development**: All backend code in one place
5. **Unified Configuration**: Single environment file

### MCP Remains Separate

**Why Keep MCP Separate**:
- Agent uses MCP via **stdio protocol** (subprocess communication)
- MCP tools are exposed to the agent as external tools
- MCP can be used by other agents/clients
- Separation of concerns (tools vs. backend logic)

**MCP Communication**:
```
Agent (in unified backend)
    │
    │ stdio (subprocess)
    ▼
MCP Server (separate process)
    │
    │ HTTP (internal)
    ▼
Unified Backend (RAG endpoints)
```

---

## 3. Updated Project Structure

### Unified Backend Structure

```
unified-backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app with all routes
│   ├── config.py                  # Configuration management
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── chatkit.py             # ChatKit endpoints
│   │   ├── rag.py                  # RAG endpoints (ingest, search)
│   │   └── health.py               # Health checks
│   │
│   ├── chatkit/
│   │   ├── __init__.py
│   │   ├── server.py              # ChatKit server implementation
│   │   └── agent.py               # Agent setup with MCP
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── vector_store.py        # MongoDB vector operations
│   │   ├── document_processor.py  # Document processing (Docling)
│   │   ├── hybrid_search.py       # Hybrid search logic
│   │   ├── embedding_service.py   # OpenAI embeddings + caching
│   │   └── llm_service.py         # LLM formatting
│   │
│   └── models/
│       ├── __init__.py
│       └── schemas.py             # Pydantic models
│
├── requirements.txt               # Consolidated dependencies
├── Dockerfile
├── docker-compose.yml
└── README.md
```

### MCP Server Structure (Separate)

```
mcp/
├── mcp_server_stdio.py           # Stdio server for agent
├── mcp_server.py                 # HTTP server (optional)
├── tools/
│   ├── quote_generator.py        # Excel quote generation
│   ├── file_search.py            # RAG search wrapper
│   ├── document_tools.py         # Document metadata
│   └── api_tools.py              # External APIs (Hyma, etc.)
├── xml_quote_generator.py
├── requirements.txt
└── README.md
```

---

## 4. Implementation Plan

### Phase 1: OpenAI Embeddings with Caching (Week 1)

**Tasks**:
1. Create `EmbeddingService` with OpenAI + caching
2. Implement cache layer (MongoDB collection)
3. Update `VectorStore` to use embedding service
4. Add batch processing for efficiency
5. Update vector size to 1536
6. Remove `sentence-transformers` dependency
7. Add cache statistics endpoint
8. Test caching effectiveness

**Files to Create/Modify**:
- ✅ `rag-service/services/embedding_service.py` (new)
- ✅ `rag-service/services/vector_store.py` (modify)
- ✅ `rag-service/main.py` (add cache init)
- ✅ `rag-service/requirements.txt` (remove sentence-transformers)
- ✅ `rag-service/config.env` (add embedding config)

**Expected Results**:
- 70-90% cache hit rate
- 80% reduction in API costs
- Faster document ingestion (cached chunks)
- No local model memory usage

### Phase 2: Service Consolidation (Week 2-3)

**Tasks**:
1. Create unified backend structure
2. Move RAG endpoints from `rag-service/main.py` to `unified-backend/app/api/rag.py`
3. Move ChatKit endpoints from `agentkit-backend/app/main.py` to `unified-backend/app/api/chatkit.py`
4. Move ChatKit server logic to `unified-backend/app/chatkit/`
5. Consolidate services (vector_store, document_processor, etc.)
6. Update agent to use internal RAG services (direct calls)
7. Consolidate dependencies
8. Update environment configuration

**Files to Create/Modify**:
- ✅ New unified backend structure
- ✅ Merge `requirements.txt` files
- ✅ Update `docker-compose.yml`
- ✅ Create unified `Dockerfile`
- ✅ Update MCP server to call unified backend (if needed)

**Key Changes**:
- Agent calls RAG services directly (no HTTP)
- MCP still uses stdio protocol
- Single FastAPI app with all endpoints

### Phase 3: Testing & Deployment (Week 4)

**Tasks**:
1. Comprehensive testing
2. Performance testing (caching effectiveness)
3. Update documentation
4. Update frontend configuration
5. Deploy to staging
6. Monitor and verify
7. Deploy to production

---

## 5. Configuration Changes

### Unified Environment Variables

**`.env` file**:
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

# Quote Generation (for MCP)
TEMPLATE_PATH=/app/mcp/quote.xlsx
OUTPUT_DIR=/app/mcp

# DigitalOcean Spaces
DO_ACCESS_KEY=your_key
DO_SECRET_KEY=your_secret
DO_SPACE_NAME=optimus
DO_REGION=ams3
DO_ENDPOINT=ams3.digitaloceanspaces.com

# MCP Server (separate)
MCP_RAG_SERVICE_URL=http://unified-backend:8000
```

### Docker Compose Updates

**Updated `docker-compose.yml`**:
```yaml
services:
  mongodb:
    # ... existing config ...
  
  unified-backend:
    build:
      context: ./unified-backend
      dockerfile: Dockerfile
    container_name: unified_backend
    restart: unless-stopped
    ports:
      - "8000:8000"
    env_file:
      - ./.env
    environment:
      - MONGODB_CONNECTION_STRING=mongodb://${MONGO_USERNAME:-admin}:${MONGO_PASSWORD:-password123}@mongodb:27017/${MONGO_DATABASE:-rag_db}?authSource=admin
      - DATABASE_NAME=${MONGO_DATABASE:-rag_db}
    depends_on:
      mongodb:
        condition: service_healthy
    volumes:
      - ./unified-backend/uploads:/app/uploads
      - ./unified-backend/templates:/app/templates
      - ./unified-backend/outputs:/app/outputs
      - ./mcp:/app/mcp:ro  # MCP tools (read-only)
    networks:
      - app_network
    deploy:
      resources:
        limits:
          memory: 4G  # Reduced from 10G (no local model)
        reservations:
          memory: 1G
  
  mcp-server:
    build:
      context: ./mcp
      dockerfile: Dockerfile
    container_name: mcp_server
    restart: unless-stopped
    ports:
      - "8005:8005"  # Optional HTTP endpoint
    env_file:
      - ./.env
    environment:
      - RAG_SERVICE_URL=http://unified-backend:8000
      - TEMPLATE_PATH=/app/quote.xlsx
      - OUTPUT_DIR=/app/outputs
    volumes:
      - ./mcp:/app
      - ./mcp/quote.xlsx:/app/quote.xlsx:ro
      - ./mcp/outputs:/app/outputs
    networks:
      - app_network
    # Note: MCP stdio is used by agent, not HTTP
  
  frontend:
    build:
      context: ./agentkit-frontend
      dockerfile: Dockerfile
    container_name: frontend
    restart: unless-stopped
    ports:
      - "8081:80"
    environment:
      - BACKEND_URL=http://unified-backend:8000
    depends_on:
      - unified-backend
    networks:
      - app_network
```

---

## 6. Migration Checklist

### Pre-Migration
- [ ] Backup current codebase
- [ ] Document current API endpoints
- [ ] Test current functionality
- [ ] Create migration branch

### Phase 1: OpenAI Embeddings
- [ ] Create `OpenAIEmbeddingService` with caching
- [ ] Implement MongoDB cache collection
- [ ] Update `VectorStore` to use embedding service
- [ ] Add batch processing
- [ ] Update vector size to 1536
- [ ] Remove `sentence-transformers` dependency
- [ ] Add cache statistics endpoint
- [ ] Test caching (verify hit rates)
- [ ] Monitor API costs

### Phase 2: Service Consolidation
- [ ] Create unified backend structure
- [ ] Move RAG endpoints
- [ ] Move ChatKit endpoints
- [ ] Consolidate services
- [ ] Update agent to use internal services
- [ ] Update MCP server configuration
- [ ] Consolidate dependencies
- [ ] Update environment files
- [ ] Update Docker configuration

### Phase 3: Testing & Deployment
- [ ] Unit tests for embedding service
- [ ] Integration tests for RAG endpoints
- [ ] Integration tests for ChatKit endpoints
- [ ] Test MCP stdio communication
- [ ] Performance testing (caching)
- [ ] End-to-end tests
- [ ] Update documentation
- [ ] Deploy to staging
- [ ] Monitor and verify
- [ ] Deploy to production

---

## 7. Expected Benefits

### Performance
- **Reduced Memory**: No local model (saves ~1GB RAM)
- **Faster Startup**: No model loading (saves 5-10 seconds)
- **Better Embeddings**: OpenAI quality > sentence-transformers
- **Caching**: 70-90% cache hit rate = 80% cost reduction

### Cost
- **API Costs**: ~$20-50/month (with caching)
- **Savings**: 80% reduction vs. no caching
- **Compute Savings**: No GPU/CPU for embeddings

### Architecture
- **Simpler**: One backend service instead of two
- **Faster**: Direct calls instead of HTTP
- **Maintainable**: All backend code in one place

---

## 8. Risk Assessment

### Low Risk
- OpenAI embeddings (well-tested API)
- Caching implementation (standard pattern)
- Service consolidation (both are FastAPI)

### Medium Risk
- Cache migration (existing embeddings need re-embedding)
- MCP communication (stdio subprocess)

### Mitigation Strategies
1. **Gradual Migration**: Keep old services running during transition
2. **Cache Warmup**: Pre-populate cache with common queries
3. **Fallback**: Keep sentence-transformers as backup (optional)
4. **Monitoring**: Track cache hit rates and API costs
5. **Rollback Plan**: Keep old code for quick rollback

---

## 9. Timeline

**Week 1**: OpenAI Embeddings with Caching
- Days 1-2: Create embedding service with caching
- Days 3-4: Update VectorStore and test
- Day 5: Monitor and optimize cache

**Week 2**: Service Consolidation (Part 1)
- Days 1-2: Create unified structure
- Days 3-4: Move RAG endpoints
- Day 5: Move ChatKit endpoints

**Week 3**: Service Consolidation (Part 2)
- Days 1-2: Consolidate services
- Days 3-4: Update agent and MCP
- Day 5: Testing and fixes

**Week 4**: Testing & Deployment
- Days 1-2: Comprehensive testing
- Day 3: Update documentation
- Days 4-5: Deploy and monitor

**Total**: 4 weeks

---

## 10. Key Decisions

✅ **OpenAI Embeddings**: Better quality, saves compute
✅ **Caching**: 80% cost reduction, faster responses
✅ **Merge Backends**: Simpler architecture, better performance
✅ **Keep MCP Separate**: Required for stdio protocol with agent

---

## 11. Next Steps

1. **Review this revised plan**
2. **Start Phase 1** (OpenAI embeddings + caching)
3. **Monitor cache effectiveness**
4. **Proceed to Phase 2** (service consolidation)
5. **Test and deploy**

---

## Conclusion

This revised plan:
- ✅ Uses OpenAI embeddings with caching (saves compute, reduces costs)
- ✅ Merges agentkit-backend and rag-service (simpler architecture)
- ✅ Keeps MCP separate (required for agent stdio communication)
- ✅ Maintains all functionality while improving performance

The migration can be done incrementally with minimal risk, and each phase can be tested independently.
