import asyncio
import uuid
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING
from sentence_transformers import SentenceTransformer
import numpy as np
import json
import os

logger = logging.getLogger(__name__)

class VectorStore:
    """Service for managing vector storage with MongoDB"""
    
    def __init__(self, connection_string: str = None, database_name: str = None):
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
        self.embedding_model = None
        self.vector_size = 384  # Default for all-MiniLM-L6-v2
    
    async def initialize(self):
        """Initialize MongoDB client and embedding model"""
        try:
            logger.info(f"Connecting to MongoDB: {self.connection_string}")
            
            # Initialize MongoDB client
            self.client = AsyncIOMotorClient(self.connection_string)
            self.db = self.client[self.database_name]
            
            # Initialize embedding model
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            self.vector_size = self.embedding_model.get_sentence_embedding_dimension()
            
            # Create indexes for better performance
            await self._create_indexes()
            
            logger.info(f"VectorStore initialized with MongoDB, vector size: {self.vector_size}")
            
        except Exception as e:
            logger.error(f"Failed to initialize VectorStore: {e}")
            raise
    
    async def _create_indexes(self):
        """Create necessary indexes for performance"""
        try:
            # Create text index for full-text search
            await self.db.documents.create_index([
                ("text", "text"),
                ("filename", "text")
            ])
            
            # Create compound index for document queries
            await self.db.documents.create_index([
                ("document_id", ASCENDING),
                ("chunk_index", ASCENDING)
            ])
            
            # Create index for metadata filtering
            await self.db.documents.create_index([
                ("filename", ASCENDING),
                ("created_at", DESCENDING)
            ])
            
            logger.info("Created MongoDB indexes for better performance")
            
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
            
            for chunk in document_data["chunks"]:
                # Generate embedding for chunk text
                embedding = self.embedding_model.encode(chunk["text"]).tolist()
                
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
            # Generate query embedding
            query_embedding = self.embedding_model.encode(query).tolist()
            
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
    
    async def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()