import asyncio
import uuid
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING
import os

from app.services.embedding_service import OpenAIEmbeddingService

logger = logging.getLogger(__name__)

class VectorStore:
    """Service for managing vector storage with MongoDB"""
    
    def __init__(self, connection_string: str = None, database_name: str = None, embedding_service: OpenAIEmbeddingService = None):
        # Use environment variables if not provided
        self.connection_string = connection_string or os.getenv(
            'MONGODB_CONNECTION_STRING', 
            'mongodb://localhost:27017'
        )
        self.database_name = database_name or os.getenv(
            'DATABASE_NAME', 
            'rag_db'
        )
        self.client = None
        self.db = None
        self.embedding_service = embedding_service
        self.vector_size = 1536  # Default for text-embedding-3-small
    
    async def initialize(self, embedding_service: OpenAIEmbeddingService = None):
        """Initialize MongoDB client and embedding service"""
        try:
            # Log connection string (mask password for security)
            masked_conn = self.connection_string
            if '@' in masked_conn:
                parts = masked_conn.split('@')
                if len(parts) == 2:
                    masked_conn = f"mongodb://***@{parts[1]}"
            logger.info(f"Connecting to MongoDB: {masked_conn}")
            logger.info(f"Database name: {self.database_name}")
            
            # Initialize MongoDB client
            self.client = AsyncIOMotorClient(self.connection_string)
            self.db = self.client[self.database_name]
            
            # Test connection
            try:
                await self.client.admin.command('ping')
                logger.info("MongoDB connection successful")
            except Exception as ping_error:
                # Check if it's an auth error
                if "authentication" in str(ping_error).lower() or "unauthorized" in str(ping_error).lower():
                    logger.error(f"MongoDB authentication failed: {ping_error}")
                    logger.error("Please set MONGODB_CONNECTION_STRING with proper credentials")
                    logger.error("Example: mongodb://username:password@host:port/database?authSource=admin")
                    raise ConnectionError(f"MongoDB authentication required: {ping_error}")
                else:
                    logger.error(f"MongoDB connection test failed: {ping_error}")
                    raise
            
            # Initialize embedding service
            if embedding_service:
                self.embedding_service = embedding_service
            elif not self.embedding_service:
                # Create new embedding service if not provided
                embedding_model = os.getenv('EMBEDDING_MODEL', 'text-embedding-3-small')
                cache_ttl_days = int(os.getenv('EMBEDDING_CACHE_TTL_DAYS', '30'))
                self.embedding_service = OpenAIEmbeddingService(
                    model=embedding_model,
                    cache_ttl_days=cache_ttl_days
                )
            
            # Ensure required collections exist
            await self._ensure_collections()
            
            # Initialize cache
            await self.embedding_service.initialize_cache(self.db)
            
            # Get vector size from embedding service
            self.vector_size = self.embedding_service.vector_size
            
            # Create indexes for better performance
            await self._create_indexes()
            
            logger.info(f"VectorStore initialized with MongoDB, vector size: {self.vector_size}")
            
        except Exception as e:
            logger.error(f"Failed to initialize VectorStore: {e}")
            raise
    
    async def _ensure_collections(self):
        """Ensure required collections (embedding_cache and documents) exist"""
        try:
            required_collections = ["embedding_cache", "documents"]
            existing_collections = await self.db.list_collection_names()
            
            for collection_name in required_collections:
                if collection_name not in existing_collections:
                    # Create collection by inserting and deleting a dummy document
                    await self.db[collection_name].insert_one({
                        "_temp": True,
                        "created_at": datetime.now()
                    })
                    await self.db[collection_name].delete_one({"_temp": True})
                    logger.info(f"Created collection: {collection_name}")
                else:
                    logger.debug(f"Collection {collection_name} already exists")
                    
        except Exception as e:
            logger.warning(f"Failed to ensure collections exist (collections may be created lazily): {e}")
    
    async def _create_indexes(self):
        """Create necessary indexes for performance"""
        try:
            # Create text index for full-text search
            try:
                await self.db.documents.create_index([
                    ("text", "text"),
                    ("filename", "text")
                ])
            except Exception as idx_error:
                # Check if it's an auth error
                if "authentication" in str(idx_error).lower() or "unauthorized" in str(idx_error).lower():
                    logger.warning(f"MongoDB authentication required for index creation. Index may already exist or you need proper credentials: {idx_error}")
                elif "already exists" in str(idx_error).lower() or "E11000" in str(idx_error):
                    logger.debug(f"Text index already exists, skipping")
                else:
                    logger.warning(f"Could not create text index: {idx_error}")
            
            # Create compound index for document queries
            try:
                await self.db.documents.create_index([
                    ("document_id", ASCENDING),
                    ("chunk_index", ASCENDING)
                ])
            except Exception as idx_error:
                if "authentication" in str(idx_error).lower() or "unauthorized" in str(idx_error).lower():
                    logger.warning(f"MongoDB authentication required for index creation: {idx_error}")
                elif "already exists" in str(idx_error).lower() or "E11000" in str(idx_error):
                    logger.debug(f"Compound index already exists, skipping")
                else:
                    logger.warning(f"Could not create compound index: {idx_error}")
            
            # Create index for metadata filtering
            try:
                await self.db.documents.create_index([
                    ("filename", ASCENDING),
                    ("created_at", DESCENDING)
                ])
            except Exception as idx_error:
                if "authentication" in str(idx_error).lower() or "unauthorized" in str(idx_error).lower():
                    logger.warning(f"MongoDB authentication required for index creation: {idx_error}")
                elif "already exists" in str(idx_error).lower() or "E11000" in str(idx_error):
                    logger.debug(f"Metadata index already exists, skipping")
                else:
                    logger.warning(f"Could not create metadata index: {idx_error}")
            
            logger.info("MongoDB indexes checked/created (some may require authentication)")
            
        except Exception as e:
            logger.error(f"Failed to create indexes: {e}")
    
    async def health_check(self) -> str:
        """Check if MongoDB is accessible"""
        try:
            await self.client.admin.command('ping')
            return "healthy"
        except Exception as e:
            logger.error(f"MongoDB health check failed: {e}")
            return "unhealthy"
    
    async def store_document(
        self, 
        document_data: Dict[str, Any], 
        collection_name: str = "documents",
        metadata: Dict[str, Any] = None
    ) -> str:
        """Store document chunks in MongoDB"""
        try:
            # Generate document ID
            document_id = str(uuid.uuid4())
            
            # Prepare documents for insertion
            documents_to_insert = []
            
            # Collect all chunk texts for batch embedding
            chunk_texts = [chunk["text"] for chunk in document_data["chunks"]]
            
            # Generate embeddings in batch (with caching)
            embeddings = await self.embedding_service.embed_batch(chunk_texts)
            
            for i, chunk in enumerate(document_data["chunks"]):
                # Get embedding from batch result
                embedding = embeddings[i]
                
                # Prepare document metadata with citation information
                doc_metadata = {
                    "document_id": document_id,
                    "chunk_index": chunk["chunk_index"],
                    "text": chunk["text"],
                    "start_char": chunk["start_char"],
                    "end_char": chunk["end_char"],
                    "filename": document_data["filename"],
                    "file_type": document_data.get("metadata", {}).get("file_type", "unknown"),
                    "page_number": chunk.get("metadata", {}).get("page_number"),
                    "created_at": datetime.now(),
                    "ingestion_date": datetime.now().isoformat(),
                    "embedding": embedding,
                    "metadata": metadata or {},
                    **chunk.get("metadata", {})
                }
                
                documents_to_insert.append(doc_metadata)
            
            # Insert documents into MongoDB
            result = await self.db[collection_name].insert_many(documents_to_insert)
            
            logger.info(f"Stored document {document_id} with {len(documents_to_insert)} chunks in MongoDB")
            return document_id
            
        except Exception as e:
            logger.error(f"Failed to store document: {e}")
            raise
    
    async def search_similar(
        self,
        query: str,
        collection_name: str = "documents",
        limit: int = 10,
        score_threshold: float = 0.0,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar documents using vector similarity"""
        try:
            # Generate query embedding (with caching)
            query_embedding = await self.embedding_service.embed_text(query)
            
            # Prepare aggregation pipeline for vector search
            pipeline = []
            
            # Add match stage for filters
            match_stage = {}
            if filters:
                for key, value in filters.items():
                    match_stage[key] = value
            
            if match_stage:
                pipeline.append({"$match": match_stage})
            
            # Add vector similarity calculation
            pipeline.extend([
                {
                    "$addFields": {
                        "similarity_score": {
                            "$divide": [
                                {
                                    "$reduce": {
                                        "input": {"$range": [0, {"$size": "$embedding"}]},
                                        "initialValue": 0,
                                        "in": {
                                            "$add": [
                                                "$$value",
                                                {
                                                    "$multiply": [
                                                        {"$arrayElemAt": ["$embedding", "$$this"]},
                                                        {"$arrayElemAt": [query_embedding, "$$this"]}
                                                    ]
                                                }
                                            ]
                                        }
                                    }
                                },
                                {
                                    "$multiply": [
                                        {
                                            "$sqrt": {
                                                "$reduce": {
                                                    "input": "$embedding",
                                                    "initialValue": 0,
                                                    "in": {"$add": ["$$value", {"$multiply": ["$$this", "$$this"]}]}
                                                }
                                            }
                                        },
                                        {
                                            "$sqrt": {
                                                "$reduce": {
                                                    "input": query_embedding,
                                                    "initialValue": 0,
                                                    "in": {"$add": ["$$value", {"$multiply": ["$$this", "$$this"]}]}
                                                }
                                            }
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                },
                {"$match": {"similarity_score": {"$gte": score_threshold}}},
                {"$sort": {"similarity_score": -1}},
                {"$limit": limit}
            ])
            
            # Execute aggregation
            cursor = self.db[collection_name].aggregate(pipeline)
            results = await cursor.to_list(length=limit)
            
            # Format results
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "document_id": result["document_id"],
                    "chunk_index": result["chunk_index"],
                    "text": result["text"],
                    "score": result["similarity_score"],
                    "metadata": {k: v for k, v in result.items() 
                               if k not in ["document_id", "chunk_index", "text", "similarity_score", "embedding", "_id"]}
                })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            raise
    
    async def search_text(
        self,
        query: str,
        collection_name: str = "documents",
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search for documents using MongoDB text search"""
        try:
            # Prepare search query
            search_query = {
                "$text": {"$search": query}
            }
            
            # Add filters
            if filters:
                search_query.update(filters)
            
            # Execute text search
            cursor = self.db[collection_name].find(
                search_query,
                {"score": {"$meta": "textScore"}}
            ).sort([("score", {"$meta": "textScore"})]).limit(limit)
            
            results = await cursor.to_list(length=limit)
            
            # Format results
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "document_id": result["document_id"],
                    "chunk_index": result["chunk_index"],
                    "text": result["text"],
                    "score": result.get("score", 0.0),
                    "metadata": {k: v for k, v in result.items() 
                               if k not in ["document_id", "chunk_index", "text", "score", "embedding", "_id"]}
                })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Text search failed: {e}")
            raise
    
    async def create_collection(self, collection_name: str) -> bool:
        """Create a new collection with indexes"""
        try:
            # Check if collection already exists
            existing_collections = await self.db.list_collection_names()
            if collection_name in existing_collections:
                logger.warning(f"Collection {collection_name} already exists")
                return False
            
            # Create collection by inserting and deleting a dummy document
            await self.db[collection_name].insert_one({
                "_temp": True,
                "created_at": datetime.now()
            })
            await self.db[collection_name].delete_one({"_temp": True})
            
            # Create indexes for the new collection
            await self.db[collection_name].create_index([
                ("text", "text"),
                ("filename", "text")
            ])
            
            await self.db[collection_name].create_index([
                ("document_id", ASCENDING),
                ("chunk_index", ASCENDING)
            ])
            
            await self.db[collection_name].create_index([
                ("filename", ASCENDING),
                ("created_at", DESCENDING)
            ])
            
            logger.info(f"Created collection: {collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create collection {collection_name}: {e}")
            raise
    
    async def list_collections(self) -> List[str]:
        """List all collections"""
        try:
            collections = await self.db.list_collection_names()
            return collections
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            raise
    
    async def get_collection_stats(self, collection_name: str = "documents") -> Dict[str, Any]:
        """Get statistics for a collection"""
        try:
            # Count total documents
            total_docs = await self.db[collection_name].count_documents({})
            
            # Count unique documents
            unique_docs = len(await self.db[collection_name].distinct("document_id"))
            
            # Get collection info
            stats = await self.db.command("collStats", collection_name)
            
            return {
                "collection_name": collection_name,
                "total_chunks": total_docs,
                "unique_documents": unique_docs,
                "storage_size": stats.get("storageSize", 0),
                "index_size": stats.get("totalIndexSize", 0),
                "vector_size": self.vector_size
            }
            
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            raise
    
    async def delete_collection(self, collection_name: str) -> bool:
        """Delete a collection"""
        try:
            await self.db[collection_name].drop()
            logger.info(f"Deleted collection: {collection_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection {collection_name}: {e}")
            raise
    
    async def get_document(self, document_id: str, collection_name: str = "documents") -> Optional[Dict[str, Any]]:
        """Get document by ID"""
        try:
            # Find all chunks of the document
            cursor = self.db[collection_name].find(
                {"document_id": document_id}
            ).sort("chunk_index", ASCENDING)
            
            chunks = await cursor.to_list(length=None)
            
            if not chunks:
                return None
            
            # Extract document metadata from first chunk
            metadata = {
                "document_id": document_id,
                "filename": chunks[0]["filename"],
                "created_at": chunks[0]["created_at"]
            }
            
            # Format chunks
            formatted_chunks = []
            for chunk in chunks:
                formatted_chunks.append({
                    "chunk_index": chunk["chunk_index"],
                    "text": chunk["text"],
                    "start_char": chunk["start_char"],
                    "end_char": chunk["end_char"]
                })
            
            return {
                "document_id": document_id,
                "chunks": formatted_chunks,
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"Failed to get document {document_id}: {e}")
            raise
    
    async def list_documents(self, collection_name: str = "documents") -> List[Dict[str, Any]]:
        """List all unique documents with their metadata"""
        try:
            # Use aggregation to get unique documents with metadata
            pipeline = [
                {
                    "$group": {
                        "_id": "$document_id",
                        "filename": {"$first": "$filename"},
                        "file_type": {"$first": "$file_type"},
                        "created_at": {"$first": "$created_at"},
                        "ingestion_date": {"$first": "$ingestion_date"},
                        "chunks_count": {"$sum": 1},
                        "metadata": {"$first": "$metadata"}
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "document_id": "$_id",
                        "filename": 1,
                        "file_type": 1,
                        "created_at": 1,
                        "ingestion_date": 1,
                        "chunks_count": 1,
                        "metadata": 1
                    }
                },
                {
                    "$sort": {"created_at": DESCENDING}
                }
            ]
            
            cursor = self.db[collection_name].aggregate(pipeline)
            documents = await cursor.to_list(length=None)
            
            return documents
            
        except Exception as e:
            logger.error(f"Failed to list documents: {e}")
            raise
    
    async def delete_document(self, document_id: str, collection_name: str = "documents") -> bool:
        """Delete a document and all its chunks by document_id"""
        try:
            # Delete all chunks with this document_id
            result = await self.db[collection_name].delete_many({"document_id": document_id})
            
            deleted_count = result.deleted_count
            logger.info(f"Deleted document {document_id}: {deleted_count} chunks removed")
            
            return deleted_count > 0
            
        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {e}")
            raise
    
    async def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()