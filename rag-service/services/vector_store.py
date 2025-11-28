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
import base64
from io import BytesIO
from PIL import Image

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
        self.vision_model = None
        self.vector_size = 384  # Default for all-MiniLM-L6-v2
        self.vision_vector_size = 512  # For CLIP-ViT-B-32
    
    async def initialize(self):
        """Initialize MongoDB client and embedding model"""
        try:
            logger.info(f"Connecting to MongoDB: {self.connection_string}")
            
            # Initialize MongoDB client
            self.client = AsyncIOMotorClient(self.connection_string)
            self.db = self.client[self.database_name]
            
            # Initialize embedding models
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            self.vector_size = self.embedding_model.get_sentence_embedding_dimension()
            
            # Initialize vision model (CLIP) for multimodal embeddings
            try:
                # Try to load CLIP model
                # Note: This requires torch and transformers, sentence-transformers supports this
                import torch
                
                self.vision_model = SentenceTransformer('clip-ViT-B-32')
                self.vision_vector_size = 512
                logger.info("CLIP vision model initialized for visual embeddings")
            except Exception as e:
                logger.warning(f"Failed to initialize CLIP vision model: {e}")
                self.vision_model = None
                self.vision_vector_size = 0
            
            # Create indexes for better performance
            await self._create_indexes()
            
            logger.info(f"VectorStore initialized with MongoDB, text vector size: {self.vector_size}, vision vector size: {self.vision_vector_size}")
            
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
    
    def _generate_vision_embedding(self, base64_data: str) -> Optional[List[float]]:
        """
        Generate vision embedding for a base64 encoded image using CLIP.
        
        Note: Images are NOT chunked before embedding. CLIP generates a single embedding
        for the entire image. This is different from text processing where we chunk text
        into smaller pieces. CLIP's embeddings capture the full visual content of an image.
        """
        if not self.vision_model:
            return None
        
        try:
            # Decode base64 image
            image_bytes = base64.b64decode(base64_data)
            image = Image.open(BytesIO(image_bytes))
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Generate embedding using CLIP (single embedding for full image)
            vision_embedding = self.vision_model.encode(image).tolist()
            
            logger.debug(f"Generated vision embedding of size {len(vision_embedding)}")
            return vision_embedding
            
        except Exception as e:
            logger.warning(f"Failed to generate vision embedding: {e}")
            return None
    
    async def store_document(
        self, 
        document_data: Dict[str, Any], 
        collection_name: str = "documents",
        metadata: Dict[str, Any] = None
    ) -> str:
        """Store document chunks in MongoDB with optional vision embeddings"""
        try:
            # Generate document ID
            document_id = str(uuid.uuid4())
            
            # Check if document has images
            doc_metadata = document_data.get("metadata", {})
            has_images = doc_metadata.get("has_images", False)
            images_data = doc_metadata.get("images", [])
            
            # Prepare documents for insertion
            documents_to_insert = []
            
            for chunk in document_data["chunks"]:
                # Generate embedding for chunk text
                embedding = self.embedding_model.encode(chunk["text"]).tolist()
                
                # Check if this chunk should have vision embeddings
                # For now, we'll store vision embeddings at document level and reference them
                vision_embedding = None
                if has_images and self.vision_model:
                    # For markdown with images, we can generate vision embeddings
                    # We'll store them separately for each chunk or at document level
                    pass
                
                # Prepare document metadata with citation information
                doc_metadata_entry = {
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
                    "has_images": has_images,
                    "image_count": doc_metadata.get("image_count", 0),
                    "metadata": metadata or {},
                    **chunk.get("metadata", {})
                }
                
                documents_to_insert.append(doc_metadata_entry)
            
            # Insert documents into MongoDB
            result = await self.db[collection_name].insert_many(documents_to_insert)
            
            # If document has images, store image embeddings separately
            if has_images and self.vision_model and images_data:
                await self._store_image_embeddings(document_id, images_data, collection_name)
            
            logger.info(f"Stored document {document_id} with {len(documents_to_insert)} chunks in MongoDB")
            if has_images:
                logger.info(f"Document has {len(images_data)} images with vision embeddings")
            return document_id
            
        except Exception as e:
            logger.error(f"Failed to store document: {e}")
            raise
    
    async def _store_image_embeddings(self, document_id: str, images_data: List[Dict[str, Any]], collection_name: str):
        """Store vision embeddings for images in a separate collection"""
        try:
            image_documents = []
            
            for img_idx, img_data in enumerate(images_data):
                base64_data = img_data.get("base64_data")
                if not base64_data:
                    continue
                
                # Generate vision embedding
                vision_embedding = self._generate_vision_embedding(base64_data)
                if not vision_embedding:
                    continue
                
                image_doc = {
                    "document_id": document_id,
                    "image_index": img_idx,
                    "alt_text": img_data.get("alt_text", ""),
                    "format": img_data.get("format", "unknown"),
                    "width": img_data.get("width"),
                    "height": img_data.get("height"),
                    "size_bytes": img_data.get("size_bytes", 0),
                    "vision_embedding": vision_embedding,
                    "position_in_text": img_data.get("position_in_text"),
                    "base64_data": base64_data,  # Store the actual image data
                    "created_at": datetime.now()
                }
                
                image_documents.append(image_doc)
            
            # Store in separate images collection
            if image_documents:
                result = await self.db[f"{collection_name}_images"].insert_many(image_documents)
                logger.info(f"Stored {len(image_documents)} image embeddings for document {document_id}")
            
        except Exception as e:
            logger.error(f"Failed to store image embeddings: {e}")
    
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
            
            # Extract scores for normalization
            if results:
                scores = [r.get("score", 0.0) for r in results if "score" in r]
                max_score = max(scores) if scores else 1.0
                min_score = min(scores) if scores else 0.0
                score_range = max_score - min_score if max_score != min_score else 1.0
            else:
                max_score = 1.0
                min_score = 0.0
                score_range = 1.0
            
            # Format results with normalized scores (0-1 range)
            formatted_results = []
            for result in results:
                raw_score = result.get("score", 0.0)
                # Normalize score to 0-1 range
                normalized_score = (raw_score - min_score) / score_range if score_range > 0 else 0.0
                
                formatted_results.append({
                    "document_id": result["document_id"],
                    "chunk_index": result["chunk_index"],
                    "text": result["text"],
                    "score": normalized_score,
                    "metadata": {k: v for k, v in result.items() 
                               if k not in ["document_id", "chunk_index", "text", "score", "embedding", "_id"]}
                })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Text search failed: {e}")
            raise
    
    async def search_images(
        self,
        query: str,
        collection_name: str = "documents",
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search for images using CLIP vision embeddings"""
        if not self.vision_model:
            logger.warning("Vision model not available, skipping image search")
            return []
        
        try:
            # Generate query embedding using text encoder (CLIP supports text queries)
            query_embedding = self.vision_model.encode(query).tolist()
            
            # Search in the images collection
            images_collection = f"{collection_name}_images"
            
            # Check if images collection exists
            collections = await self.db.list_collection_names()
            if images_collection not in collections:
                logger.info(f"Images collection {images_collection} does not exist")
                return []
            
            # Prepare aggregation pipeline for image search
            pipeline = []
            
            # Add match stage for filters
            if filters and "document_id" in filters:
                pipeline.append({"$match": {"document_id": filters["document_id"]}})
            
            # Add vector similarity calculation for images
            pipeline.extend([
                {
                    "$addFields": {
                        "similarity_score": {
                            "$divide": [
                                {
                                    "$reduce": {
                                        "input": {"$range": [0, {"$size": "$vision_embedding"}]},
                                        "initialValue": 0,
                                        "in": {
                                            "$add": [
                                                "$$value",
                                                {
                                                    "$multiply": [
                                                        {"$arrayElemAt": ["$vision_embedding", "$$this"]},
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
                                                    "input": "$vision_embedding",
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
                {"$match": {"similarity_score": {"$gte": 0.0}}},
                {"$sort": {"similarity_score": -1}},
                {"$limit": limit}
            ])
            
            # Execute aggregation
            cursor = self.db[images_collection].aggregate(pipeline)
            results = await cursor.to_list(length=limit)
            
            # Format results
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "document_id": result["document_id"],
                    "image_index": result.get("image_index", 0),
                    "alt_text": result.get("alt_text", ""),
                    "format": result.get("format", "unknown"),
                    "width": result.get("width"),
                    "height": result.get("height"),
                    "size_bytes": result.get("size_bytes", 0),
                    "score": result["similarity_score"],
                    "base64_data": result.get("base64_data"),  # Include image data
                    "search_type": "vision",
                    "metadata": {k: v for k, v in result.items() 
                               if k not in ["document_id", "image_index", "similarity_score", "vision_embedding", "_id"]}
                })
                print("*********************")
                print(result["similarity_score"])
                print(result["document_id"])
                print(len(result.get("base64_data")))


           
            
            logger.info(f"Image search found {len(formatted_results)} results")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Image search failed: {e}")
            return []
    
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
    
    async def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()