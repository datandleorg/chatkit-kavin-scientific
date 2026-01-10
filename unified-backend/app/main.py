"""
Unified Backend Service - Combining RAG and ChatKit
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
# Try to load from .env file, but don't fail if it doesn't exist
env_file = Path(".env")
if env_file.exists():
    load_dotenv(env_file)
else:
    # Also try config.env for backward compatibility
    config_env = Path("config.env")
    if config_env.exists():
        load_dotenv(config_env)
    load_dotenv()  # Load from environment variables

# Import services
from app.services.document_processor import DocumentProcessor
from app.services.vector_store import VectorStore
from app.services.hybrid_search import HybridSearch
from app.services.llm_service import LLMService
from app.services.embedding_service import OpenAIEmbeddingService

# Import API routes
from app.api import rag, chatkit, health

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Unified Backend Service",
    description="Combined RAG and ChatKit backend service",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services (will be set in startup)
document_processor = DocumentProcessor()
vector_store: VectorStore = None
hybrid_search: HybridSearch = None
llm_service = LLMService()

# Create upload directory
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global vector_store, hybrid_search, llm_service
    
    logger.info("Starting Unified Backend Service...")
    
    # Initialize embedding service
    embedding_model = os.getenv('EMBEDDING_MODEL', 'text-embedding-3-small')
    cache_ttl_days = int(os.getenv('EMBEDDING_CACHE_TTL_DAYS', '30'))
    embedding_service = OpenAIEmbeddingService(
        model=embedding_model,
        cache_ttl_days=cache_ttl_days
    )
    
    # Initialize vector store with embedding service
    vector_store = VectorStore()
    await vector_store.initialize(embedding_service=embedding_service)
    
    # Initialize hybrid search
    hybrid_search = HybridSearch(vector_store)
    
    # Initialize LLM service
    await llm_service.initialize()
    
    # Set services in API modules
    rag.vector_store = vector_store
    rag.hybrid_search = hybrid_search
    rag.llm_service = llm_service
    
    health.vector_store = vector_store
    
    logger.info("Unified Backend Service started successfully!")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down Unified Backend Service...")
    if hasattr(chatkit.server, 'cleanup'):
        await chatkit.server.cleanup()


# Include routers
app.include_router(health.router)
app.include_router(rag.router)
app.include_router(chatkit.router)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    logger.info(f"Starting Unified Backend Service on {host}:{port}")
    uvicorn.run(app, host=host, port=port)

