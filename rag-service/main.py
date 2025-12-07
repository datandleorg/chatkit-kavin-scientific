from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import uuid
import asyncio
from pathlib import Path
import logging
from dotenv import load_dotenv

# Load environment variables from config.env
load_dotenv('config.env')

from services.document_processor import DocumentProcessor
from services.vector_store import VectorStore
from services.hybrid_search import HybridSearch
from services.llm_service import LLMService
from models.schemas import DocumentResponse, SearchResponse, SearchRequest

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="RAG Service",
    description="Document ingestion and hybrid search service using Docling and Qdrant",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
document_processor = DocumentProcessor()
vector_store = None
hybrid_search = None
llm_service = LLMService()

# Create upload directory
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global vector_store, hybrid_search, llm_service
    
    logger.info("Starting RAG Service...")
    
    # Initialize vector store with environment variables
    vector_store = VectorStore()
    await vector_store.initialize()
    
    # Initialize hybrid search
    hybrid_search = HybridSearch(vector_store)
    
    # Initialize LLM service
    await llm_service.initialize()
    
    logger.info("RAG Service started successfully!")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down RAG Service...")

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "RAG Service is running", "status": "healthy"}

@app.get("/health")
async def health_check():
    """Detailed health check"""
    try:
        # Check if MongoDB is accessible
        mongodb_status = await vector_store.health_check()
        return {
            "status": "healthy",
            "mongodb": mongodb_status,
            "services": {
                "document_processor": "ready",
                "vector_store": "ready",
                "hybrid_search": "ready"
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")

@app.post("/ingest", response_model=DocumentResponse)
async def ingest_document(
    file: UploadFile = File(...),
    collection_name: str = Query(default="documents", description="Collection name for storing documents"),
    chunk_size: int = Query(default=1000, description="Size of text chunks"),
    chunk_overlap: int = Query(default=200, description="Overlap between chunks")
):
    """
    Ingest a document (PDF, DOCX, TXT, XLSX, XLS, CSV) and store it in the vector database
    """
    try:
        # Validate file type
        allowed_types = [".pdf", ".docx", ".txt", ".xlsx", ".xls", ".csv"]
        file_extension = Path(file.filename).suffix.lower()
        
        if file_extension not in allowed_types:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type. Allowed types: {allowed_types}"
            )
        
        # Save uploaded file
        file_id = str(uuid.uuid4())
        file_path = UPLOAD_DIR / f"{file_id}{file_extension}"
        
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        logger.info(f"Processing document: {file.filename}")
        
        # Process document with Docling
        document_data = await document_processor.process_document(
            file_path=file_path,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        
        # Store in vector database
        document_id = await vector_store.store_document(
            document_data=document_data,
            collection_name=collection_name,
            metadata={
                "filename": file.filename,
                "file_type": file_extension,
                "file_id": file_id,
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap
            }
        )
        
        # Clean up uploaded file
        file_path.unlink()
        
        return DocumentResponse(
            document_id=document_id,
            filename=file.filename,
            chunks_count=len(document_data["chunks"]),
            collection_name=collection_name,
            status="success"
        )
        
    except Exception as e:
        logger.error(f"Document ingestion failed: {e}")
        # Clean up file if it exists
        if 'file_path' in locals() and file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=f"Document ingestion failed: {str(e)}")

@app.post("/search")
async def search_documents(
    request: SearchRequest,
    collection_name: str = Query(default="documents", description="Collection name to search in"),
    limit: int = Query(default=10, description="Maximum number of results"),
    hybrid_weight: float = Query(default=0.7, description="Weight for hybrid search (0.0-1.0)"),
    text_only: bool = Query(default=False, description="Return only concatenated text content"),
    llm_format: bool = Query(default=False, description="Use LLM to format content based on query"),
    llm_provider: str = Query(default="openai", description="LLM provider (openai only)")
):
    """
    Perform hybrid search combining vector similarity and keyword matching
    with optional LLM formatting and text-only output
    """
    try:
        if hybrid_weight < 0.0 or hybrid_weight > 1.0:
            raise HTTPException(
                status_code=400,
                detail="hybrid_weight must be between 0.0 and 1.0"
            )
        
        logger.info(f"Performing hybrid search for query: {request.query}")
        
        # Perform hybrid search
        search_results = await hybrid_search.search(
            query=request.query,
            collection_name=collection_name,
            limit=limit,
            vector_weight=hybrid_weight,
            keyword_weight=1.0 - hybrid_weight,
            filters=request.filters
        )
        
        # Apply LLM formatting and text-only options
        formatted_results = await llm_service.format_search_results(
            search_results=search_results,
            query=request.query,
            text_only=text_only,
            llm_format=llm_format,
            provider=llm_provider
        )
        
        # Return appropriate response format
        if text_only:
            return {
                "query": request.query,
                "collection_name": collection_name,
                "search_type": "hybrid",
                **formatted_results
            }
        else:
            return SearchResponse(
                query=request.query,
                results=formatted_results.get("results", search_results),
                total_results=formatted_results.get("total_results", len(search_results)),
                collection_name=collection_name,
                search_type="hybrid",
                formatting_applied=formatted_results.get("formatting_applied", False)
            )
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.post("/collections")
async def create_collection(collection_name: str = Query(..., description="Name of the collection to create")):
    """Create a new collection with proper indexes"""
    try:
        logger.info(f"Creating collection: {collection_name}")
        
        # Validate collection name
        if not collection_name or not collection_name.strip():
            raise HTTPException(status_code=400, detail="Collection name cannot be empty")
        
        # MongoDB collection name restrictions
        if ' ' in collection_name or collection_name.startswith('$'):
            raise HTTPException(status_code=400, detail="Invalid collection name")
        
        success = await vector_store.create_collection(collection_name)
        
        if success:
            return {
                "message": f"Collection '{collection_name}' created successfully",
                "collection_name": collection_name,
                "status": "created"
            }
        else:
            return {
                "message": f"Collection '{collection_name}' already exists",
                "collection_name": collection_name,
                "status": "exists"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create collection: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create collection: {str(e)}")

@app.get("/collections")
async def list_collections():
    """List all available collections"""
    try:
        collections = await vector_store.list_collections()
        return {"collections": collections}
    except Exception as e:
        logger.error(f"Failed to list collections: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list collections: {str(e)}")

@app.get("/collections/{collection_name}/stats")
async def collection_stats(collection_name: str):
    """Get statistics for a specific collection"""
    try:
        stats = await vector_store.get_collection_stats(collection_name)
        return stats
    except Exception as e:
        logger.error(f"Failed to get collection stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get collection stats: {str(e)}")

@app.delete("/collections/{collection_name}")
async def delete_collection(collection_name: str):
    """Delete a collection and all its documents"""
    try:
        await vector_store.delete_collection(collection_name)
        return {"message": f"Collection '{collection_name}' deleted successfully"}
    except Exception as e:
        logger.error(f"Failed to delete collection: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete collection: {str(e)}")

@app.post("/search/vector", response_model=SearchResponse)
async def search_vector_only(
    request: SearchRequest,
    collection_name: str = Query(default="documents", description="Collection name to search in"),
    limit: int = Query(default=10, description="Maximum number of results")
):
    """Perform vector-only search using semantic similarity"""
    try:
        logger.info(f"Performing vector search for query: {request.query}")
        
        search_results = await hybrid_search.search_vector_only(
            query=request.query,
            collection_name=collection_name,
            limit=limit,
            filters=request.filters
        )
        
        return SearchResponse(
            query=request.query,
            results=search_results,
            total_results=len(search_results),
            collection_name=collection_name,
            search_type="vector"
        )
        
    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Vector search failed: {str(e)}")

@app.post("/search/keyword", response_model=SearchResponse)
async def search_keyword_only(
    request: SearchRequest,
    collection_name: str = Query(default="documents", description="Collection name to search in"),
    limit: int = Query(default=10, description="Maximum number of results")
):
    """Perform keyword-only search using MongoDB text search"""
    try:
        logger.info(f"Performing keyword search for query: {request.query}")
        
        search_results = await hybrid_search.search_keyword_only(
            query=request.query,
            collection_name=collection_name,
            limit=limit,
            filters=request.filters
        )
        
        return SearchResponse(
            query=request.query,
            results=search_results,
            total_results=len(search_results),
            collection_name=collection_name,
            search_type="keyword"
        )
        
    except Exception as e:
        logger.error(f"Keyword search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Keyword search failed: {str(e)}")

@app.get("/documents/{document_id}")
async def get_document(document_id: str):
    """Get document metadata by ID"""
    try:
        document = await vector_store.get_document(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        return document
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get document: {str(e)}")

@app.post("/documents/{document_id}/search")
async def search_single_document(
    document_id: str,
    request: SearchRequest,
    collection_name: str = Query(default="documents", description="Collection name to search in"),
    limit: int = Query(default=10, description="Maximum number of results"),
    text_only: bool = Query(default=False, description="Return only concatenated text content"),
    llm_format: bool = Query(default=False, description="Use LLM to format content based on query"),
    llm_provider: str = Query(default="openai", description="LLM provider (openai only)")
):
    """
    Search within a specific document by ID
    """
    try:
        logger.info(f"Searching within document {document_id} for query: {request.query}")
        
        # First verify the document exists
        document = await vector_store.get_document(document_id, collection_name)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Add document filter to search filters
        search_filters = request.filters or {}
        search_filters["document_id"] = document_id
        
        # Perform hybrid search with document filter
        search_results = await hybrid_search.search(
            query=request.query,
            collection_name=collection_name,
            limit=limit,
            vector_weight=0.7,
            keyword_weight=0.3,
            filters=search_filters
        )
        
        # Apply LLM formatting and text-only options
        formatted_results = await llm_service.format_search_results(
            search_results=search_results,
            query=request.query,
            text_only=text_only,
            llm_format=llm_format,
            provider=llm_provider
        )
        
        # Return appropriate response format
        if text_only:
            return {
                "query": request.query,
                "document_id": document_id,
                "collection_name": collection_name,
                "search_type": "document_search",
                **formatted_results
            }
        else:
            return SearchResponse(
                query=request.query,
                results=formatted_results.get("results", search_results),
                total_results=formatted_results.get("total_results", len(search_results)),
                collection_name=collection_name,
                search_type="document_search",
                formatting_applied=formatted_results.get("formatting_applied", False),
                document_id=document_id
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Document search failed: {str(e)}")

@app.delete("/admin/reset")
async def reset_database():
    """Reset/clear all collections and vector database"""
    try:
        logger.info("Starting database reset...")
        
        # Get all collections
        collections = await vector_store.list_collections()
        
        reset_results = {
            "deleted_collections": [],
            "total_collections_deleted": 0,
            "status": "success",
            "message": "All collections and vector database cleared successfully"
        }
        
        # Delete each collection
        for collection_name in collections:
            try:
                await vector_store.delete_collection(collection_name)
                reset_results["deleted_collections"].append(collection_name)
                logger.info(f"Deleted collection: {collection_name}")
            except Exception as e:
                logger.error(f"Failed to delete collection {collection_name}: {e}")
                reset_results["deleted_collections"].append(f"{collection_name} (failed: {str(e)})")
        
        reset_results["total_collections_deleted"] = len(reset_results["deleted_collections"])
        
        logger.info(f"Database reset completed. Deleted {reset_results['total_collections_deleted']} collections.")
        return reset_results
        
    except Exception as e:
        logger.error(f"Database reset failed: {e}")
        raise HTTPException(status_code=500, detail=f"Database reset failed: {str(e)}")

@app.delete("/admin/collections/{collection_name}")
async def delete_specific_collection(collection_name: str):
    """Delete a specific collection"""
    try:
        logger.info(f"Deleting collection: {collection_name}")
        
        await vector_store.delete_collection(collection_name)
        
        return {
            "collection_name": collection_name,
            "status": "success",
            "message": f"Collection '{collection_name}' deleted successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to delete collection {collection_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete collection: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
