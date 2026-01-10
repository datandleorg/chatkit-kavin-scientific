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
    message: Optional[str] = None

class SearchRequest(BaseModel):
    """Request model for search operations"""
    query: str = Field(..., description="Search query")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Additional filters for search")

class Citation(BaseModel):
    """Citation information for a search result"""
    document_id: str
    filename: str
    page_number: Optional[int] = None
    chunk_index: int
    start_char: Optional[int] = None
    end_char: Optional[int] = None
    document_type: Optional[str] = None
    ingestion_date: Optional[str] = None

class SearchResult(BaseModel):
    """Individual search result with citation"""
    document_id: str
    chunk_index: int
    text: str
    score: float
    metadata: Dict[str, Any]
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
