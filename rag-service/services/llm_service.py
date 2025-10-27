import asyncio
import logging
from typing import List, Dict, Any, Optional
import os
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

class LLMService:
    """Service for LLM-based content formatting and processing"""
    
    def __init__(self):
        self.openai_client = None
        self.default_provider = os.getenv('LLM_PROVIDER', 'openai')
        
    async def initialize(self):
        """Initialize LLM clients"""
        try:
            # Initialize OpenAI client
            openai_api_key = os.getenv('OPENAI_API_KEY')
            if openai_api_key:
                self.openai_client = AsyncOpenAI(api_key=openai_api_key)
                logger.info("OpenAI client initialized")
            else:
                logger.warning("No OpenAI API key found. LLM features will be disabled.")
                
        except Exception as e:
            logger.error(f"Failed to initialize LLM clients: {e}")
    
    async def format_content(
        self, 
        content: str, 
        query: str, 
        provider: str = None,
        model: str = None,
        preserve_citations: bool = True
    ) -> str:
        """
        Format content using LLM based on the query
        
        Args:
            content: The content to format (search results with citations)
            query: The user query to guide formatting
            provider: LLM provider (e.g., 'openai')
            model: Specific model to use
            preserve_citations: Whether to preserve citation information
            
        Returns:
            Formatted content in markdown format
        """
        try:
            provider = provider or self.default_provider
            
            if provider == 'openai' and self.openai_client:
                return await self._format_with_openai(content, query, model, preserve_citations)
            else:
                logger.warning(f"LLM provider {provider} not available, returning original content")
                return content
                
        except Exception as e:
            logger.error(f"LLM formatting failed: {e}")
            return content  # Return original content on error
    
    async def _format_with_openai(self, content: str, query: str, model: str = None, preserve_citations: bool = True) -> str:
        """Format content using OpenAI in markdown format without truncating details"""
        model = model or os.getenv('OPENAI_MODEL', 'gpt-5')
        
        # # Extract citations from content if they exist
        # citations = []
        # if preserve_citations and "Source:" in content:
        #     # Extract citation information
        #     lines = content.split('\n')
        #     for line in lines:
        #         if line.strip().startswith('Source:'):
        #             citations.append(line.strip())
        
        # # Remove citations from content for LLM processing
        # content_for_llm = content
        # if preserve_citations and citations:
        #     # Remove citation lines for LLM processing
        #     lines = content.split('\n')
        #     content_lines = []
        #     for line in lines:
        #         if not line.strip().startswith('Source:'):
        #             content_lines.append(line)
        #     content_for_llm = '\n'.join(content_lines)
        
        system_prompt = f"""You are a helpful assistant"""
        
        user_prompt = f"{query}\n\n\n{content}"

        print(user_prompt)
        
        response = await self.openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=4000,  # Increased to avoid truncation
            temperature=0.1   # Lower temperature for more consistent formatting
        )
        
        formatted_content = response.choices[0].message.content

        print("**************************************")
        print(formatted_content)
        
        # Re-add citations if they were preserved
        # if preserve_citations and citations:
        #     formatted_content += "\n\n## Sources\n" + "\n".join(citations)
        
        return formatted_content
    
    async def format_search_results_with_query(
        self, 
        search_results: List[Dict[str, Any]], 
        query: str,
        provider: str = None
    ) -> str:
        """
        Format search results based on query in markdown format
        
        Args:
            search_results: List of search results with citations
            query: The user's search query
            provider: LLM provider to use
            
        Returns:
            Formatted markdown content with all details preserved
        """
        try:
            # Extract text content with citations
            text_content = self.extract_text_only(search_results)
            
            if self.openai_client:
                # Use LLM to format the content in markdown
                formatted_content = await self.format_content(text_content, query, provider, preserve_citations=True)
                return formatted_content
            else:
                # Return original content if LLM not available
                return text_content
                
        except Exception as e:
            logger.error(f"Error formatting search results: {e}")
            return self.extract_text_only(search_results)
    
    def _format_citation(self, citation: Dict[str, Any], index: int) -> str:
        """Format citation information consistently"""
        citation_text = f"[{index}]"
        if citation.get('filename'):
            citation_text += f" {citation['filename']}"
        if citation.get('page_number'):
            citation_text += f", Page {citation['page_number']}"
        return citation_text
    
    def extract_text_only(self, search_results: List[Dict[str, Any]]) -> str:
        """
        Extract and concatenate only the text content from search results with citations
        
        Args:
            search_results: List of search result dictionaries
            
        Returns:
            Concatenated text content with citations
        """
        try:
            text_parts = []
            for i, result in enumerate(search_results, 1):
                if 'text' in result and result['text']:
                    text = result['text'].strip()
                    citation = result.get('citation', {})
                    
                    # Add citation information using helper method
                    citation_text = self._format_citation(citation, i)
                    
                    text_parts.append(f"{text}\n\nSource: {citation_text}")
            
            return "\n\n".join(text_parts)
            
        except Exception as e:
            logger.error(f"Failed to extract text: {e}")
            return ""
    
    async def format_search_results(
        self, 
        search_results: List[Dict[str, Any]], 
        query: str,
        text_only: bool = False,
        llm_format: bool = False,
        provider: str = None
    ) -> Dict[str, Any]:
        """
        Format search results based on parameters
        
        Args:
            search_results: List of search results
            query: User query
            text_only: Whether to return only text content
            llm_format: Whether to use LLM for formatting
            provider: LLM provider
            
        Returns:
            Formatted results
        """
        try:
            if text_only:
                # Extract only text content
                text_content = self.extract_text_only(search_results)
                
                if llm_format and self.openai_client:
                    # Use LLM to format the content in markdown without truncating details
                    formatted_content = await self.format_content(text_content, query, provider, preserve_citations=True)
                    return {
                        "formatted_content": formatted_content,
                        "original_text": text_content,
                        "total_results": len(search_results),
                        "formatting_applied": True
                    }
                else:
                    return {
                        "text_content": text_content,
                        "total_results": len(search_results),
                        "formatting_applied": False
                    }
            else:
                # Return full results with optional LLM formatting
                if llm_format and self.openai_client:
                    # Format each result individually while preserving citations
                    formatted_results = []
                    for result in search_results:
                        if 'text' in result:
                            # Create text with citation for LLM formatting
                            citation = result.get('citation', {})
                            citation_text = self._format_citation(citation, len(formatted_results) + 1)
                            
                            text_with_citation = f"{result['text']}\n\nSource: {citation_text}"
                            formatted_text = await self.format_content(text_with_citation, query, provider, preserve_citations=True)
                            
                            formatted_result = result.copy()
                            formatted_result['formatted_text'] = formatted_text
                            formatted_results.append(formatted_result)
                        else:
                            formatted_results.append(result)
                    
                    return {
                        "results": formatted_results,
                        "total_results": len(formatted_results),
                        "formatting_applied": True
                    }
                else:
                    return {
                        "results": search_results,
                        "total_results": len(search_results),
                        "formatting_applied": False
                    }
                    
        except Exception as e:
            logger.error(f"Failed to format search results: {e}")
            return {
                "results": search_results,
                "total_results": len(search_results),
                "formatting_applied": False,
                "error": str(e)
            }
