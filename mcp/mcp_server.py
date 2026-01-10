import asyncio
import os
import logging
from typing import Any, Dict, List, Optional

import httpx
import boto3
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from mcp.server.fastmcp import FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Quote Generator Server Setup ---

# Template file path and output directory
TEMPLATE_PATH = "/Users/saravanan/kavin/chatkit-kavin-scientific/mcp/quote.xlsx"
OUTPUT_DIR = "/Users/saravanan/kavin/chatkit-kavin-scientific/mcp"

# DigitalOcean Spaces configuration
DO_ACCESS_KEY = "DO00DK7ZU22GLQVH767D"
DO_SECRET_KEY = "SPO1OnYRpw5pvBwh9dwSfec6c5eP+LNY1qYkxEY8TPs"
DO_SPACE_NAME = "optimus"
DO_REGION = "ams3"
DO_ENDPOINT = "ams3.digitaloceanspaces.com"

def upload_to_do_spaces(file_path: str, file_name: str) -> str:
    """
    Upload file to DigitalOcean Spaces and return public URL
    """
    try:
        # Initialize S3 client for DigitalOcean Spaces
        session = boto3.session.Session()
        s3_client = session.client(
            's3',
            region_name=DO_REGION,
            endpoint_url=f'https://{DO_ENDPOINT}',
            aws_access_key_id=DO_ACCESS_KEY,
            aws_secret_access_key=DO_SECRET_KEY
        )
        
        # Upload file to Spaces
        s3_client.upload_file(
            file_path,
            DO_SPACE_NAME,
            file_name,
            ExtraArgs={'ACL': 'public-read'}  # Make file publicly accessible
        )
        
        # Return public URL
        public_url = f"https://{DO_SPACE_NAME}.{DO_ENDPOINT}/{file_name}"
        return public_url
        
    except Exception as e:
        raise Exception(f"Failed to upload to DigitalOcean Spaces: {str(e)}")

# --- RAG Service Configuration ---
RAG_SERVICE_URL = os.getenv("RAG_SERVICE_URL", "http://localhost:8000")

# Initialize MCP server for quote generation and file search
mcp = FastMCP(
    name="quote-generator",
    instructions="A server that generates Excel quotes for products and provides file search capabilities"
)

# Tool: Generate Excel quote for a list of products
@mcp.tool()
async def generate_quote_for_products(
    products: List[Dict[str, Any]],
    file_name: str
) -> str:
    """
    Generate a quote in Excel format for a list of products with specified details.
    Args:
        products: List of product dicts with required fields.
        file_name: Desired filename for the generated Excel quote.
    """

    logger.info("generate_quote_for_products called with %s products and file_name=%s", len(products or []), file_name)
    logger.debug("Products payload: %s", products)

    # Validate inputs
    if not products:
        return "Products list cannot be empty"
    if not file_name:
        return "File name cannot be empty"
    required_fields = ["name", "cas_number", "packing", "price", "part", "hs_code", "tax"]
    for i, product in enumerate(products):
        missing_fields = [field for field in required_fields if field not in product]
        if missing_fields:
            return f"Product {i+1} missing required fields: {missing_fields}"
    # Check if template exists
    import os
    if not os.path.exists(TEMPLATE_PATH):
        return f"Template file not found: {TEMPLATE_PATH}"
    # Generate quote using XML-based method (preserves images AND data)
    try:
        from xml_quote_generator import XMLQuoteGenerator
        generator = XMLQuoteGenerator(TEMPLATE_PATH)
        output_path = generator.generate_quote(products, file_name)
        logger.info("Quote generated at %s", output_path)
        # Check if template has images and confirm preservation
        image_info = ""
        try:
            import zipfile
            with zipfile.ZipFile(TEMPLATE_PATH, 'r') as zip_ref:
                template_images = [f for f in zip_ref.namelist() if f.startswith('xl/media/')]
            with zipfile.ZipFile(output_path, 'r') as zip_ref:
                output_images = [f for f in zip_ref.namelist() if f.startswith('xl/media/')]
            if template_images:
                image_info = f"\n\n✅ IMAGES PRESERVED:\n"
                image_info += f"Template had {len(template_images)} image(s)\n"
                image_info += f"Generated quote has {len(output_images)} image(s)\n"
                if len(template_images) == len(output_images):
                    image_info += f"All images successfully preserved! 🎉"
                else:
                    image_info += f"Some images may be missing"
        except Exception:
            pass
        # Upload to DigitalOcean Spaces
        try:
            # Ensure the uploaded file has .xlsx extension
            if not file_name.endswith('.xlsx'):
                file_name += '.xlsx'
            public_url = upload_to_do_spaces(output_path, file_name)
            upload_info = f"\n\n🌐 FILE UPLOADED TO CLOUD:\nPublic URL: {public_url}"
            logger.info("Quote uploaded to Spaces: %s", public_url)
        except Exception as upload_error:
            upload_info = f"\n\n❌ UPLOAD FAILED:\n{str(upload_error)}"
            logger.exception("Failed to upload quote to Spaces")
        
        def _to_float(val, default=0.0):
            try:
                return float(val)
            except (TypeError, ValueError):
                return default

        total_amt = 0.0
        for product in products:
            price = _to_float(product.get('price'))
            quantity = _to_float(product.get('quantity', 1), 1.0)
            discount_pct = _to_float(product.get('discount', 0.0))
            tax_pct = _to_float(product.get('tax', 0.0))

            discounted_rate = price * (1 - discount_pct / 100)
            amount = discounted_rate * quantity
            tax_amount = amount * (tax_pct / 100)
            total_amt += amount + tax_amount
        return (
            f"Quote generated successfully!\n"
            f"File saved to: {output_path}\n"
            f"Products processed: {len(products)}\n"
            f"Total G.Amt: ${total_amt:.2f}"
            f"{image_info}"
            f"{upload_info}"
        )
    except Exception as e:
        logger.exception("Error generating quote")
        return f"Error generating quote: {str(e)}"

# Tool: Search files using RAG service
@mcp.tool()
async def file_search(
    query: str,
) -> str:
    """
    Search through uploaded documents using the RAG service.
    Returns formatted text-only results based on the search query.
    
    Args:
        query: The search query to find relevant content
        collection_name: Collection to search in (default: "documents")
        limit: Maximum number of results to return (default: 10)
        document_id: Optional specific document ID to search within
    """
    try:
        logger.info("file_search called with query=%s", query)
        # Prepare the search request
        search_data = {
            "query": query,
            "filters": {}
        }
        
        # Determine the endpoint based on whether we're searching a specific document
        # if document_id:
        #     endpoint = f"{RAG_SERVICE_URL}/documents/{document_id}/search"
        # else:
        endpoint = f"{RAG_SERVICE_URL}/api/rag/search"

        text_only = True
        
        # Prepare query parameters
        params = {
            "collection_name": "documents",
            "limit": 10,
            "text_only": text_only,
            "llm_format": False,
            "llm_provider": "openai"
        }
        logger.debug("RAG search params: %s", params)
        # Make the request to RAG service
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                endpoint,
                json=search_data,
                params=params
            )
            logger.info("RAG search response status: %s", response.status_code)
            
            if response.status_code == 200:
                result = response.json()
   
                if text_only:
                    # Return formatted content if available, otherwise text content
                    content = result.get('formatted_content') or result.get('text_content', '')
                    
                    if content:
                        return content
                    else:
                        return f"No relevant content found for query: '{query}'"
                else:
                    # Return structured results as plain text
                    results = result.get('results', [])
                    if results:
                        formatted_results = []
                        for i, res in enumerate(results, 1):
                            text = res.get('formatted_text') or res.get('text', '')
                            score = res.get('score', 0)
                            formatted_results.append(f"Result {i} (Score: {score:.3f}): {text}")
                        
                        return "\n\n".join(formatted_results)
                    else:
                        return f"No results found for query: '{query}'"
                        
            elif response.status_code == 404:
                return f"Document not found: {document_id}" if document_id else "No documents found in collection"
            else:
                error_detail = response.json().get('detail', 'Unknown error') if response.headers.get('content-type', '').startswith('application/json') else response.text
                return f"Search failed: {error_detail}"
                
    except httpx.TimeoutException:
        return "Search request timed out. Please try again."
    except httpx.ConnectError:
        return f"Could not connect to RAG service at {RAG_SERVICE_URL}. Please ensure the service is running."
    except Exception as e:
        return f"Error during file search: {str(e)}"

# Tool: Get document information
@mcp.tool()
async def get_document_info(document_id: str) -> str:
    """
    Get information about a specific document by its ID.
    
    Args:
        document_id: The unique identifier of the document
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{RAG_SERVICE_URL}/api/rag/documents/{document_id}")
            
            if response.status_code == 200:
                doc_info = response.json()
                return f"**Document Information**\n\n**ID:** {document_id}\n**Filename:** {doc_info.get('filename', 'Unknown')}\n**Chunks:** {doc_info.get('chunks_count', 0)}\n**Collection:** {doc_info.get('collection_name', 'Unknown')}"
            elif response.status_code == 404:
                return f"Document not found: {document_id}"
            else:
                return f"Error retrieving document info: {response.text}"
                
    except Exception as e:
        return f"Error getting document information: {str(e)}"

# Tool: List available collections
@mcp.tool()
async def list_collections() -> str:
    """
    List all available document collections in the RAG service.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{RAG_SERVICE_URL}/api/rag/collections")
            
            if response.status_code == 200:
                collections_data = response.json()
                collections = collections_data.get('collections', [])
                
                if collections:
                    return f"**Available Collections:**\n\n" + "\n".join(f"- {col}" for col in collections)
                else:
                    return "No collections found. Upload some documents first."
            else:
                return f"Error listing collections: {response.text}"
                
    except Exception as e:
        return f"Error listing collections: {str(e)}"

# --- FastAPI App with SSE ---

app = FastAPI()

# Add CORS middleware with explicit SSE headers support
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],  # SSE uses GET, but allow POST for other endpoints
    allow_headers=[
        "*",  # Allow all headers
        "Accept",
        "Accept-Encoding",
        "Accept-Language",
        "Cache-Control",
        "Connection",
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "text/event-stream",  # SSE specific
    ],
    expose_headers=[
        "Content-Type",
        "Cache-Control",
        "Connection",
        "X-Accel-Buffering",  # For nginx compatibility
    ],
)

# Mount the MCP SSE app
# Note: SSE endpoint expects GET requests with Accept: text/event-stream header
# Add explicit OPTIONS handler for CORS preflight
@app.options("/messages/")
async def options_messages():
    """Handle CORS preflight for SSE endpoint"""
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Accept, Accept-Encoding, Cache-Control, Connection, Content-Type, Authorization",
            "Access-Control-Expose-Headers": "Content-Type, Cache-Control, Connection",
            "Access-Control-Max-Age": "3600",
        }
    )

# Add middleware to ensure SSE headers are properly set and log requests
@app.middleware("http")
async def add_sse_headers(request: Request, call_next):
    """Add SSE-specific headers to responses and log SSE requests"""
    # Log SSE endpoint requests for debugging
    if "/messages/" in str(request.url.path):
        logger.info(f"SSE Request: {request.method} {request.url.path}")
        logger.info(f"Headers: {dict(request.headers)}")
        logger.info(f"Accept header: {request.headers.get('accept', 'Not set')}")
    
    try:
        response = await call_next(request)
        
        # If this is an SSE endpoint request, ensure proper headers
        if "/messages/" in str(request.url.path):
            # Ensure CORS headers are present
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Accept, Accept-Encoding, Cache-Control, Connection, Content-Type, Authorization"
            
            # SSE-specific headers
            accept_header = request.headers.get("accept", "").lower()
            if "text/event-stream" in accept_header or request.method == "GET":
                response.headers["Content-Type"] = "text/event-stream"
                response.headers["Cache-Control"] = "no-cache"
                response.headers["Connection"] = "keep-alive"
                response.headers["X-Accel-Buffering"] = "no"  # Disable buffering for nginx
        
        return response
    except Exception as e:
        logger.error(f"Error in SSE middleware: {e}", exc_info=True)
        # Return a proper error response
        return Response(
            content=f'{{"error": "SSE request failed: {str(e)}"}}',
            status_code=500,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Content-Type": "application/json"
            }
        )

sse_app = mcp.sse_app(mount_path="/messages/")
app.mount("/messages/", sse_app)

# Add a root endpoint for health checks
@app.get("/")
async def root():
    """Root endpoint for health checks"""
    return {
        "status": "running",
        "service": "MCP Quote Generator Server",
        "endpoints": {
            "sse": "/messages/",
            "docs": "/docs"
        }
    }

# Add health check endpoint
@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "MCP Server"}

# Main entry point
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
