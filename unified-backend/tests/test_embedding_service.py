"""
Tests for OpenAI Embedding Service with caching
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from app.services.embedding_service import OpenAIEmbeddingService


@pytest.fixture
def mock_db():
    """Mock MongoDB database"""
    db = Mock()
    collection = Mock()
    db.__getitem__ = Mock(return_value=collection)
    collection.create_index = AsyncMock()
    collection.find = Mock(return_value=Mock(to_list=AsyncMock(return_value=[])))
    collection.insert_many = AsyncMock()
    collection.count_documents = AsyncMock(return_value=0)
    return db


@pytest.fixture
def embedding_service():
    """Create embedding service instance"""
    with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
        service = OpenAIEmbeddingService(
            model="text-embedding-3-small",
            cache_ttl_days=30
        )
        return service


@pytest.mark.asyncio
async def test_initialize_cache(embedding_service, mock_db):
    """Test cache initialization"""
    await embedding_service.initialize_cache(mock_db)
    
    assert embedding_service.db == mock_db
    assert embedding_service.cache_collection is not None
    assert mock_db["embedding_cache"].create_index.call_count == 2


@pytest.mark.asyncio
async def test_hash_text(embedding_service):
    """Test text hashing"""
    text1 = "Hello World"
    text2 = "hello world"  # Same when normalized
    text3 = "Different text"
    
    hash1 = embedding_service._hash_text(text1)
    hash2 = embedding_service._hash_text(text2)
    hash3 = embedding_service._hash_text(text3)
    
    assert hash1 == hash2  # Should be same after normalization
    assert hash1 != hash3  # Different text should have different hash
    assert len(hash1) == 64  # SHA256 hex length


@pytest.mark.asyncio
async def test_get_from_cache(embedding_service, mock_db):
    """Test retrieving from cache"""
    await embedding_service.initialize_cache(mock_db)
    
    # Mock cached results
    cached_items = [
        {"hash": "hash1", "embedding": [0.1, 0.2, 0.3]},
        {"hash": "hash2", "embedding": [0.4, 0.5, 0.6]}
    ]
    mock_db["embedding_cache"].find.return_value.to_list = AsyncMock(return_value=cached_items)
    
    result = await embedding_service._get_from_cache(["hash1", "hash2", "hash3"])
    
    assert "hash1" in result
    assert "hash2" in result
    assert result["hash1"] == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_embed_text_with_cache(embedding_service, mock_db):
    """Test embedding text with cache hit"""
    await embedding_service.initialize_cache(mock_db)
    
    # Mock cache hit
    cached_item = {
        "hash": embedding_service._hash_text("test text"),
        "embedding": [0.1] * 1536
    }
    mock_db["embedding_cache"].find.return_value.to_list = AsyncMock(return_value=[cached_item])
    
    result = await embedding_service.embed_text("test text")
    
    assert len(result) == 1536
    assert result == [0.1] * 1536
    # Should not call OpenAI API
    assert not hasattr(embedding_service.client.embeddings, 'create')


@pytest.mark.asyncio
async def test_embed_batch_mixed_cache(embedding_service, mock_db):
    """Test batch embedding with some cached, some not"""
    await embedding_service.initialize_cache(mock_db)
    
    text1 = "cached text"
    text2 = "new text"
    
    hash1 = embedding_service._hash_text(text1)
    cached_item = {"hash": hash1, "embedding": [0.1] * 1536}
    mock_db["embedding_cache"].find.return_value.to_list = AsyncMock(return_value=[cached_item])
    
    # Mock OpenAI API call for uncached text
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[0.2] * 1536)]
    embedding_service.client.embeddings.create = Mock(return_value=mock_response)
    
    results = await embedding_service.embed_batch([text1, text2])
    
    assert len(results) == 2
    assert results[0] == [0.1] * 1536  # From cache
    assert results[1] == [0.2] * 1536  # From API
    # Should save new embedding to cache
    assert mock_db["embedding_cache"].insert_many.called


@pytest.mark.asyncio
async def test_get_cache_stats(embedding_service, mock_db):
    """Test getting cache statistics"""
    await embedding_service.initialize_cache(mock_db)
    
    mock_db["embedding_cache"].count_documents = AsyncMock(return_value=100)
    
    stats = await embedding_service.get_cache_stats()
    
    assert stats["total_cached"] == 100
    assert stats["model"] == "text-embedding-3-small"
    assert stats["vector_size"] == 1536


def test_vector_size_property(embedding_service):
    """Test vector size property"""
    assert embedding_service.vector_size == 1536

