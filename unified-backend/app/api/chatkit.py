"""
ChatKit API endpoints
"""
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, JSONResponse
import logging
import json
import secrets

from app.chatkit.server import KavinScientificServer

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ChatKit"])

# Initialize ChatKit server
server = KavinScientificServer()


@router.post("/v1/chatkit/sessions")
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
        client_secret = f"chatkit_session_{secrets.token_urlsafe(32)}"
        
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
        
        # Extract model from request body
        model = "gpt-5"  # default
        try:
            body_json = json.loads(body)
            
            # ChatKit protocol structure: params.input.inference_options.model
            if isinstance(body_json, dict) and "params" in body_json:
                params = body_json.get("params", {})
                if isinstance(params, dict) and "input" in params:
                    input_data = params.get("input", {})
                    if isinstance(input_data, dict) and "inference_options" in input_data:
                        inference_options = input_data.get("inference_options", {})
                        if isinstance(inference_options, dict) and "model" in inference_options:
                            model = inference_options["model"]
                            logger.info(f"Found model in params.input.inference_options.model: {model}")
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Could not parse request body as JSON or extract model: {e}")
        
        # Fallback to headers if model not found in body
        if model == "gpt-5":
            header_model = request.headers.get("x-model") or request.headers.get("X-Model")
            if header_model:
                model = header_model
                logger.info(f"Using model from header: {model}")
        
        logger.info(f"Final extracted model: {model}")
        
        # Process the request using the chatkit server
        result = await server.process(body, {"request": request, "model": model})

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


@router.post("/chatkit")
async def chatkit_endpoint(request: Request):
    """ChatKit endpoint that processes requests"""
    return await _handle_chatkit_request(request)


@router.post("/support/chatkit")
async def support_chatkit_endpoint(request: Request):
    """Support ChatKit endpoint - proxied from frontend via Vite proxy"""
    logger.info(f"Support ChatKit endpoint called from {request.client.host if request.client else 'unknown'}")
    return await _handle_chatkit_request(request)


@router.get("/support/threads")
async def list_threads():
    """List available threads with basic metadata."""
    try:
        threads = server.list_threads()
        return JSONResponse(content={"threads": threads})
    except Exception as e:
        logger.error(f"Error listing threads: {e}", exc_info=True)
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.post("/support/threads")
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


@router.get("/support/customer")
@router.post("/support/customer")
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

