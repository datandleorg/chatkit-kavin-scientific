import asyncio
import logging
from typing import List, Dict, Any, Optional
from services.vector_store import VectorStore
from models.schemas import SearchResult

logger = logging.getLogger(__name__)

class HybridSearch:
    """Service for performing hybrid search combining vector and text search"""
    
    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store
    
    async def search(
        self,
        query: str,
        collection_name: str = "documents",
        limit: int = 10,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search combining vector similarity and keyword matching
        
        Args:
            query: Search query
            collection_name: Collection to search in
            limit: Maximum number of results
            vector_weight: Weight for vector search (0.0-1.0)
            keyword_weight: Weight for keyword search (0.0-1.0)
            filters: Additional filters for search
            
        Returns:
            List of search results with combined scores
        """
        try:
            # Normalize weights
            total_weight = vector_weight + keyword_weight
            if total_weight > 0:
                vector_weight = vector_weight / total_weight
                keyword_weight = keyword_weight / total_weight
            
            logger.info(f"Performing hybrid search with vector_weight={vector_weight}, keyword_weight={keyword_weight}")
            
            # Perform both searches concurrently
            vector_task = self.vector_store.search_similar(
                query=query,
                collection_name=collection_name,
                limit=limit * 2,  # Get more results to ensure good coverage
                filters=filters
            )
            
            keyword_task = self.vector_store.search_text(
                query=query,
                collection_name=collection_name,
                limit=limit * 2,
                filters=filters
            )
            
            # Wait for both searches to complete
            vector_results, keyword_results = await asyncio.gather(
                vector_task, keyword_task, return_exceptions=True
            )
            
            # Handle exceptions
            if isinstance(vector_results, Exception):
                logger.error(f"Vector search failed: {vector_results}")
                vector_results = []
            
            if isinstance(keyword_results, Exception):
                logger.error(f"Keyword search failed: {keyword_results}")
                keyword_results = []
            
            # Combine results
            combined_results = self._combine_search_results(
                vector_results=vector_results,
                keyword_results=keyword_results,
                vector_weight=vector_weight,
                keyword_weight=keyword_weight,
                limit=limit
            )
            
            logger.info(f"Hybrid search completed, found {len(combined_results)} results")
            return combined_results
            
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            raise
    
    def _combine_search_results(
        self,
        vector_results: List[Dict[str, Any]],
        keyword_results: List[Dict[str, Any]],
        vector_weight: float,
        keyword_weight: float,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Combine vector and keyword search results"""
        
        # Create a dictionary to store combined results
        combined_dict = {}
        
        # Process vector results
        for result in vector_results:
            key = f"{result['document_id']}_{result['chunk_index']}"
            combined_dict[key] = {
                "document_id": result["document_id"],
                "chunk_index": result["chunk_index"],
                "text": result["text"],
                "vector_score": result["score"],
                "keyword_score": 0.0,
                "combined_score": result["score"] * vector_weight,
                "metadata": result["metadata"]
            }
        
        # Process keyword results
        for result in keyword_results:
            key = f"{result['document_id']}_{result['chunk_index']}"
            if key in combined_dict:
                # Update existing result
                combined_dict[key]["keyword_score"] = result["score"]
                combined_dict[key]["combined_score"] += result["score"] * keyword_weight
            else:
                # Add new result
                combined_dict[key] = {
                    "document_id": result["document_id"],
                    "chunk_index": result["chunk_index"],
                    "text": result["text"],
                    "vector_score": 0.0,
                    "keyword_score": result["score"],
                    "combined_score": result["score"] * keyword_weight,
                    "metadata": result["metadata"]
                }
        
        # Convert to list and sort by combined score
        combined_results = list(combined_dict.values())
        combined_results.sort(key=lambda x: x["combined_score"], reverse=True)
        
        # Format results to match schema with citations
        formatted_results = []
        for result in combined_results[:limit]:
            # Extract citation information from metadata
            metadata = result["metadata"]
            citation = {
                "document_id": result["document_id"],
                "filename": metadata.get("filename", "Unknown"),
                "page_number": metadata.get("page_number"),
                "chunk_index": result["chunk_index"],
                "start_char": metadata.get("start_char"),
                "end_char": metadata.get("end_char"),
                "document_type": metadata.get("file_type"),
                "ingestion_date": metadata.get("ingestion_date")
            }
            
            formatted_results.append({
                "document_id": result["document_id"],
                "chunk_index": result["chunk_index"],
                "text": result["text"],
                "score": result["combined_score"],
                "metadata": result["metadata"],
                "citation": citation
            })
        
        return formatted_results
    
    async def search_vector_only(
        self,
        query: str,
        collection_name: str = "documents",
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Perform vector-only search"""
        try:
            results = await self.vector_store.search_similar(
                query=query,
                collection_name=collection_name,
                limit=limit,
                filters=filters
            )
            
            # Format results for consistency
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "document_id": result["document_id"],
                    "chunk_index": result["chunk_index"],
                    "text": result["text"],
                    "score": result["score"],
                    "search_type": "vector",
                    "metadata": result["metadata"]
                })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Vector-only search failed: {e}")
            raise
    
    async def search_keyword_only(
        self,
        query: str,
        collection_name: str = "documents",
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Perform keyword-only search"""
        try:
            results = await self.vector_store.search_text(
                query=query,
                collection_name=collection_name,
                limit=limit,
                filters=filters
            )
            
            # Format results for consistency
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "document_id": result["document_id"],
                    "chunk_index": result["chunk_index"],
                    "text": result["text"],
                    "score": result["score"],
                    "search_type": "keyword",
                    "metadata": result["metadata"]
                })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Keyword-only search failed: {e}")
            raise
