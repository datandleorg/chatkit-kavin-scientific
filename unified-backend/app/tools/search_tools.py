"""
Search tools for Kavin Scientific Agent
"""
import os
import logging
import time
import uuid
import asyncio
from typing import Optional

from agents import function_tool
from app.api import rag
from app.models.schemas import SearchRequest

logger = logging.getLogger(__name__)


async def _perform_search(
    query: str,
    collection_name: str = "documents",
    limit: int = 10,
    request_id: str = ""
) -> str:
    """Internal async function to perform the search"""
    try:
        # Check if services are initialized
        if not rag.hybrid_search:
            logger.error(f"[RequestID: {request_id}] Hybrid search service not initialized")
            return "Search service not available. Please ensure the service is running."
        
        logger.debug(f"[RequestID: {request_id}] Performing hybrid search directly using RAG services")
        
        # Create search request
        search_request = SearchRequest(query=query, filters={})
        
        # Perform hybrid search
        search_results = await rag.hybrid_search.search(
            query=query,
            collection_name=collection_name,
            limit=limit,
            vector_weight=0.7,
            keyword_weight=0.3,
            filters=search_request.filters
        )
        
        # Format results with LLM service (text_only=True, llm_format=False)
        formatted_results = await rag.llm_service.format_search_results(
            search_results=search_results,
            query=query,
            text_only=True,
            llm_format=False,
            provider="openai"
        )
        
        # Extract content from formatted results
        content = formatted_results.get('formatted_content') or formatted_results.get('text_content', '')
        
        if content:
            content_length = len(content)
            logger.info(f"✅ [RequestID: {request_id}] Search successful. Found content ({content_length} characters)")
            logger.debug(f"[RequestID: {request_id}] Search content preview: {content[:500]}...")
            return content
        else:
            logger.warning(f"⚠️  [RequestID: {request_id}] No content found for query: '{query}'")
            return f"No relevant content found for query: '{query}'"
            
    except Exception as e:
        logger.error(f"❌ [RequestID: {request_id}] Error during file search: {str(e)}", exc_info=True)
        return f"Error during file search: {str(e)}"


@function_tool
def file_search(
    query: str,
    collection_name: str = "documents",
    limit: int = 10
) -> str:
    """
    Search through uploaded documents using the RAG service. Returns formatted text-only results based on the search query.
    
    Args:
        query: The search query to find relevant content
        collection_name: Collection to search in (default: documents)
        limit: Maximum number of results to return (default: 10)
    
    Returns:
        Formatted text content from the search results, or error message
    """
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    logger.info("=" * 60)
    logger.info(f"🔧 [RequestID: {request_id}] Tool Call: file_search")
    logger.info(f"📥 [RequestID: {request_id}] Query: '{query}', collection: '{collection_name}', limit: {limit}")
    logger.info("=" * 60)
    
    try:
        # Run async search function - handle both cases: with and without existing event loop
        try:
            # Try to get existing event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, create a new event loop in a thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, _perform_search(query, collection_name, limit, request_id))
                    content = future.result(timeout=30.0)
            else:
                content = loop.run_until_complete(_perform_search(query, collection_name, limit, request_id))
        except RuntimeError:
            # No event loop exists, create a new one
            content = asyncio.run(_perform_search(query, collection_name, limit, request_id))
        
        elapsed_time = time.time() - start_time
        if content and not content.startswith("Error") and not content.startswith("Search service"):
            logger.info(f"✅ [RequestID: {request_id}] Tool 'file_search' completed successfully in {elapsed_time:.2f}s")
        else:
            logger.info(f"⏱️  [RequestID: {request_id}] Tool 'file_search' completed in {elapsed_time:.2f}s")
        logger.info("=" * 60)
        return content
        
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"❌ [RequestID: {request_id}] Error during file search: {str(e)}", exc_info=True)
        logger.info(f"⏱️  [RequestID: {request_id}] Tool 'file_search' failed after {elapsed_time:.2f}s")
        logger.info("=" * 60)
        return f"Error during file search: {str(e)}"

