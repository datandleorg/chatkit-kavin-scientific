"""
FastAPI application entry point for Kavin Scientific AgentKit Backend
"""
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.chatkit_server import KavinScientificServer
import logging
import os
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Kavin Scientific AgentKit Backend",
    description="ChatKit backend with Agent integration for chemical product quotations",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize ChatKit server
server = KavinScientificServer()

@app.post("/v1/chatkit/sessions")
async def create_chatkit_session(request: Request):
    """Create a ChatKit session - compatible with OpenAI ChatKit API"""
    try:
        body = await request.json()
        logger.info(f"Creating ChatKit session: {json.dumps(body, indent=2)}")
        
        # Extract workflow and user info
        workflow = body.get("workflow", {})
        workflow_id = workflow.get("id") if isinstance(workflow, dict) else None
        user = body.get("user", "default_user")
        chatkit_config = body.get("chatkit_configuration", {})
        
        # Generate a client secret (session token)
        import secrets
        client_secret = f"chatkit_session_{secrets.token_urlsafe(32)}"
        
        # Store session info (in production, use a proper session store)
        # For now, we'll just return the client_secret
        
        logger.info(f"Session created for user: {user}, workflow: {workflow_id}")
        
        return JSONResponse(content={
            "client_secret": client_secret,
            "expires_after": 3600,  # 1 hour
            "session_id": client_secret,
        })
    except Exception as e:
        logger.error(f"Error creating session: {e}", exc_info=True)
        return JSONResponse(
            content={"error": str(e)},
            status_code=500
        )

async def _handle_chatkit_request(request: Request):
    """Internal handler for ChatKit requests - shared by both endpoints"""
    try:
        # Log request details
        logger.info(f"ChatKit request: {request.method} {request.url.path}")
        logger.info(f"Headers: {dict(request.headers)}")
        
        body = await request.body()
        logger.info(f"Received ChatKit request: {len(body)} bytes")
        
        if len(body) == 0:
            logger.warning("Empty request body received")
            return JSONResponse(
                content={"error": "Empty request body"},
                status_code=400
            )
        
        # Process the request using the chatkit server
        result = await server.process(body, {"request": request})

        try:
            from chatkit.server import StreamingResult  # type: ignore
        except Exception:
            StreamingResult = None  # type: ignore

        if StreamingResult and isinstance(result, StreamingResult):
            logger.info("Returning streaming response")
            return StreamingResponse(
                result,
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                    "Access-Control-Allow-Headers": "*",
                },
            )

        if hasattr(result, "json"):
            payload = result.json
            try:
                return JSONResponse(content=json.loads(payload))
            except Exception:
                return JSONResponse(content={"data": payload})

        logger.info("Returning JSON response")
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error processing ChatKit request: {e}", exc_info=True)
        import traceback
        logger.error(traceback.format_exc())
        return JSONResponse(
            content={"error": str(e)},
            status_code=500
        )

@app.post("/chatkit")
async def chatkit_endpoint(request: Request):
    """ChatKit endpoint that processes requests"""
    return await _handle_chatkit_request(request)

@app.post("/support/chatkit")
async def support_chatkit_endpoint(request: Request):
    """Support ChatKit endpoint - proxied from frontend via Vite proxy"""
    logger.info(f"Support ChatKit endpoint called from {request.client.host if request.client else 'unknown'}")
    return await _handle_chatkit_request(request)

@app.get("/support/threads")
async def list_threads():
    """List available threads with basic metadata."""
    try:
        threads = server.list_threads()
        return JSONResponse(content={"threads": threads})
    except Exception as e:
        logger.error(f"Error listing threads: {e}", exc_info=True)
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.post("/support/threads")
async def create_thread(request: Request):
    """Create a new thread and return its metadata."""
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    try:
        title = None
        if isinstance(payload, dict):
            title = payload.get("title")
        thread = await server.create_thread(title=title)
        return JSONResponse(content={"thread": thread})
    except Exception as e:
        logger.error(f"Error creating thread: {e}", exc_info=True)
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/support/customer")
@app.post("/support/customer")
async def support_customer_endpoint(request: Request):
    """Support customer endpoint - for customer context"""
    try:
        thread_id = request.query_params.get("thread_id")
        logger.info(f"Customer context request for thread: {thread_id}")
        if thread_id:
            try:
                await server.ensure_thread(thread_id)  # best-effort ensure
            except Exception as e:
                logger.warning(f"Could not ensure thread {thread_id}: {e}")
        
        # Try to get body if it's a POST request
        try:
            if request.method == "POST":
                body = await request.json()
        except:
            body = {}
        
        # Return customer context (can be extended based on thread_id)
        return JSONResponse(content={
            "thread_id": thread_id,
            "customer": {
                "name": "Guest User",
                "status": "active"
            }
        })
    except Exception as e:
        logger.error(f"Error in customer endpoint: {e}", exc_info=True)
        return JSONResponse(
            content={"error": str(e)},
            status_code=500
        )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "agentkit-backend",
        "agent": "Kavin Scientific Assistant"
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Kavin Scientific AgentKit Backend",
        "endpoints": {
            "health": "/health",
            "chatkit": "/chatkit",
            "support_chatkit": "/support/chatkit",
            "support_threads": "/support/threads",
            "support_customer": "/support/customer",
            "create_session": "/v1/chatkit/sessions",
        },
        "agent": {
            "name": "Kavin Scientific Assistant",
            "model": "gpt-5",
            "mcp_server": "stdio",
            "tools": ["file_search", "generate_quote_for_products", "get_document_info", "list_collections"]
        }
    }

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down AgentKit Backend...")
    if hasattr(server, 'cleanup'):
        await server.cleanup()

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8002))  # Default to 8005 for agentkit-backend
    host = os.getenv("HOST", "0.0.0.0")
    
    logger.info(f"Starting Kavin Scientific AgentKit Backend on {host}:{port}")
    logger.info(f"Frontend should proxy /support to http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)
