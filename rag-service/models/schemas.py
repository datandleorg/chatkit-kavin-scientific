from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class DocumentChunk(BaseModel):
    """Represents a chunk of a document"""
    text: str
    chunk_index: int
    start_char: int
    end_char: int
    metadata: Optional[Dict[str, Any]] = None

class DocumentData(BaseModel):
    """Represents processed document data"""
    filename: str
    content: str
    chunks: List[DocumentChunk]
    metadata: Dict[str, Any]
    processing_time: float

class DocumentResponse(BaseModel):
    """Response model for document ingestion"""
    document_id: str
    filename: str
    chunks_count: int
    collection_name: str
    status: str
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Document metadata including file type, processing info, etc.")
    message: Optional[str] = None

class SearchRequest(BaseModel):
    """Request model for search operations"""
    query: str = Field(..., description="Search query")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Additional filters for search")

class Citation(BaseModel):
    """Citation information for a search result"""
    document_id: str
    filename: str
    chunk_index: Optional[int] = None
    image_index: Optional[int] = None

class SearchResult(BaseModel):
    """Individual search result with citation"""
    type: str  # "text" or "image"
    document_id: str
    chunk_index: Optional[int] = None
    image_index: Optional[int] = None
    text: Optional[str] = None
    alt_text: Optional[str] = None
    score: float
    vector_score: Optional[float] = None
    keyword_score: Optional[float] = None
    vision_score: Optional[float] = None
    image_data: Optional[Dict[str, Any]] = None
    citation: Citation

class SearchResponse(BaseModel):
    """Response model for search operations"""
    query: str
    results: List[SearchResult]
    total_results: int
    collection_name: str
    search_type: str
    processing_time: Optional[float] = None
    formatting_applied: Optional[bool] = None
    document_id: Optional[str] = None

class CollectionStats(BaseModel):
    """Statistics for a collection"""
    collection_name: str
    documents_count: int
    vectors_count: int
    created_at: datetime
    last_updated: datetime

class HealthStatus(BaseModel):
    """Health check response"""
    status: str
    qdrant: str
    services: Dict[str, str]
