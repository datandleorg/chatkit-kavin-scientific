import asyncio
import logging
from typing import List, Dict, Any, Optional
from services.vector_store import VectorStore
from models.schemas import SearchResult

logger = logging.getLogger(__name__)

class HybridSearch:
<<<<<<< HEAD
    """Service for performing hybrid search combining vector and keyword search"""
=======
    """Service for performing hybrid search combining vector and text search"""
>>>>>>> 743801bcc0d94f9953f34961b803df0b4769c53d
    
    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store
    
    async def search(
        self,
        query: str,
        collection_name: str = "documents",
        limit: int = 10,
<<<<<<< HEAD
        score_threshold: float = 0.0,
        document_id: Optional[str] = None,
=======
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
>>>>>>> 743801bcc0d94f9953f34961b803df0b4769c53d
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search combining vector similarity and keyword matching
        
        Args:
            query: Search query
            collection_name: Collection to search in
            limit: Maximum number of results
<<<<<<< HEAD
            score_threshold: Minimum score threshold for results (0.0-1.0)
            document_id: Optional document ID to search within a specific document only
            filters: Additional filters for search
            
        Returns:
            List of search results
        """
        try:
            # Add document_id to filters if provided
            if document_id:
                if filters is None:
                    filters = {}
                filters["document_id"] = document_id
                logger.info(f"Searching within document: {document_id}")
            
            logger.info(f"Performing hybrid search with score_threshold={score_threshold}")
            
            # Perform parallel searches
            tasks = []
            
            # Text vector search
            tasks.append(self.vector_store.search_similar(
                query=query,
                collection_name=collection_name,
                limit=limit * 2,
                score_threshold=score_threshold,
                filters=filters
            ))
            
            # Keyword search
            tasks.append(self.vector_store.search_text(
=======
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
>>>>>>> 743801bcc0d94f9953f34961b803df0b4769c53d
                query=query,
                collection_name=collection_name,
                limit=limit * 2,
                filters=filters
<<<<<<< HEAD
            ))
            
            # Vision search (for images)
            tasks.append(self.vector_store.search_images(
                query=query,
                collection_name=collection_name,
                limit=limit * 2,
                filters=filters
            ))
            
            # Wait for all searches to complete
            search_results = await asyncio.gather(*tasks, return_exceptions=True)
            vector_results = search_results[0]
            keyword_results = search_results[1]
            vision_results = search_results[2]
=======
            )
            
            # Wait for both searches to complete
            vector_results, keyword_results = await asyncio.gather(
                vector_task, keyword_task, return_exceptions=True
            )
>>>>>>> 743801bcc0d94f9953f34961b803df0b4769c53d
            
            # Handle exceptions
            if isinstance(vector_results, Exception):
                logger.error(f"Vector search failed: {vector_results}")
                vector_results = []
            
            if isinstance(keyword_results, Exception):
                logger.error(f"Keyword search failed: {keyword_results}")
                keyword_results = []
            
            # Combine results
            combined_results = self._combine_search_results(
<<<<<<< HEAD
                vector_results=vector_results if not isinstance(vector_results, Exception) else [],
                keyword_results=keyword_results if not isinstance(keyword_results, Exception) else [],
                vision_results=vision_results if not isinstance(vision_results, Exception) else [],
                score_threshold=score_threshold,
=======
                vector_results=vector_results,
                keyword_results=keyword_results,
                vector_weight=vector_weight,
                keyword_weight=keyword_weight,
>>>>>>> 743801bcc0d94f9953f34961b803df0b4769c53d
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
<<<<<<< HEAD
        vision_results: List[Dict[str, Any]],
        score_threshold: float,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Combine vector, keyword, and vision search results"""
=======
        vector_weight: float,
        keyword_weight: float,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Combine vector and keyword search results"""
>>>>>>> 743801bcc0d94f9953f34961b803df0b4769c53d
        
        # Create a dictionary to store combined results
        combined_dict = {}
        
<<<<<<< HEAD
        # Process vector results (text chunks)
        for result in vector_results:
            if result["score"] < score_threshold:
                continue
                
            key = f"{result['document_id']}_{result['chunk_index']}"
            
=======
        # Process vector results
        for result in vector_results:
            key = f"{result['document_id']}_{result['chunk_index']}"
>>>>>>> 743801bcc0d94f9953f34961b803df0b4769c53d
            combined_dict[key] = {
                "document_id": result["document_id"],
                "chunk_index": result["chunk_index"],
                "text": result["text"],
                "vector_score": result["score"],
                "keyword_score": 0.0,
<<<<<<< HEAD
                "vision_score": 0.0,
                "combined_score": result["score"],
=======
                "combined_score": result["score"] * vector_weight,
>>>>>>> 743801bcc0d94f9953f34961b803df0b4769c53d
                "metadata": result["metadata"]
            }
        
        # Process keyword results
        for result in keyword_results:
<<<<<<< HEAD
            if result["score"] < score_threshold:
                continue
                
            key = f"{result['document_id']}_{result['chunk_index']}"
            if key in combined_dict:
                # Update existing result with keyword score
                combined_dict[key]["keyword_score"] = result["score"]
                # Average the scores for combined_score (should be between 0-1)
                current_score = combined_dict[key]["combined_score"]
                combined_dict[key]["combined_score"] = (current_score + result["score"]) / 2.0
=======
            key = f"{result['document_id']}_{result['chunk_index']}"
            if key in combined_dict:
                # Update existing result
                combined_dict[key]["keyword_score"] = result["score"]
                combined_dict[key]["combined_score"] += result["score"] * keyword_weight
>>>>>>> 743801bcc0d94f9953f34961b803df0b4769c53d
            else:
                # Add new result
                combined_dict[key] = {
                    "document_id": result["document_id"],
                    "chunk_index": result["chunk_index"],
                    "text": result["text"],
                    "vector_score": 0.0,
                    "keyword_score": result["score"],
<<<<<<< HEAD
                    "vision_score": 0.0,
                    "combined_score": result["score"],
                    "metadata": result["metadata"]
                }
        
        # Process vision results (images)
        for result in vision_results:
            if result["score"] < score_threshold:
                continue
                
            doc_id = result["document_id"]
            img_idx = result.get("image_index", 0)
            key = f"{doc_id}_img_{img_idx}"
            
            combined_dict[key] = {
                "document_id": doc_id,
                "chunk_index": None,
                "image_index": img_idx,
                "text": result.get("alt_text", ""),
                "vector_score": 0.0,
                "keyword_score": 0.0,
                "vision_score": result["score"],
                "combined_score": result["score"],
                "has_images": True,
                "image_data": {
                    "alt_text": result.get("alt_text", ""),
                    "format": result.get("format", "unknown"),
                    "width": result.get("width"),
                    "height": result.get("height"),
                    "size_bytes": result.get("size_bytes", 0),
                    "base64_data": result.get("base64_data")
                },
                "metadata": result["metadata"]
            }
        
=======
                    "combined_score": result["score"] * keyword_weight,
                    "metadata": result["metadata"]
                }
        
>>>>>>> 743801bcc0d94f9953f34961b803df0b4769c53d
        # Convert to list and sort by combined score
        combined_results = list(combined_dict.values())
        combined_results.sort(key=lambda x: x["combined_score"], reverse=True)
        
        # Format results to match schema with citations
        formatted_results = []
        for result in combined_results[:limit]:
            # Extract citation information from metadata
<<<<<<< HEAD
            metadata = result.get("metadata", {})
            
            # For image results, citation is different
            if result.get("has_images"):
                citation = {
                    "document_id": result["document_id"],
                    "filename": metadata.get("metadata", {}).get("filename", "Unknown"),
                    "image_index": result.get("image_index")
                }
            else:
                citation = {
                    "document_id": result["document_id"],
                    "filename": metadata.get("metadata", {}).get("filename", "Unknown"),
                    "chunk_index": result.get("chunk_index")
                }
            
            # Determine if this is a text result or an image result
            is_image_result = result.get("has_images", False)
            
            if is_image_result:
                # This is an IMAGE result - standalone image
                formatted_result = {
                    "type": "image",
                    "document_id": result["document_id"],
                    "image_index": result.get("image_index"),
                    "alt_text": result.get("text", ""),
                    "score": result["combined_score"],
                    "vision_score": result.get("vision_score", 0.0),
                    "image_data": result.get("image_data"),
                    "citation": citation
                }
            else:
                # This is a TEXT result - text chunk
                formatted_result = {
                    "type": "text",
                    "document_id": result["document_id"],
                    "chunk_index": result.get("chunk_index"),
                    "text": result["text"],
                    "score": result["combined_score"],
                    "vector_score": result.get("vector_score", 0.0),
                    "keyword_score": result.get("keyword_score", 0.0),
                    "citation": citation
                }
            
            formatted_results.append(formatted_result)
=======
            metadata = result["metadata"]
            citation = {
                "document_id": result["document_id"],
                "filename": metadata.get("metadata", {}).get("filename", "Unknown"),
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
>>>>>>> 743801bcc0d94f9953f34961b803df0b4769c53d
        
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
                
                metadata = result["metadata"]

                citation = {
                    "document_id": result["document_id"],
                    "filename": metadata.get("metadata", {}).get("filename", "Unknown"),
                    "page_number": metadata.get("page_number"),
                    "chunk_index": result["chunk_index"],
                    "start_char": metadata.get("start_char"),
                    "end_char": metadata.get("end_char"),
                    "document_type": metadata.get("file_type"),
                    "ingestion_date": metadata.get("ingestion_date")
                }
                
                formatted_results.append({
<<<<<<< HEAD
                    "type": "text",
=======
>>>>>>> 743801bcc0d94f9953f34961b803df0b4769c53d
                    "document_id": result["document_id"],
                    "chunk_index": result["chunk_index"],
                    "text": result["text"],
                    "score": result["score"],
                    "search_type": "vector",
                    "metadata": result["metadata"],
                    "citation": citation
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
                metadata = result["metadata"]
                citation = {
                    "document_id": result["document_id"],
                    "filename": metadata.get("metadata", {}).get("filename", "Unknown"),
                    "page_number": metadata.get("page_number"),
                    "chunk_index": result["chunk_index"],
                    "start_char": metadata.get("start_char"),
                    "end_char": metadata.get("end_char"),
                    "document_type": metadata.get("file_type"),
                    "ingestion_date": metadata.get("ingestion_date")
                }
                
                formatted_results.append({
<<<<<<< HEAD
                    "type": "text",
=======
>>>>>>> 743801bcc0d94f9953f34961b803df0b4769c53d
                    "document_id": result["document_id"],
                    "chunk_index": result["chunk_index"],
                    "text": result["text"],
                    "score": result["score"],
                    "search_type": "keyword",
                    "metadata": result["metadata"],
                    "citation": citation
                })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Keyword-only search failed: {e}")
            raise
