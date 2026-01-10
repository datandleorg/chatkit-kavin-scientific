"""
Health check endpoints
"""
from fastapi import APIRouter, HTTPException
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])

# These will be set by main.py
vector_store = None


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        mongodb_status = "unknown"
        if vector_store:
            mongodb_status = await vector_store.health_check()
        
        return {
            "status": "healthy" if mongodb_status == "healthy" else "degraded",
            "mongodb": mongodb_status,
            "service": "unified-backend"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@router.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Unified Backend Service",
        "endpoints": {
            "health": "/health",
            "rag": "/api/rag",
            "chatkit": "/chatkit",
            "support_chatkit": "/support/chatkit",
            "create_session": "/v1/chatkit/sessions",
        },
        "version": "1.0.0"
    }

