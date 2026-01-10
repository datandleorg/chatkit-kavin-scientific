"""
Tests for Vector Store service
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from app.services.vector_store import VectorStore
from app.services.embedding_service import OpenAIEmbeddingService


@pytest.fixture
def mock_embedding_service():
    """Mock embedding service"""
    service = Mock(spec=OpenAIEmbeddingService)
    service.vector_size = 1536
    service.embed_text = AsyncMock(return_value=[0.1] * 1536)
    service.embed_batch = AsyncMock(return_value=[[0.1] * 1536, [0.2] * 1536])
    service.initialize_cache = AsyncMock()
    return service


@pytest.fixture
def mock_mongo_client():
    """Mock MongoDB client"""
    client = Mock()
    db = Mock()
    client.__getitem__ = Mock(return_value=db)
    
    # Mock collection operations
    collection = Mock()
    db.__getitem__ = Mock(return_value=collection)
    db.list_collection_names = AsyncMock(return_value=[])
    db.command = AsyncMock(return_value={"storageSize": 1000, "totalIndexSize": 100})
    
    collection.create_index = AsyncMock()
    collection.insert_many = AsyncMock(return_value=Mock(inserted_ids=[1, 2]))
    collection.find = Mock(return_value=Mock(
        sort=Mock(return_value=Mock(to_list=AsyncMock(return_value=[]))),
        to_list=AsyncMock(return_value=[])
    ))
    collection.aggregate = Mock(return_value=Mock(to_list=AsyncMock(return_value=[])))
    collection.count_documents = AsyncMock(return_value=0)
    collection.distinct = AsyncMock(return_value=[])
    collection.drop = AsyncMock()
    
    return client, db


@pytest.mark.asyncio
async def test_initialize(mock_embedding_service, mock_mongo_client):
    """Test vector store initialization"""
    client, db = mock_mongo_client
    
    with patch('app.services.vector_store.AsyncIOMotorClient', return_value=client):
        store = VectorStore()
        await store.initialize(embedding_service=mock_embedding_service)
        
        assert store.embedding_service == mock_embedding_service
        assert store.vector_size == 1536
        assert mock_embedding_service.initialize_cache.called


@pytest.mark.asyncio
async def test_store_document(mock_embedding_service, mock_mongo_client):
    """Test storing a document"""
    client, db = mock_mongo_client
    
    with patch('app.services.vector_store.AsyncIOMotorClient', return_value=client):
        store = VectorStore()
        await store.initialize(embedding_service=mock_embedding_service)
        
        document_data = {
            "filename": "test.pdf",
            "chunks": [
                {"text": "chunk 1", "chunk_index": 0, "start_char": 0, "end_char": 7},
                {"text": "chunk 2", "chunk_index": 1, "start_char": 8, "end_char": 15}
            ],
            "metadata": {"file_type": "pdf"}
        }
        
        doc_id = await store.store_document(document_data, "test_collection")
        
        assert doc_id is not None
        assert db["test_collection"].insert_many.called
        assert mock_embedding_service.embed_batch.called


@pytest.mark.asyncio
async def test_search_similar(mock_embedding_service, mock_mongo_client):
    """Test vector similarity search"""
    client, db = mock_mongo_client
    
    with patch('app.services.vector_store.AsyncIOMotorClient', return_value=client):
        store = VectorStore()
        await store.initialize(embedding_service=mock_embedding_service)
        
        results = await store.search_similar("test query", "test_collection", limit=10)
        
        assert isinstance(results, list)
        assert mock_embedding_service.embed_text.called


@pytest.mark.asyncio
async def test_health_check(mock_mongo_client):
    """Test health check"""
    client, db = mock_mongo_client
    client.admin.command = AsyncMock(return_value={"ok": 1})
    
    with patch('app.services.vector_store.AsyncIOMotorClient', return_value=client):
        store = VectorStore()
        store.client = client
        
        status = await store.health_check()
        
        assert status == "healthy"


@pytest.mark.asyncio
async def test_create_collection(mock_embedding_service, mock_mongo_client):
    """Test creating a collection"""
    client, db = mock_mongo_client
    
    with patch('app.services.vector_store.AsyncIOMotorClient', return_value=client):
        store = VectorStore()
        await store.initialize(embedding_service=mock_embedding_service)
        
        result = await store.create_collection("new_collection")
        
        assert result is True
        assert db["new_collection"].create_index.call_count >= 2

