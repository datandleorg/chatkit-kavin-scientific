"""
MCP Server using stdio transport for Kavin Scientific
This server communicates via stdin/stdout and can be used with MCPServerStdio
"""
import asyncio
import os
import sys
import json
import logging
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, List, Optional
from pathlib import Path

import httpx
import boto3
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Configure logging
# IMPORTANT: stdout is reserved for MCP JSONRPC protocol, all output must go to stderr
# The MCP stdio server uses stdout for JSONRPC messages, so any print() statements will break it
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "mcp_server.log"

handlers = [
    logging.StreamHandler(sys.stderr),  # All logs go to stderr, not stdout
    RotatingFileHandler(LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=5, encoding="utf-8"),
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=handlers,
)
logger = logging.getLogger(__name__)

# Monkey-patch print to use logger instead of stdout
# This ensures any print() statements don't break MCP protocol
_original_print = print
def safe_print(*args, **kwargs):
    """Redirect print() to logger to avoid breaking MCP stdio protocol"""
    message = ' '.join(str(arg) for arg in args)
    logger.info(message)
    if kwargs.get('file') == sys.stderr:
        _original_print(*args, **kwargs)
# Replace built-in print
import builtins
builtins.print = safe_print

# Configure paths - adjust these for your system
BASE_DIR = Path(__file__).parent
TEMPLATE_PATH = str(BASE_DIR / "quote.xlsx")
OUTPUT_DIR = str(BASE_DIR)

# DigitalOcean Spaces configuration
DO_ACCESS_KEY = "DO00DK7ZU22GLQVH767D"
DO_SECRET_KEY = "SPO1OnYRpw5pvBwh9dwSfec6c5eP+LNY1qYkxEY8TPs"
DO_SPACE_NAME = "optimus"
DO_REGION = "ams3"
DO_ENDPOINT = "ams3.digitaloceanspaces.com"

# RAG Service Configuration
RAG_SERVICE_URL = os.getenv("RAG_SERVICE_URL", "http://localhost:8000")

# Initialize MCP server
logger.info("Initializing MCP Server 'quote-generator'...")
server = Server("quote-generator")
logger.info("MCP Server 'quote-generator' initialized successfully")

def upload_to_do_spaces(file_path: str, file_name: str, delete_after_upload: bool = True) -> str:
    """Upload file to DigitalOcean Spaces and return public URL
    
    Args:
        file_path: Local path to the file to upload
        file_name: Name to use for the file in the cloud
        delete_after_upload: If True, delete local file after successful upload
    
    Returns:
        Public URL of the uploaded file
    
    Raises:
        Exception: If upload fails
    """
    try:
        logger.info(f"Uploading file to DigitalOcean Spaces: {file_name}")
        session = boto3.session.Session()
        s3_client = session.client(
            's3',
            region_name=DO_REGION,
            endpoint_url=f'https://{DO_ENDPOINT}',
            aws_access_key_id=DO_ACCESS_KEY,
            aws_secret_access_key=DO_SECRET_KEY
        )
        
        s3_client.upload_file(
            file_path,
            DO_SPACE_NAME,
            file_name,
            ExtraArgs={'ACL': 'public-read'}
        )
        
        public_url = f"https://{DO_SPACE_NAME}.{DO_ENDPOINT}/{file_name}"
        logger.info(f"Successfully uploaded file. Public URL: {public_url}")
        
        # Delete local file after successful upload
        if delete_after_upload and os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"Deleted local file after successful upload: {file_path}")
            except Exception as delete_error:
                logger.warning(f"Failed to delete local file {file_path}: {delete_error}")
                # Don't raise - upload was successful, deletion failure is non-critical
        
        return public_url
    except Exception as e:
        logger.error(f"Failed to upload to DigitalOcean Spaces: {str(e)}", exc_info=True)
        raise Exception(f"Failed to upload to DigitalOcean Spaces: {str(e)}")

@server.list_tools()
async def list_tools() -> List[Tool]:
    """List available tools"""
    logger.info("list_tools() called - preparing tool definitions")
    tools = [
        Tool(
            name="generate_quote_for_products",
            description="Generate a quote in Excel format for a list of products with specified details.",
            inputSchema={
                "type": "object",
                "properties": {
                    "products": {
                        "type": "array",
                        "description": "List of product dictionaries with required fields",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "cas_number": {"type": "string"},
                                "packing": {"type": "string"},
                                "price": {"type": "number"},
                                "part": {"type": "string"},
                                "hs_code": {"type": "string"},
                                "tax": {"type": "number"},
                                "quantity": {"type": "number"},
                                "discount": {"type": "number"},
                            },
                            "required": ["name", "cas_number", "packing", "price", "part", "hs_code", "tax"]
                        }
                    },
                    "file_name": {
                        "type": "string",
                        "description": "Desired filename for the generated Excel quote"
                    }
                },
                "required": ["products", "file_name"]
            }
        ),
        Tool(
            name="file_search",
            description="Search through uploaded documents using the RAG service. Returns formatted text-only results based on the search query.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to find relevant content"
                    },
                    "collection_name": {
                        "type": "string",
                        "description": "Collection to search in (default: documents)",
                        "default": "documents"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 10)",
                        "default": 10
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_document_info",
            description="Get information about a specific document by its ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "document_id": {
                        "type": "string",
                        "description": "The unique identifier of the document"
                    }
                },
                "required": ["document_id"]
            }
        ),
        Tool(
            name="list_collections",
            description="List all available document collections in the RAG service.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]
    tool_names = [tool.name for tool in tools]
    logger.info(f"Returning {len(tools)} tool(s): {', '.join(tool_names)}")
    return tools

@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls"""
    logger.info(f"Tool call received: {name}")
    logger.debug(f"Tool arguments: {json.dumps(arguments, indent=2)}")
    
    try:
        if name == "generate_quote_for_products":
            products = arguments.get("products", [])
            file_name = arguments.get("file_name", "")
            
            logger.info(f"Generating quote for {len(products)} products, filename: {file_name}")
            
            # Validate inputs
            if not products:
                logger.warning("Quote generation failed: Products list is empty")
                return [TextContent(type="text", text="Error: Products list cannot be empty")]
            if not file_name:
                logger.warning("Quote generation failed: File name is empty")
                return [TextContent(type="text", text="Error: File name cannot be empty")]
        
            required_fields = ["name", "cas_number", "packing", "price", "part", "hs_code", "tax"]
            for i, product in enumerate(products):
                missing_fields = [field for field in required_fields if field not in product]
                if missing_fields:
                    logger.warning(f"Product {i+1} missing required fields: {missing_fields}")
                    return [TextContent(type="text", text=f"Product {i+1} missing required fields: {missing_fields}")]
            
            if not os.path.exists(TEMPLATE_PATH):
                logger.error(f"Template file not found: {TEMPLATE_PATH}")
                return [TextContent(type="text", text=f"Template file not found: {TEMPLATE_PATH}")]
            
            logger.info(f"Using template: {TEMPLATE_PATH}")
            try:
                logger.debug("Importing XMLQuoteGenerator...")
                from xml_quote_generator import XMLQuoteGenerator
                generator = XMLQuoteGenerator(TEMPLATE_PATH, OUTPUT_DIR)
                logger.info("Generating quote using XMLQuoteGenerator...")
                output_path = generator.generate_quote(products, file_name)
                logger.info(f"Quote generated successfully: {output_path}")
                
                # Upload to DigitalOcean Spaces
                if not file_name.endswith('.xlsx'):
                    file_name += '.xlsx'
                
                try:
                    # Upload to cloud and delete local file after successful upload
                    public_url = upload_to_do_spaces(output_path, file_name, delete_after_upload=True)
                    upload_info = f"\n\n🌐 FILE UPLOADED TO CLOUD:\nPublic URL: {public_url}\n(Local file deleted after upload)"
                except Exception as upload_error:
                    logger.error(f"Upload to DigitalOcean Spaces failed: {upload_error}", exc_info=True)
                    upload_info = f"\n\n❌ UPLOAD FAILED:\n{str(upload_error)}\n(Local file kept: {output_path})"
                
                def _to_float(val, default=0.0):
                    try:
                        return float(val)
                    except (TypeError, ValueError):
                        return default

                logger.debug("Calculating totals for products...")
                total_amt = 0.0
                for i, product in enumerate(products, 1):
                    price = _to_float(product.get('price'))
                    quantity = _to_float(product.get('quantity', 1), 1.0)
                    discount_pct = _to_float(product.get('discount', 0.0))
                    tax_pct = _to_float(product.get('tax', 0.0))

                    discounted_rate = price * (1 - discount_pct / 100)
                    amount = discounted_rate * quantity
                    tax_amount = amount * (tax_pct / 100)
                    total_amt += amount + tax_amount
                    logger.debug(f"Product {i} ({product.get('name', 'Unknown')}): ${amount + tax_amount:.2f}")
                
                result = (
                    f"Quote generated successfully!\n"
                    f"File saved to: {output_path}\n"
                    f"Products processed: {len(products)}\n"
                    f"Total G.Amt: ${total_amt:.2f}"
                    f"{upload_info}"
                )
                
                logger.info(f"Quote generation completed successfully. Total amount: ${total_amt:.2f}")
                logger.debug(f"Quote result text length: {len(result)} chars")
                return [TextContent(type="text", text=result)]
            except Exception as e:
                logger.error(f"Error generating quote: {str(e)}", exc_info=True)
                return [TextContent(type="text", text=f"Error generating quote: {str(e)}")]
    
        elif name == "file_search":
            query = arguments.get("query", "")
            collection_name = arguments.get("collection_name", "documents")
            limit = arguments.get("limit", 10)
            
            logger.info(f"Searching for query: '{query}' in collection: '{collection_name}' (limit: {limit})")
            
            try:
                search_data = {"query": query, "filters": {}}
                params = {
                    "collection_name": collection_name,
                    "limit": limit,
                    "text_only": True,
                    "llm_format": False,
                    "llm_provider": "openai"
                }
                
                logger.debug(f"Calling RAG service at {RAG_SERVICE_URL}/search")
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        f"{RAG_SERVICE_URL}/search",
                        json=search_data,
                        params=params
                    )
                    
                    logger.debug(f"RAG service response status: {response.status_code}")
                    
                    if response.status_code == 200:
                        result = response.json()
                        content = result.get('formatted_content') or result.get('text_content', '')
                        
                        if content:
                            content_length = len(content)
                            logger.info(f"Search successful. Found content ({content_length} characters)")
                            logger.debug(f"Search content preview: {content[:500]}...")
                            return [TextContent(type="text", text=content)]
                        else:
                            logger.warning(f"No content found for query: '{query}'")
                            return [TextContent(type="text", text=f"No relevant content found for query: '{query}'")]
                    else:
                        error_detail = response.json().get('detail', 'Unknown error') if response.headers.get('content-type', '').startswith('application/json') else response.text
                        logger.error(f"RAG service returned error: {response.status_code} - {error_detail}")
                        return [TextContent(type="text", text=f"Search failed: {error_detail}")]
            except httpx.TimeoutException:
                logger.error(f"Search request timed out after 30 seconds for query: '{query}'")
                return [TextContent(type="text", text="Search request timed out. Please try again.")]
            except httpx.ConnectError as e:
                logger.error(f"Could not connect to RAG service at {RAG_SERVICE_URL}: {e}")
                return [TextContent(type="text", text=f"Could not connect to RAG service at {RAG_SERVICE_URL}. Please ensure the service is running.")]
            except Exception as e:
                logger.error(f"Error during file search: {str(e)}", exc_info=True)
                return [TextContent(type="text", text=f"Error during file search: {str(e)}")]
    
        elif name == "get_document_info":
            document_id = arguments.get("document_id", "")
            
            logger.info(f"Getting document info for ID: {document_id}")
            
            try:
                logger.debug(f"Calling RAG service at {RAG_SERVICE_URL}/documents/{document_id}")
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(f"{RAG_SERVICE_URL}/documents/{document_id}")
                    
                    logger.debug(f"RAG service response status: {response.status_code}")
                    
                    if response.status_code == 200:
                        doc_info = response.json()
                        filename = doc_info.get('filename', 'Unknown')
                        chunks_count = doc_info.get('chunks_count', 0)
                        collection = doc_info.get('collection_name', 'Unknown')
                        logger.info(f"Document info retrieved: {filename} ({chunks_count} chunks in {collection})")
                        
                        result = (
                            f"**Document Information**\n\n"
                            f"**ID:** {document_id}\n"
                            f"**Filename:** {filename}\n"
                            f"**Chunks:** {chunks_count}\n"
                            f"**Collection:** {collection}"
                        )
                        return [TextContent(type="text", text=result)]
                    elif response.status_code == 404:
                        logger.warning(f"Document not found: {document_id}")
                        return [TextContent(type="text", text=f"Document not found: {document_id}")]
                    else:
                        logger.error(f"Error retrieving document info: {response.status_code} - {response.text}")
                        return [TextContent(type="text", text=f"Error retrieving document info: {response.text}")]
            except Exception as e:
                logger.error(f"Error getting document information: {str(e)}", exc_info=True)
                return [TextContent(type="text", text=f"Error getting document information: {str(e)}")]
    
        elif name == "list_collections":
            logger.info("Listing all collections from RAG service")
            
            try:
                logger.debug(f"Calling RAG service at {RAG_SERVICE_URL}/collections")
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(f"{RAG_SERVICE_URL}/collections")
                    
                    logger.debug(f"RAG service response status: {response.status_code}")
                    
                    if response.status_code == 200:
                        collections_data = response.json()
                        collections = collections_data.get('collections', [])
                        
                        logger.info(f"Found {len(collections)} collection(s): {collections}")
                        
                        if collections:
                            result = "**Available Collections:**\n\n" + "\n".join(f"- {col}" for col in collections)
                            return [TextContent(type="text", text=result)]
                        else:
                            logger.warning("No collections found in RAG service")
                            return [TextContent(type="text", text="No collections found. Upload some documents first.")]
                    else:
                        logger.error(f"Error listing collections: {response.status_code} - {response.text}")
                        return [TextContent(type="text", text=f"Error listing collections: {response.text}")]
            except Exception as e:
                logger.error(f"Error listing collections: {str(e)}", exc_info=True)
                return [TextContent(type="text", text=f"Error listing collections: {str(e)}")]
        
        else:
            logger.warning(f"Unknown tool requested: {name}")
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    
    except Exception as e:
        logger.error(f"Unexpected error in call_tool for {name}: {str(e)}", exc_info=True)
        return [TextContent(type="text", text=f"Unexpected error: {str(e)}")]

async def main():
    """Run the stdio server"""
    logger.info("=" * 60)
    logger.info("Starting MCP stdio server for Kavin Scientific")
    logger.info(f"Template path: {TEMPLATE_PATH}")
    logger.info(f"Output directory: {OUTPUT_DIR}")
    logger.info(f"RAG Service URL: {RAG_SERVICE_URL}")
    logger.info("=" * 60)
    
    try:
        logger.info("Initializing stdio server...")
        async with stdio_server() as (read_stream, write_stream):
            logger.info("stdio_server initialized, starting server.run()...")
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options()
            )
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Fatal error in main: {str(e)}", exc_info=True)
        raise
    finally:
        logger.info("MCP stdio server shutdown complete")

if __name__ == "__main__":
    logger.info("MCP stdio server script started")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)
