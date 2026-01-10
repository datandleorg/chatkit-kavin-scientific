"""
Tests for RAG API endpoints
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch
import io

from app.main import app
from app.services.vector_store import VectorStore
from app.services.hybrid_search import HybridSearch


@pytest.fixture
def mock_services():
    """Mock services"""
    vector_store = Mock(spec=VectorStore)
    vector_store.health_check = AsyncMock(return_value="healthy")
    vector_store.store_document = AsyncMock(return_value="doc-123")
    vector_store.get_document = AsyncMock(return_value=None)
    vector_store.list_collections = AsyncMock(return_value=["documents"])
    vector_store.get_collection_stats = AsyncMock(return_value={"total_chunks": 100})
    vector_store.create_collection = AsyncMock(return_value=True)
    vector_store.delete_collection = AsyncMock()
    vector_store.embedding_service = Mock()
    vector_store.embedding_service.get_cache_stats = AsyncMock(return_value={"total_cached": 50})
    
    hybrid_search = Mock(spec=HybridSearch)
    hybrid_search.search = AsyncMock(return_value=[])
    
    return vector_store, hybrid_search


@pytest.fixture
def client(mock_services):
    """Test client"""
    vector_store, hybrid_search = mock_services
    
    # Set services in app
    from app.api import rag
    rag.vector_store = vector_store
    rag.hybrid_search = hybrid_search
    
    return TestClient(app)


def test_health_check(client):
    """Test health check endpoint"""
    response = client.get("/api/rag/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_list_collections(client):
    """Test listing collections"""
    response = client.get("/api/rag/collections")
    assert response.status_code == 200
    assert "collections" in response.json()


def test_create_collection(client):
    """Test creating a collection"""
    response = client.post("/api/rag/collections?collection_name=test_collection")
    assert response.status_code == 200
    assert response.json()["status"] == "created"


def test_get_collection_stats(client):
    """Test getting collection stats"""
    response = client.get("/api/rag/collections/documents/stats")
    assert response.status_code == 200
    assert "total_chunks" in response.json()


def test_get_cache_stats(client):
    """Test getting cache stats"""
    response = client.get("/api/rag/embedding/cache/stats")
    assert response.status_code == 200
    assert "total_cached" in response.json()


def test_search_documents(client):
    """Test search endpoint"""
    response = client.post(
        "/api/rag/search",
        json={"query": "test query", "filters": {}}
    )
    assert response.status_code == 200
    assert "query" in response.json()


def test_ingest_document(client, mock_services):
    """Test document ingestion"""
    vector_store, _ = mock_services
    
    # Mock document processor
    with patch('app.api.rag.document_processor') as mock_processor:
        mock_processor.process_document = AsyncMock(return_value={
            "filename": "test.pdf",
            "chunks": [
                {"text": "chunk 1", "chunk_index": 0, "start_char": 0, "end_char": 7}
            ],
            "metadata": {}
        })
        
        # Create a test file
        file_content = b"test pdf content"
        files = {"file": ("test.pdf", io.BytesIO(file_content), "application/pdf")}
        
        response = client.post(
            "/api/rag/ingest",
            files=files,
            params={"collection_name": "test_collection"}
        )
        
        assert response.status_code == 200
        assert response.json()["status"] == "success"

