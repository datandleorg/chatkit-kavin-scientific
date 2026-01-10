"""
OpenAI Embedding Service with MongoDB Caching
Provides embeddings using OpenAI API with intelligent caching to reduce costs
"""
import hashlib
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import os

logger = logging.getLogger(__name__)


class OpenAIEmbeddingService:
    """OpenAI embedding service with MongoDB caching"""
    
    def __init__(self, model: str = "text-embedding-3-small", cache_ttl_days: int = 30):
        """
        Initialize OpenAI embedding service
        
        Args:
            model: OpenAI embedding model name
            cache_ttl_days: Cache TTL in days
        """
        try:
            from openai import OpenAI
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable is required")
            
            self.client = OpenAI(api_key=api_key)
            self.model = model
            self._vector_size = 1536 if "small" in model else 3072
            self.cache_ttl = timedelta(days=cache_ttl_days)
            self.cache_collection = None
            self.db = None
            
            logger.info(f"Initialized OpenAIEmbeddingService with model: {model}, vector_size: {self.vector_size}")
        except ImportError:
            raise ImportError("openai package is required. Install with: pip install openai")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAIEmbeddingService: {e}")
            raise
    
    async def initialize_cache(self, db):
        """
        Initialize cache collection in MongoDB
        
        Args:
            db: MongoDB database instance
        """
        try:
            self.db = db
            self.cache_collection = db["embedding_cache"]
            
            # Create index on hash for fast lookups (using Motor async API)
            # Motor requires list format: [(field, direction)] or string for text index
            try:
                await self.cache_collection.create_index([("hash", 1)], unique=True)
            except Exception as idx_error:
                # If index already exists, ignore the error
                if "E11000" not in str(idx_error) and "duplicate key" not in str(idx_error).lower():
                    logger.warning(f"Could not create hash index (may already exist): {idx_error}")
            
            # Create TTL index for automatic expiration
            await self.cache_collection.create_index(
                [("created_at", 1)],
                expireAfterSeconds=int(self.cache_ttl.total_seconds())
            )
            
            logger.info("Embedding cache initialized in MongoDB")
        except Exception as e:
            logger.error(f"Failed to initialize embedding cache: {e}")
            raise
    
    def _hash_text(self, text: str) -> str:
        """
        Generate SHA256 hash of normalized text
        
        Args:
            text: Input text
            
        Returns:
            SHA256 hash as hex string
        """
        normalized = text.strip().lower()
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()
    
    async def _get_from_cache(self, text_hashes: List[str]) -> Dict[str, List[float]]:
        """
        Retrieve embeddings from cache
        
        Args:
            text_hashes: List of text hashes to look up
            
        Returns:
            Dictionary mapping hash to embedding
        """
        if not self.cache_collection or not text_hashes:
            return {}
        
        try:
            cached = await self.cache_collection.find(
                {"hash": {"$in": text_hashes}}
            ).to_list(length=None)
            
            return {item["hash"]: item["embedding"] for item in cached}
        except Exception as e:
            logger.warning(f"Error retrieving from cache: {e}")
            return {}
    
    async def _save_to_cache(self, cache_entries: List[Dict]):
        """
        Save embeddings to cache
        
        Args:
            cache_entries: List of cache entry dictionaries
        """
        if not self.cache_collection or not cache_entries:
            return
        
        try:
            # Use insert_many with ordered=False to handle duplicates gracefully
            await self.cache_collection.insert_many(cache_entries, ordered=False)
            logger.debug(f"Saved {len(cache_entries)} embeddings to cache")
        except Exception as e:
            # Ignore duplicate key errors (already cached)
            if "duplicate key" not in str(e).lower() and "E11000" not in str(e):
                logger.warning(f"Error saving to cache: {e}")
    
    async def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text (with caching)
        
        Args:
            text: Input text
            
        Returns:
            Embedding vector as list of floats
        """
        results = await self.embed_batch([text])
        return results[0] if results else []
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts (with caching and batching)
        
        Args:
            texts: List of input texts
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        # Generate hashes for all texts
        text_hash_map = {self._hash_text(text): text for text in texts}
        hashes = list(text_hash_map.keys())
        
        # Check cache
        cached = await self._get_from_cache(hashes)
        cached_hashes = set(cached.keys())
        
        # Prepare results array (maintain order)
        results = []
        uncached_texts = []
        uncached_hashes = []
        hash_to_index = {}
        
        for i, (hash_val, text) in enumerate(text_hash_map.items()):
            hash_to_index[hash_val] = i
            if hash_val in cached:
                results.append((i, cached[hash_val]))
            else:
                uncached_texts.append(text)
                uncached_hashes.append(hash_val)
                results.append((i, None))
        
        # Fetch uncached embeddings from OpenAI
        if uncached_texts:
            try:
                # OpenAI API supports up to 2048 inputs per request
                # Process in batches of 100 for safety
                batch_size = 100
                cache_entries = []
                
                for batch_start in range(0, len(uncached_texts), batch_size):
                    batch_texts = uncached_texts[batch_start:batch_start + batch_size]
                    batch_hashes = uncached_hashes[batch_start:batch_start + batch_size]
                    
                    response = self.client.embeddings.create(
                        model=self.model,
                        input=batch_texts
                    )
                    
                    # Process batch results
                    for i, embedding_data in enumerate(response.data):
                        hash_val = batch_hashes[i]
                        text = batch_texts[i]
                        embedding = embedding_data.embedding
                        
                        # Find original index
                        original_index = hash_to_index[hash_val]
                        
                        # Update results
                        for j, (idx, emb) in enumerate(results):
                            if idx == original_index and emb is None:
                                results[j] = (idx, embedding)
                                break
                        
                        # Prepare cache entry
                        cache_entries.append({
                            "hash": hash_val,
                            "text": text,
                            "embedding": embedding,
                            "model": self.model,
                            "created_at": datetime.utcnow()
                        })
                
                # Save all to cache
                if cache_entries:
                    await self._save_to_cache(cache_entries)
                    logger.info(f"Generated {len(cache_entries)} new embeddings, cached {len(cache_entries)}")
                
            except Exception as e:
                logger.error(f"Error generating embeddings from OpenAI: {e}")
                raise
        
        # Return embeddings in original order
        sorted_results = sorted(results, key=lambda x: x[0])
        return [emb for _, emb in sorted_results]
    
    async def get_cache_stats(self) -> Dict[str, any]:
        """
        Get cache statistics
        
        Returns:
            Dictionary with cache statistics
        """
        if not self.cache_collection:
            return {"error": "Cache not initialized"}
        
        try:
            total_cached = await self.cache_collection.count_documents({})
            
            # Count recent entries (last 24 hours)
            yesterday = datetime.utcnow() - timedelta(days=1)
            recent_count = await self.cache_collection.count_documents({
                "created_at": {"$gte": yesterday}
            })
            
            return {
                "total_cached": total_cached,
                "recent_entries_24h": recent_count,
                "model": self.model,
                "vector_size": self.vector_size,
                "cache_ttl_days": self.cache_ttl.days
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"error": str(e)}
    
    @property
    def vector_size(self) -> int:
        """Return the dimension of embeddings"""
        return self._vector_size

