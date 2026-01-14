"""
RAG API endpoints for document ingestion and search
"""
from fastapi import APIRouter, File, UploadFile, HTTPException, Query
from typing import List, Optional, Dict, Any
import os
import uuid
from pathlib import Path
import logging

from app.models.schemas import DocumentResponse, SearchResponse, SearchRequest
from app.services.document_processor import DocumentProcessor
from app.services.vector_store import VectorStore
from app.services.hybrid_search import HybridSearch
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rag", tags=["RAG"])

# These will be initialized in main.py
document_processor = DocumentProcessor()
vector_store: Optional[VectorStore] = None
hybrid_search: Optional[HybridSearch] = None
llm_service = LLMService()

# Create upload directory
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@router.get("/health")
async def health_check():
    """Detailed health check"""
    try:
        if not vector_store:
            raise HTTPException(status_code=503, detail="Vector store not initialized")
        
        # Check if MongoDB is accessible
        mongodb_status = await vector_store.health_check()
        return {
            "status": "healthy",
            "mongodb": mongodb_status,
            "services": {
                "document_processor": "ready",
                "vector_store": "ready",
                "hybrid_search": "ready" if hybrid_search else "not ready"
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")


@router.post("/ingest", response_model=DocumentResponse)
async def ingest_document(
    file: UploadFile = File(...),
    collection_name: str = Query(default="documents", description="Collection name for storing documents"),
    chunk_size: int = Query(default=1000, description="Size of text chunks"),
    chunk_overlap: int = Query(default=200, description="Overlap between chunks")
):
    """
    Ingest a document (PDF, DOCX, TXT, XLSX, XLS, CSV) and store it in the vector database
    """
    if not vector_store:
        raise HTTPException(status_code=503, detail="Vector store not initialized")
    
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


@router.post("/search")
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
    if not hybrid_search:
        raise HTTPException(status_code=503, detail="Hybrid search not initialized")
    
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


@router.post("/collections")
async def create_collection(collection_name: str = Query(..., description="Name of the collection to create")):
    """Create a new collection with proper indexes"""
    if not vector_store:
        raise HTTPException(status_code=503, detail="Vector store not initialized")
    
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


@router.get("/collections")
async def list_collections():
    """List all available collections"""
    if not vector_store:
        raise HTTPException(status_code=503, detail="Vector store not initialized")
    
    try:
        collections = await vector_store.list_collections()
        return {"collections": collections}
    except Exception as e:
        logger.error(f"Failed to list collections: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list collections: {str(e)}")


@router.get("/collections/{collection_name}/stats")
async def collection_stats(collection_name: str):
    """Get statistics for a specific collection"""
    if not vector_store:
        raise HTTPException(status_code=503, detail="Vector store not initialized")
    
    try:
        stats = await vector_store.get_collection_stats(collection_name)
        return stats
    except Exception as e:
        logger.error(f"Failed to get collection stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get collection stats: {str(e)}")


@router.delete("/collections/{collection_name}")
async def delete_collection(collection_name: str):
    """Delete a collection and all its documents"""
    if not vector_store:
        raise HTTPException(status_code=503, detail="Vector store not initialized")
    
    try:
        await vector_store.delete_collection(collection_name)
        return {"message": f"Collection '{collection_name}' deleted successfully"}
    except Exception as e:
        logger.error(f"Failed to delete collection: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete collection: {str(e)}")


@router.get("/embedding/cache/stats")
async def get_cache_stats():
    """Get embedding cache statistics"""
    if not vector_store or not vector_store.embedding_service:
        return {"error": "Embedding service not initialized"}
    
    try:
        stats = await vector_store.embedding_service.get_cache_stats()
        return stats
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get cache stats: {str(e)}")


@router.get("/documents")
async def list_documents(
    collection_name: str = Query(default="documents", description="Collection name to list documents from")
):
    """List all ingested documents with their metadata"""
    if not vector_store:
        raise HTTPException(status_code=503, detail="Vector store not initialized")
    
    try:
        documents = await vector_store.list_documents(collection_name=collection_name)
        return {
            "documents": documents,
            "total": len(documents),
            "collection_name": collection_name
        }
    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {str(e)}")


@router.get("/documents/{document_id}")
async def get_document(
    document_id: str,
    collection_name: str = Query(default="documents", description="Collection name to get document from")
):
    """Get document metadata by ID"""
    if not vector_store:
        raise HTTPException(status_code=503, detail="Vector store not initialized")
    
    try:
        document = await vector_store.get_document(document_id, collection_name=collection_name)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        return document
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get document: {str(e)}")


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    collection_name: str = Query(default="documents", description="Collection name to delete document from")
):
    """Delete a document and all its chunks by ID"""
    if not vector_store:
        raise HTTPException(status_code=503, detail="Vector store not initialized")
    
    try:
        deleted = await vector_store.delete_document(document_id, collection_name=collection_name)
        if not deleted:
            raise HTTPException(status_code=404, detail="Document not found")
        return {
            "message": f"Document {document_id} deleted successfully",
            "document_id": document_id,
            "collection_name": collection_name
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete document: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")

