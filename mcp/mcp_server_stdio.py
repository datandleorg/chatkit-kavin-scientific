"""
MCP Server using stdio transport for Kavin Scientific
This server communicates via stdin/stdout and can be used with MCPServerStdio
"""
import asyncio
import os
import sys
import json
import logging
import re
import time
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, List, Optional
from pathlib import Path

import httpx
import boto3
import base64
from bs4 import BeautifulSoup
from urllib.parse import urlencode, quote_plus, urlparse, parse_qs
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
        # Tool(
        #     name="get_document_info",
        #     description="Get information about a specific document by its ID.",
        #     inputSchema={
        #         "type": "object",
        #         "properties": {
        #             "document_id": {
        #                 "type": "string",
        #                 "description": "The unique identifier of the document"
        #             }
        #         },
        #         "required": ["document_id"]
        #     }
        # ),
        # Tool(
        #     name="list_collections",
        #     description="List all available document collections in the RAG service.",
        #     inputSchema={
        #         "type": "object",
        #         "properties": {}
        #     }
        # ),
        Tool(
            name="search_hyma",
            description="Search for products from Hyma Synthesis brand by chemical name. Returns a list of matching products with their catalog numbers (ItemCode). Use get_hyma_product_details to get detailed information for specific products.",
            inputSchema={
                "type": "object",
                "properties": {
                    "chemical_name": {
                        "type": "string",
                        "description": "The chemical name to search for (e.g., 'acetone', 'formic acid')"
                    }
                },
                "required": ["chemical_name"]
            }
        ),
        Tool(
            name="get_hyma_product_details",
            description="Get detailed product information from Hyma Synthesis including stock availability, price, pack size, CAS number, purity, and specifications. Requires the ItemCode (catalog number) from a search_hyma result.",
            inputSchema={
                "type": "object",
                "properties": {
                    "item_code": {
                        "type": "string",
                        "description": "The ItemCode (catalog number) of the product to get details for"
                    }
                },
                "required": ["item_code"]
            }
        ),
        Tool(
            name="search_spectrochem",
            description="Search for products from Spectrochem brand by chemical name. Returns a list of matching products with their product IDs and names. Use get_spectrochem_product_details to get detailed information for specific products.",
            inputSchema={
                "type": "object",
                "properties": {
                    "chemical_name": {
                        "type": "string",
                        "description": "The chemical name to search for (e.g., 'acetone', 'formic acid', 'hydro')"
                    }
                },
                "required": ["chemical_name"]
            }
        ),
        Tool(
            name="get_spectrochem_product_details",
            description="Get detailed product information from Spectrochem including stock availability, price, and specifications. Requires the product_id and product_name from a search_spectrochem result.",
            inputSchema={
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "string",
                        "description": "The product ID (catalog number) of the product to get details for"
                    },
                    "product_name": {
                        "type": "string",
                        "description": "The product name of the product to get details for"
                    }
                },
                "required": ["product_id", "product_name"]
            }
        ),
        Tool(
            name="search_glosil",
            description="Search for products from Glosil Scientific brand by search term. Returns a list of matching products with their product IDs (encoded) and names. Use get_glosil_product_details to get detailed information for specific products.",
            inputSchema={
                "type": "object",
                "properties": {
                    "search_term": {
                        "type": "string",
                        "description": "The search term to search for (e.g., 'thermo', 'anemometer', 'balance')"
                    }
                },
                "required": ["search_term"]
            }
        ),
        Tool(
            name="get_glosil_product_details",
            description="Get detailed product information from Glosil Scientific including stock availability, price, and specifications. Requires the product_id (encoded pid from search_glosil result) and product_url.",
            inputSchema={
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "string",
                        "description": "The product ID (encoded pid, e.g., 'Nw==') from a search_glosil result"
                    },
                    "product_url": {
                        "type": "string",
                        "description": "The product URL (e.g., 'productdesc.php?pid=Nw==') from a search_glosil result"
                    }
                },
                "required": ["product_id", "product_url"]
            }
        ),
        Tool(
            name="search_tci",
            description="Search for products from TCI Chemicals brand by search term. Returns a list of matching products with their product IDs, codes, CAS numbers, and names. Use get_tci_product_details to get detailed information for specific products.",
            inputSchema={
                "type": "object",
                "properties": {
                    "search_term": {
                        "type": "string",
                        "description": "The search term to search for (e.g., 'acetone', 'formic acid', 'sodium')"
                    }
                },
                "required": ["search_term"]
            }
        ),
        Tool(
            name="get_tci_product_details",
            description="Get detailed product information from TCI Chemicals including stock availability, price, pack sizes, and specifications. Requires the product_url from a search_tci result.",
            inputSchema={
                "type": "object",
                "properties": {
                    "product_url": {
                        "type": "string",
                        "description": "The product URL (e.g., '/IN/en/p/A0638') from a search_tci result"
                    }
                },
                "required": ["product_url"]
            }
        )
    ]
    tool_names = [tool.name for tool in tools]
    logger.info(f"Returning {len(tools)} tool(s): {', '.join(tool_names)}")
    return tools

@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls with comprehensive logging"""
    start_time = time.time()
    logger.info("=" * 60)
    logger.info(f"🔧 MCP Tool Call: {name}")
    logger.info(f"📥 Arguments: {json.dumps(arguments, indent=2, ensure_ascii=False)}")
    logger.info("=" * 60)
    
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
                elapsed_time = time.time() - start_time
                logger.info(f"✅ Tool 'generate_quote_for_products' completed successfully in {elapsed_time:.2f}s")
                logger.info("=" * 60)
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
        
        elif name == "search_hyma":
            chemical_name = arguments.get("chemical_name", "").strip()
            
            if not chemical_name:
                logger.warning("search_hyma called without chemical_name")
                return [TextContent(type="text", text="Error: chemical_name is required")]
            
            logger.info(f"Searching Hyma Synthesis for chemical: '{chemical_name}'")
            
            try:
                # Headers for Hyma Synthesis API
                headers = {
                    "accept": "application/json, text/plain, */*",
                    "accept-language": "en-US,en;q=0.9,ta;q=0.8",
                    "origin": "https://www.hymasynthesis.com",
                    "priority": "u=1, i",
                    "referer": "https://www.hymasynthesis.com/",
                    "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": '"Windows"',
                    "sec-fetch-dest": "empty",
                    "sec-fetch-mode": "cors",
                    "sec-fetch-site": "same-site",
                    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
                }
                
                async with httpx.AsyncClient(timeout=30.0) as client:
                    logger.debug(f"Calling Hyma Synthesis search API for: {chemical_name}")
                    search_url = "https://hymasynthesis.com/webservices/api/Values/GetProductsBasedOnChemicalName"
                    search_data = {"ChemicalName": chemical_name}
                    
                    search_response = await client.post(
                        search_url,
                        data=search_data,
                        headers=headers
                    )
                    
                    logger.debug(f"Hyma search API response status: {search_response.status_code}")
                    
                    if search_response.status_code != 200:
                        error_detail = search_response.text
                        logger.error(f"Hyma search API returned error: {search_response.status_code} - {error_detail}")
                        return [TextContent(type="text", text=f"Search failed: {error_detail}")]
                    
                    products = search_response.json()
                    
                    if not products or len(products) == 0:
                        logger.info(f"No products found for chemical: {chemical_name}")
                        return [TextContent(type="text", text=f"No products found for '{chemical_name}' in Hyma Synthesis catalog.")]
                    
                    logger.info(f"Found {len(products)} product(s) for {chemical_name}")
                    
                    # Format search results with basic info
                    # Note: Search API returns CatalogNo (not ItemCode which is null)
                    results = []
                    for idx, product in enumerate(products, 1):
                        catalog_no = product.get("CatalogNo") or product.get("catalogNo") or product.get("Catalog_No")
                        item_name = product.get("ItemName") or product.get("itemName") or product.get("Item_Name", "")
                        cas_number = product.get("CAS") or product.get("cas", "")
                        hsn_code = product.get("HSNCode") or product.get("hsnCode", "")
                        group_name = product.get("GroupName") or product.get("groupName", "")
                        
                        if catalog_no:
                            product_info = f"**Product {idx}**\n"
                            product_info += f"**Item Name:** {item_name}\n"
                            product_info += f"**Catalog Number (ItemCode):** {catalog_no}\n"
                            if cas_number:
                                product_info += f"**CAS Number:** {cas_number}\n"
                            if hsn_code:
                                product_info += f"**HSN Code:** {hsn_code}\n"
                            if group_name:
                                product_info += f"**Group:** {group_name}\n"
                            product_info += f"**Brand:** HYMA\n"
                            results.append(product_info)
                    
                    if not results:
                        return [TextContent(type="text", text=f"Found products for '{chemical_name}' but could not extract Catalog Numbers.")]
                    
                    result_text = f"**Hyma Synthesis Products for '{chemical_name}' (Found {len(results)} products):**\n\n" + "\n".join(results)
                    result_text += "\n\n*Use get_hyma_product_details with the Catalog Number (ItemCode) to get detailed product information including stock, price, and specifications.*"
                    elapsed_time = time.time() - start_time
                    logger.info(f"✅ Tool 'search_hyma' completed successfully in {elapsed_time:.2f}s")
                    logger.info("=" * 60)
                    return [TextContent(type="text", text=result_text)]
                    
            except httpx.TimeoutException:
                logger.error(f"Hyma search request timed out for: {chemical_name}")
                return [TextContent(type="text", text="Search request timed out. Please try again.")]
            except httpx.ConnectError as e:
                logger.error(f"Could not connect to Hyma Synthesis API: {e}")
                return [TextContent(type="text", text=f"Could not connect to Hyma Synthesis API: {str(e)}")]
            except Exception as e:
                logger.error(f"Error during Hyma search: {str(e)}", exc_info=True)
                return [TextContent(type="text", text=f"Error during Hyma search: {str(e)}")]
        
        elif name == "get_hyma_product_details":
            item_code = arguments.get("item_code", "").strip()
            
            if not item_code:
                logger.warning("get_hyma_product_details called without item_code")
                return [TextContent(type="text", text="Error: item_code is required")]
            
            logger.info(f"Getting Hyma Synthesis product details for ItemCode: '{item_code}'")
            
            try:
                # Headers for Hyma Synthesis API
                headers = {
                    "accept": "application/json, text/plain, */*",
                    "accept-language": "en-US,en;q=0.9,ta;q=0.8",
                    "origin": "https://www.hymasynthesis.com",
                    "priority": "u=1, i",
                    "referer": "https://www.hymasynthesis.com/",
                    "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": '"Windows"',
                    "sec-fetch-dest": "empty",
                    "sec-fetch-mode": "cors",
                    "sec-fetch-site": "same-site",
                    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
                }
                
                async with httpx.AsyncClient(timeout=30.0) as client:
                    logger.debug(f"Fetching product details for ItemCode: {item_code}")
                    
                    # Get stock and price info
                    stock_url = "https://hymasynthesis.com/webservices/api/Values/GetWebStockItemMstBasedOnId"
                    stock_response = await client.get(
                        stock_url,
                        params={"ItemCode": item_code},
                        headers=headers
                    )
                    
                    # Get product specification
                    spec_url = "https://hymasynthesis.com/webservices/api/Values/GetProductSpecificationOnCatalogNo"
                    spec_response = await client.get(
                        spec_url,
                        params={"ItemCode": item_code},
                        headers=headers
                    )
                    
                    # Parse responses
                    stock_response_data = stock_response.json() if stock_response.status_code == 200 else {}
                    spec_data = spec_response.json() if spec_response.status_code == 200 else {}
                    
                    if not stock_response_data and not spec_data:
                        logger.warning(f"No product details found for ItemCode: {item_code}")
                        return [TextContent(type="text", text=f"No product details found for ItemCode '{item_code}'.")]
                    
                    # Build product information string
                    product_info = "**Hyma Synthesis Product Details**\n\n"
                    product_info += f"**Brand:** HYMA\n"
                    product_info += f"**Catalog Number (ItemCode):** {item_code}\n\n"
                    
                    # Parse stock data structure: {ProdDet: [...], Item: [...]}
                    if stock_response_data:
                        # Get basic item info from Item array
                        item_info = stock_response_data.get("Item", [])
                        if item_info and len(item_info) > 0:
                            item = item_info[0]
                            product_info += f"**Product Name:** {item.get('ItemName', item.get('itemName', 'N/A'))}\n"
                            product_info += f"**CAS Number:** {item.get('CAS', item.get('cas', 'N/A'))}\n"
                            product_info += f"**Stockable:** {item.get('Stockable', item.get('stockable', 'N/A'))}\n"
                            product_info += f"**Active:** {item.get('Active', item.get('active', 'N/A'))}\n"
                            product_info += "\n"
                        
                        # Get stock and pricing info from ProdDet array (multiple pack sizes)
                        prod_det = stock_response_data.get("ProdDet", [])
                        if prod_det and len(prod_det) > 0:
                            product_info += "**Available Pack Sizes & Pricing:**\n\n"
                            for idx, pack in enumerate(prod_det, 1):
                                pack_size = pack.get("PackSize", pack.get("packSize", ""))
                                price = pack.get("Price", pack.get("price", ""))
                                qty = pack.get("Qty", pack.get("qty", ""))
                                qty_a = pack.get("QtyA", pack.get("qtyA", ""))
                                pack_code = pack.get("PackCode", pack.get("packCode", ""))
                                gst_tax = pack.get("GSTTAX", pack.get("gsttax", ""))
                                
                                product_info += f"**Pack {idx}:**\n"
                                if pack_code:
                                    product_info += f"  - Pack Code: {pack_code}\n"
                                if pack_size:
                                    product_info += f"  - Pack Size: {pack_size}\n"
                                if price:
                                    product_info += f"  - Price: ₹{price}\n"
                                if qty or qty_a:
                                    product_info += f"  - Stock Quantity: {qty if qty else qty_a}\n"
                                if gst_tax:
                                    product_info += f"  - GST: {gst_tax}%\n"
                                product_info += "\n"
                    
                    # Specification info (if available from spec API)
                    if spec_data:
                        # Handle spec_data - it might be an array or object
                        if isinstance(spec_data, list) and len(spec_data) > 0:
                            spec = spec_data[0]
                        elif isinstance(spec_data, dict):
                            spec = spec_data
                        else:
                            spec = {}
                        
                        if spec:
                            product_info += "**Specifications:**\n"
                            if spec.get("CASNo") or spec.get("CAS_No") or spec.get("CASNumber"):
                                product_info += f"  - CAS Number: {spec.get('CASNo') or spec.get('CAS_No') or spec.get('CASNumber', 'N/A')}\n"
                            if spec.get("Purity") or spec.get("purity"):
                                product_info += f"  - Purity: {spec.get('Purity') or spec.get('purity', 'N/A')}\n"
                            if spec.get("MolecularFormula") or spec.get("Molecular_Formula"):
                                product_info += f"  - Molecular Formula: {spec.get('MolecularFormula') or spec.get('Molecular_Formula', 'N/A')}\n"
                            if spec.get("MolecularWeight") or spec.get("Molecular_Weight"):
                                product_info += f"  - Molecular Weight: {spec.get('MolecularWeight') or spec.get('Molecular_Weight', 'N/A')}\n"
                    
                    logger.info(f"Successfully retrieved product details for ItemCode: {item_code}")
                    elapsed_time = time.time() - start_time
                    logger.info(f"✅ Tool 'get_hyma_product_details' completed successfully in {elapsed_time:.2f}s")
                    logger.info("=" * 60)
                    return [TextContent(type="text", text=product_info)]
                    
            except httpx.TimeoutException:
                logger.error(f"Hyma product details request timed out for ItemCode: {item_code}")
                return [TextContent(type="text", text="Request timed out. Please try again.")]
            except httpx.ConnectError as e:
                logger.error(f"Could not connect to Hyma Synthesis API: {e}")
                return [TextContent(type="text", text=f"Could not connect to Hyma Synthesis API: {str(e)}")]
            except Exception as e:
                logger.error(f"Error getting Hyma product details: {str(e)}", exc_info=True)
                return [TextContent(type="text", text=f"Error getting product details: {str(e)}")]
        
        elif name == "search_spectrochem":
            chemical_name = arguments.get("chemical_name", "").strip()
            
            if not chemical_name:
                logger.warning("search_spectrochem called without chemical_name")
                return [TextContent(type="text", text="Error: chemical_name is required")]
            
            logger.info(f"Searching Spectrochem for chemical: '{chemical_name}'")
            
            try:
                # Headers for Spectrochem search
                headers = {
                    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                    "accept-language": "en-US,en;q=0.9,ta;q=0.8",
                    "priority": "u=0, i",
                    "referer": "https://spectrochem.in/",
                    "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": '"Windows"',
                    "sec-fetch-dest": "document",
                    "sec-fetch-mode": "navigate",
                    "sec-fetch-site": "same-origin",
                    "sec-fetch-user": "?1",
                    "upgrade-insecure-requests": "1",
                    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
                    "Cookie": "_ga=GA1.2.459231741.1767172079; _gid=GA1.2.2017523276.1767172079"
                }
                
                async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                    logger.debug(f"Calling Spectrochem search for: {chemical_name}")
                    search_url = f"https://spectrochem.in/?s={quote_plus(chemical_name)}"
                    
                    search_response = await client.get(
                        search_url,
                        headers=headers
                    )
                    
                    logger.debug(f"Spectrochem search response status: {search_response.status_code}")
                    
                    if search_response.status_code != 200:
                        error_detail = search_response.text[:500] if search_response.text else "Unknown error"
                        logger.error(f"Spectrochem search returned error: {search_response.status_code}")
                        return [TextContent(type="text", text=f"Search failed with status {search_response.status_code}")]
                    
                    # Parse HTML response
                    html_content = search_response.text
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
                    products = []
                    seen_products = set()
                    
                    # Find the product results table with id="prod_result"
                    prod_table = soup.find('table', id='prod_result')
                    
                    if prod_table:
                        # Find all stock check links with data-id and data-name attributes
                        stock_check_links = prod_table.find_all('a', class_='stockCheck')
                        
                        for link in stock_check_links:
                            try:
                                product_id = link.get('data-id', '').strip()
                                product_name = link.get('data-name', '').strip()
                                
                                if product_id and product_name:
                                    product_key = (product_id, product_name)
                                    if product_key not in seen_products:
                                        seen_products.add(product_key)
                                        products.append({
                                            "product_id": product_id,
                                            "product_name": product_name
                                        })
                            except Exception as e:
                                logger.debug(f"Error parsing stock check link: {e}")
                                continue
                        
                        # If no stock check links found, try parsing table rows directly
                        if not products:
                            rows = prod_table.find_all('tr')
                            for row in rows:
                                try:
                                    # Skip header row and category rows
                                    if row.find('th') or 'categoryTr' in row.get('class', []):
                                        continue
                                    
                                    # Get all td elements in this row
                                    tds = row.find_all('td')
                                    if len(tds) < 2:
                                        continue
                                    
                                    # Extract Product Code from first column
                                    product_code_td = None
                                    product_name_td = None
                                    
                                    for td in tds:
                                        data_title = td.get('data-title', '')
                                        if data_title == 'Product Code':
                                            product_code_td = td
                                        elif data_title == 'Product Name':
                                            product_name_td = td
                                    
                                    product_id = ""
                                    product_name = ""
                                    
                                    if product_code_td:
                                        product_id = product_code_td.get_text(strip=True)
                                    
                                    if product_name_td:
                                        # Get text and clean up HTML tags like <br/>
                                        product_name = product_name_td.get_text(separator=' ', strip=True)
                                    
                                    if product_id and product_name:
                                        product_key = (product_id, product_name)
                                        if product_key not in seen_products:
                                            seen_products.add(product_key)
                                            products.append({
                                                "product_id": product_id,
                                                "product_name": product_name
                                            })
                                except Exception as e:
                                    logger.debug(f"Error parsing table row: {e}")
                                    continue
                    else:
                        logger.warning("Product results table (id='prod_result') not found in HTML")
                    
                    if not products:
                        logger.info(f"No products found for chemical: {chemical_name}")
                        return [TextContent(type="text", text=f"No products found for '{chemical_name}' in Spectrochem catalog.")]
                    
                    logger.info(f"Found {len(products)} product(s) for {chemical_name}")
                    
                    # Format search results
                    results = []
                    for idx, product in enumerate(products, 1):
                        product_info = f"**Product {idx}**\n"
                        product_info += f"**Product Name:** {product['product_name']}\n"
                        if product['product_id'] and product['product_id'] != "N/A":
                            product_info += f"**Product ID:** {product['product_id']}\n"
                        product_info += f"**Brand:** SPECTROCHEM\n"
                        results.append(product_info)
                    
                    result_text = f"**Spectrochem Products for '{chemical_name}' (Found {len(results)} products):**\n\n" + "\n".join(results)
                    result_text += "\n\n*Use get_spectrochem_product_details with the Product ID and Product Name to get detailed product information including stock and pricing.*"
                    elapsed_time = time.time() - start_time
                    logger.info(f"✅ Tool 'search_spectrochem' completed successfully in {elapsed_time:.2f}s")
                    logger.info("=" * 60)
                    return [TextContent(type="text", text=result_text)]
                    
            except httpx.TimeoutException:
                logger.error(f"Spectrochem search request timed out for: {chemical_name}")
                return [TextContent(type="text", text="Search request timed out. Please try again.")]
            except httpx.ConnectError as e:
                logger.error(f"Could not connect to Spectrochem: {e}")
                return [TextContent(type="text", text=f"Could not connect to Spectrochem: {str(e)}")]
            except Exception as e:
                logger.error(f"Error during Spectrochem search: {str(e)}", exc_info=True)
                return [TextContent(type="text", text=f"Error during Spectrochem search: {str(e)}")]
        
        elif name == "get_spectrochem_product_details":
            product_id = arguments.get("product_id", "").strip()
            product_name = arguments.get("product_name", "").strip()
            
            if not product_id or not product_name:
                logger.warning("get_spectrochem_product_details called without product_id or product_name")
                return [TextContent(type="text", text="Error: product_id and product_name are required")]
            
            logger.info(f"Getting Spectrochem product details for Product ID: '{product_id}', Name: '{product_name}'")
            
            try:
                # Headers for Spectrochem stock API
                headers = {
                    "accept": "*/*",
                    "accept-language": "en-US,en;q=0.9,ta;q=0.8",
                    "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "origin": "https://spectrochem.in",
                    "priority": "u=1, i",
                    "referer": f"https://spectrochem.in/?s={quote_plus(product_name)}",
                    "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": '"Windows"',
                    "sec-fetch-dest": "empty",
                    "sec-fetch-mode": "cors",
                    "sec-fetch-site": "same-origin",
                    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
                    "x-requested-with": "XMLHttpRequest",
                    "Cookie": "_ga=GA1.2.459231741.1767172079; _gid=GA1.2.871069873.1767431678"
                }
                
                async with httpx.AsyncClient(timeout=30.0) as client:
                    logger.debug(f"Fetching product details for Product ID: {product_id}")
                    
                    # Prepare form data
                    form_data = {
                        "action": "load_stock_list",
                        "product_id": product_id,
                        "product_name": product_name
                    }
                    
                    stock_url = "https://spectrochem.in/wp-admin/admin-ajax.php"
                    stock_response = await client.post(
                        stock_url,
                        data=form_data,
                        headers=headers
                    )
                    
                    logger.debug(f"Spectrochem stock API response status: {stock_response.status_code}")
                    
                    if stock_response.status_code != 200:
                        error_detail = stock_response.text[:500] if stock_response.text else "Unknown error"
                        logger.error(f"Spectrochem stock API returned error: {stock_response.status_code}")
                        return [TextContent(type="text", text=f"Failed to get product details: Status {stock_response.status_code}")]
                    
                    # Parse response - it's HTML
                    response_text = stock_response.text
                    
                    # Build product information string
                    product_info = "**Spectrochem Product Details**\n\n"
                    product_info += f"**Brand:** SPECTROCHEM\n"
                    product_info += f"**Product ID:** {product_id}\n"
                    product_info += f"**Product Name:** {product_name}\n\n"
                    
                    # Parse HTML response
                    soup = BeautifulSoup(response_text, 'html.parser')
                    
                    # Remove scripts and styles
                    for script in soup(["script", "style"]):
                        script.decompose()
                    
                    # Try to extract stock/pricing information from HTML
                    data_found = False
                    
                    # Method 1: Look for tables (common for stock/pricing data)
                    tables = soup.find_all('table')
                    if tables:
                        data_found = True
                        product_info += "**Stock/Pricing Information:**\n\n"
                        for table_idx, table in enumerate(tables, 1):
                            if table_idx > 1:
                                product_info += f"\n**Table {table_idx}:**\n"
                            
                            rows = table.find_all('tr')
                            headers = []
                            header_row = rows[0] if rows else None
                            if header_row:
                                headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
                            
                            for row_idx, row in enumerate(rows[1:] if headers else rows, 1):  # Skip header row if present
                                cells = row.find_all(['td', 'th'])
                                if cells:
                                    row_data = []
                                    for cell_idx, cell in enumerate(cells):
                                        cell_text = cell.get_text(strip=True, separator=' ')
                                        if cell_text:
                                            if headers and cell_idx < len(headers):
                                                row_data.append(f"{headers[cell_idx]}: {cell_text}")
                                            else:
                                                row_data.append(cell_text)
                                    if row_data:
                                        product_info += f"  - {' | '.join(row_data)}\n"
                    
                    # Method 2: Look for lists (ul/ol) with stock information
                    if not data_found:
                        lists = soup.find_all(['ul', 'ol'])
                        if lists:
                            data_found = True
                            product_info += "**Stock/Pricing Information:**\n\n"
                            for list_elem in lists:
                                items = list_elem.find_all('li')
                                for item in items:
                                    item_text = item.get_text(strip=True, separator=' ')
                                    if item_text and len(item_text) > 3:
                                        product_info += f"  - {item_text}\n"
                    
                    # Method 3: Look for divs with product information
                    if not data_found:
                        # Try to find divs with classes that suggest product info
                        info_divs = soup.find_all('div', class_=lambda x: x and any(keyword in str(x).lower() for keyword in ['stock', 'price', 'product', 'info', 'detail']))
                        if info_divs:
                            data_found = True
                            product_info += "**Stock/Pricing Information:**\n\n"
                            for div in info_divs:
                                div_text = div.get_text(strip=True, separator='\n')
                                if div_text and len(div_text) > 5:
                                    # Split by lines and format
                                    lines = [line.strip() for line in div_text.split('\n') if line.strip()]
                                    for line in lines[:20]:  # Limit to first 20 lines
                                        product_info += f"  - {line}\n"
                    
                    # Method 4: Extract all meaningful text if structured data not found
                    if not data_found:
                        # Get all text, but try to structure it
                        text_content = soup.get_text(strip=True, separator='\n')
                        if text_content and len(text_content) > 10:
                            # Filter out very short lines and common noise
                            lines = [line.strip() for line in text_content.split('\n') if line.strip() and len(line.strip()) > 3]
                            # Remove duplicate consecutive lines
                            filtered_lines = []
                            prev_line = None
                            for line in lines:
                                if line != prev_line:
                                    filtered_lines.append(line)
                                prev_line = line
                            
                            if filtered_lines:
                                product_info += "**Stock/Pricing Information:**\n\n"
                                for line in filtered_lines[:30]:  # Limit to first 30 meaningful lines
                                    product_info += f"  - {line}\n"
                        else:
                            product_info += "*Stock information not available.*\n"
                    
                    logger.info(f"Successfully retrieved product details for Product ID: {product_id}")
                    elapsed_time = time.time() - start_time
                    logger.info(f"✅ Tool 'get_spectrochem_product_details' completed successfully in {elapsed_time:.2f}s")
                    logger.info("=" * 60)
                    return [TextContent(type="text", text=product_info)]
                    
            except httpx.TimeoutException:
                logger.error(f"Spectrochem product details request timed out for Product ID: {product_id}")
                return [TextContent(type="text", text="Request timed out. Please try again.")]
            except httpx.ConnectError as e:
                logger.error(f"Could not connect to Spectrochem: {e}")
                return [TextContent(type="text", text=f"Could not connect to Spectrochem: {str(e)}")]
            except Exception as e:
                logger.error(f"Error getting Spectrochem product details: {str(e)}", exc_info=True)
                return [TextContent(type="text", text=f"Error getting product details: {str(e)}")]
        
        elif name == "search_glosil":
            search_term = arguments.get("search_term", "").strip()
            
            if not search_term:
                logger.warning("search_glosil called without search_term")
                return [TextContent(type="text", text="Error: search_term is required")]
            
            logger.info(f"Searching Glosil Scientific for: '{search_term}'")
            
            try:
                # Headers for Glosil Scientific search
                headers = {
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                    "Accept-Language": "en-US,en;q=0.9,ta;q=0.8",
                    "Cache-Control": "max-age=0",
                    "Connection": "keep-alive",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": "https://www.glosilscientific.com",
                    "Referer": "https://www.glosilscientific.com/",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "same-origin",
                    "Sec-Fetch-User": "?1",
                    "Upgrade-Insecure-Requests": "1",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
                    "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": '"Windows"'
                }
                
                async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                    logger.debug(f"Calling Glosil Scientific search for: {search_term}")
                    search_url = "https://www.glosilscientific.com/search.php"
                    form_data = {"search": search_term}
                    
                    search_response = await client.post(
                        search_url,
                        data=form_data,
                        headers=headers
                    )
                    
                    logger.debug(f"Glosil search response status: {search_response.status_code}")
                    
                    if search_response.status_code != 200:
                        error_detail = search_response.text[:500] if search_response.text else "Unknown error"
                        logger.error(f"Glosil search returned error: {search_response.status_code}")
                        return [TextContent(type="text", text=f"Search failed with status {search_response.status_code}")]
                    
                    # Parse HTML response
                    html_content = search_response.text
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
                    products = []
                    seen_products = set()
                    
                    # Find product items - they're in divs with class "ltn__product-item"
                    product_items = soup.find_all('div', class_='ltn__product-item')
                    
                    for item in product_items:
                        try:
                            # Find product title link
                            product_link = item.find('a', href=True)
                            if not product_link:
                                continue
                            
                            product_url = product_link.get('href', '')
                            if not product_url or 'productdesc.php' not in product_url:
                                continue
                            
                            # Extract product ID from URL (pid parameter)
                            parsed_url = urlparse(product_url)
                            query_params = parse_qs(parsed_url.query)
                            product_id = query_params.get('pid', [None])[0] if query_params.get('pid') else None
                            
                            if not product_id:
                                continue
                            
                            # Get product name from title
                            product_title_elem = item.find('h2', class_='product-title')
                            if product_title_elem:
                                title_link = product_title_elem.find('a')
                                product_name = title_link.get_text(strip=True) if title_link else product_title_elem.get_text(strip=True)
                            else:
                                product_name = product_link.get_text(strip=True) or product_link.get('title', '')
                            
                            if not product_name:
                                continue
                            
                            # Create product info
                            product_key = (product_id, product_name)
                            if product_key not in seen_products:
                                seen_products.add(product_key)
                                products.append({
                                    "product_id": product_id,
                                    "product_name": product_name,
                                    "product_url": product_url if product_url.startswith('http') else f"https://www.glosilscientific.com/{product_url}"
                                })
                        except Exception as e:
                            logger.debug(f"Error parsing product item: {e}")
                            continue
                    
                    if not products:
                        logger.info(f"No products found for search term: {search_term}")
                        return [TextContent(type="text", text=f"No products found for '{search_term}' in Glosil Scientific catalog.")]
                    
                    logger.info(f"Found {len(products)} product(s) for {search_term}")
                    
                    # Format search results
                    results = []
                    for idx, product in enumerate(products, 1):
                        product_info = f"**Product {idx}**\n"
                        product_info += f"**Product Name:** {product['product_name']}\n"
                        product_info += f"**Product ID:** {product['product_id']}\n"
                        product_info += f"**Brand:** GLOSIL\n"
                        results.append(product_info)
                    
                    result_text = f"**Glosil Scientific Products for '{search_term}' (Found {len(results)} products):**\n\n" + "\n".join(results)
                    result_text += "\n\n*Use get_glosil_product_details with the Product ID and Product URL to get detailed product information including stock and pricing.*"
                    return [TextContent(type="text", text=result_text)]
                    
            except httpx.TimeoutException:
                logger.error(f"Glosil search request timed out for: {search_term}")
                return [TextContent(type="text", text="Search request timed out. Please try again.")]
            except httpx.ConnectError as e:
                logger.error(f"Could not connect to Glosil Scientific: {e}")
                return [TextContent(type="text", text=f"Could not connect to Glosil Scientific: {str(e)}")]
            except Exception as e:
                logger.error(f"Error during Glosil search: {str(e)}", exc_info=True)
                return [TextContent(type="text", text=f"Error during Glosil search: {str(e)}")]
        
        elif name == "get_glosil_product_details":
            product_id = arguments.get("product_id", "").strip()
            product_url = arguments.get("product_url", "").strip()
            
            if not product_id or not product_url:
                logger.warning("get_glosil_product_details called without product_id or product_url")
                return [TextContent(type="text", text="Error: product_id and product_url are required")]
            
            logger.info(f"Getting Glosil Scientific product details for Product ID: '{product_id}'")
            
            try:
                # Headers for Glosil Scientific product details
                headers = {
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9,ta;q=0.8",
                    "Cache-Control": "max-age=0",
                    "Connection": "keep-alive",
                    "Referer": "https://www.glosilscientific.com/search.php",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "same-origin",
                    "Sec-Fetch-User": "?1",
                    "Upgrade-Insecure-Requests": "1",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
                    "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": '"Windows"'
                }
                
                async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                    logger.debug(f"Fetching product details from URL: {product_url}")
                    
                    # Ensure URL is absolute
                    if not product_url.startswith('http'):
                        product_url = f"https://www.glosilscientific.com/{product_url}"
                    
                    detail_response = await client.get(product_url, headers=headers)
                    
                    logger.debug(f"Glosil product details response status: {detail_response.status_code}")
                    
                    if detail_response.status_code != 200:
                        error_detail = detail_response.text[:500] if detail_response.text else "Unknown error"
                        logger.error(f"Glosil product details API returned error: {detail_response.status_code}")
                        return [TextContent(type="text", text=f"Failed to get product details: Status {detail_response.status_code}")]
                    
                    # Parse HTML response
                    response_text = detail_response.text
                    soup = BeautifulSoup(response_text, 'html.parser')
                    
                    # Build product information string
                    product_info = "**Glosil Scientific Product Details**\n\n"
                    product_info += f"**Brand:** GLOSIL\n"
                    product_info += f"**Product ID:** {product_id}\n\n"
                    
                    # Remove scripts and styles
                    for script in soup(["script", "style"]):
                        script.decompose()
                    
                    # Try to extract product information
                    data_found = False
                    
                    # Method 1: Look for product title
                    product_title = soup.find('h1', class_=re.compile(r'product.*title|title', re.I))
                    if not product_title:
                        product_title = soup.find('h1')
                    if product_title:
                        title_text = product_title.get_text(strip=True)
                        if title_text:
                            product_info += f"**Product Name:** {title_text}\n\n"
                            data_found = True
                    
                    # Method 2: Look for price information
                    price_elem = soup.find(class_=re.compile(r'price', re.I))
                    if price_elem:
                        price_text = price_elem.get_text(strip=True)
                        if price_text:
                            product_info += f"**Price:** {price_text}\n\n"
                            data_found = True
                    
                    # Method 3: Look for product description/details
                    desc_elem = soup.find(class_=re.compile(r'description|detail|specification', re.I))
                    if desc_elem:
                        desc_text = desc_elem.get_text(strip=True, separator='\n')
                        if desc_text and len(desc_text) > 10:
                            product_info += "**Description:**\n"
                            lines = [line.strip() for line in desc_text.split('\n') if line.strip() and len(line.strip()) > 3]
                            for line in lines[:20]:  # Limit to first 20 lines
                                product_info += f"  - {line}\n"
                            product_info += "\n"
                            data_found = True
                    
                    # Method 4: Look for tables with product information
                    tables = soup.find_all('table')
                    if tables:
                        data_found = True
                        product_info += "**Product Information:**\n\n"
                        for table_idx, table in enumerate(tables, 1):
                            rows = table.find_all('tr')
                            for row in rows:
                                cells = row.find_all(['td', 'th'])
                                if len(cells) >= 2:
                                    label = cells[0].get_text(strip=True)
                                    value = cells[1].get_text(strip=True)
                                    if label and value:
                                        product_info += f"  - **{label}:** {value}\n"
                    
                    # Method 5: Extract all meaningful text if structured data not found
                    if not data_found:
                        text_content = soup.get_text(strip=True, separator='\n')
                        if text_content and len(text_content) > 10:
                            lines = [line.strip() for line in text_content.split('\n') if line.strip() and len(line.strip()) > 3]
                            if lines:
                                product_info += "**Product Information:**\n\n"
                                for line in lines[:30]:  # Limit to first 30 lines
                                    product_info += f"  - {line}\n"
                    
                    logger.info(f"Successfully retrieved product details for Product ID: {product_id}")
                    elapsed_time = time.time() - start_time
                    logger.info(f"✅ Tool 'get_glosil_product_details' completed successfully in {elapsed_time:.2f}s")
                    logger.info("=" * 60)
                    return [TextContent(type="text", text=product_info)]
                    
            except httpx.TimeoutException:
                elapsed_time = time.time() - start_time
                logger.error(f"Glosil product details request timed out for Product ID: {product_id}")
                logger.info(f"⏱️  Tool 'get_glosil_product_details' timed out after {elapsed_time:.2f}s")
                logger.info("=" * 60)
                return [TextContent(type="text", text="Request timed out. Please try again.")]
            except httpx.ConnectError as e:
                logger.error(f"Could not connect to Glosil Scientific: {e}")
                return [TextContent(type="text", text=f"Could not connect to Glosil Scientific: {str(e)}")]
            except Exception as e:
                logger.error(f"Error getting Glosil product details: {str(e)}", exc_info=True)
                return [TextContent(type="text", text=f"Error getting product details: {str(e)}")]
        
        elif name == "search_tci":
            search_term = arguments.get("search_term", "").strip()
            
            if not search_term:
                logger.warning("search_tci called without search_term")
                return [TextContent(type="text", text="Error: search_term is required")]
            
            logger.info(f"Searching TCI Chemicals for: '{search_term}'")
            
            try:
                # Headers for TCI Chemicals search
                headers = {
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Cache-Control": "max-age=0",
                    "Connection": "keep-alive",
                    "Referer": "https://www.tcichemicals.com/",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "same-origin",
                    "Sec-Fetch-User": "?1",
                    "Upgrade-Insecure-Requests": "1",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
                    "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": '"Windows"'
                }
                
                async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                    logger.debug(f"Calling TCI Chemicals search for: {search_term}")
                    search_url = f"https://www.tcichemicals.com/IN/en/search/?text={quote_plus(search_term)}"
                    
                    search_response = await client.get(search_url, headers=headers)
                    
                    logger.debug(f"TCI search response status: {search_response.status_code}")
                    
                    if search_response.status_code != 200:
                        error_detail = search_response.text[:500] if search_response.text else "Unknown error"
                        logger.error(f"TCI search returned error: {search_response.status_code}")
                        return [TextContent(type="text", text=f"Search failed with status {search_response.status_code}")]
                    
                    # Parse HTML response
                    html_content = search_response.text
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
                    products = []
                    seen_products = set()
                    
                    # Find product items - they're in divs with class "prductlist selectProduct"
                    product_items = soup.find_all('div', class_='prductlist')
                    
                    for item in product_items:
                        try:
                            # Get product ID and code from data attributes
                            product_id = item.get('data-id', '').strip()
                            product_code = item.get('data-product-code1', '').strip() or product_id
                            cas_number = item.get('data-casno', '').strip()
                            
                            if not product_id:
                                continue
                            
                            # Get product name from title link
                            product_title_link = item.find('a', class_='product-title')
                            if product_title_link:
                                product_name = product_title_link.get_text(strip=True)
                                product_url = product_title_link.get('href', '')
                            else:
                                # Fallback: look for any link with title
                                product_link = item.find('a', href=True, title=True)
                                if product_link:
                                    product_name = product_link.get('title', '').strip() or product_link.get_text(strip=True)
                                    product_url = product_link.get('href', '')
                                else:
                                    continue
                            
                            if not product_name or not product_url:
                                continue
                            
                            # Ensure URL is relative (starts with /)
                            if not product_url.startswith('/'):
                                # Try to extract from full URL
                                if 'tcichemicals.com' in product_url:
                                    parsed = urlparse(product_url)
                                    product_url = parsed.path
                            
                            # Create product info
                            product_key = (product_id, product_name)
                            if product_key not in seen_products:
                                seen_products.add(product_key)
                                products.append({
                                    "product_id": product_id,
                                    "product_code": product_code,
                                    "product_name": product_name,
                                    "cas_number": cas_number,
                                    "product_url": product_url
                                })
                        except Exception as e:
                            logger.debug(f"Error parsing product item: {e}")
                            continue
                    
                    if not products:
                        logger.info(f"No products found for search term: {search_term}")
                        return [TextContent(type="text", text=f"No products found for '{search_term}' in TCI Chemicals catalog.")]
                    
                    logger.info(f"Found {len(products)} product(s) for {search_term}")
                    
                    # Format search results
                    results = []
                    for idx, product in enumerate(products, 1):
                        product_info = f"**Product {idx}**\n"
                        product_info += f"**Product Name:** {product['product_name']}\n"
                        product_info += f"**Product Code:** {product['product_code']}\n"
                        if product['cas_number']:
                            product_info += f"**CAS Number:** {product['cas_number']}\n"
                        product_info += f"**Brand:** TCI\n"
                        results.append(product_info)
                    
                    result_text = f"**TCI Chemicals Products for '{search_term}' (Found {len(results)} products):**\n\n" + "\n".join(results)
                    result_text += "\n\n*Use get_tci_product_details with the Product URL to get detailed product information including stock, pricing, and pack sizes.*"
                    elapsed_time = time.time() - start_time
                    logger.info(f"✅ Tool 'search_tci' completed successfully in {elapsed_time:.2f}s")
                    logger.info("=" * 60)
                    return [TextContent(type="text", text=result_text)]
                    
            except httpx.TimeoutException:
                logger.error(f"TCI search request timed out for: {search_term}")
                return [TextContent(type="text", text="Search request timed out. Please try again.")]
            except httpx.ConnectError as e:
                logger.error(f"Could not connect to TCI Chemicals: {e}")
                return [TextContent(type="text", text=f"Could not connect to TCI Chemicals: {str(e)}")]
            except Exception as e:
                logger.error(f"Error during TCI search: {str(e)}", exc_info=True)
                return [TextContent(type="text", text=f"Error during TCI search: {str(e)}")]
        
        elif name == "get_tci_product_details":
            product_url = arguments.get("product_url", "").strip()
            
            if not product_url:
                logger.warning("get_tci_product_details called without product_url")
                return [TextContent(type="text", text="Error: product_url is required")]
            
            logger.info(f"Getting TCI Chemicals product details from URL: '{product_url}'")
            
            try:
                # Headers for TCI Chemicals product details
                headers = {
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Cache-Control": "max-age=0",
                    "Connection": "keep-alive",
                    "Referer": "https://www.tcichemicals.com/IN/en/search/",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "same-origin",
                    "Sec-Fetch-User": "?1",
                    "Upgrade-Insecure-Requests": "1",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
                    "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": '"Windows"'
                }
                
                async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                    # Ensure URL is absolute
                    if not product_url.startswith('http'):
                        if product_url.startswith('/'):
                            product_url = f"https://www.tcichemicals.com{product_url}"
                        else:
                            product_url = f"https://www.tcichemicals.com/IN/en/p/{product_url}"
                    
                    logger.debug(f"Fetching product details from URL: {product_url}")
                    
                    detail_response = await client.get(product_url, headers=headers)
                    
                    logger.debug(f"TCI product details response status: {detail_response.status_code}")
                    
                    if detail_response.status_code != 200:
                        error_detail = detail_response.text[:500] if detail_response.text else "Unknown error"
                        logger.error(f"TCI product details API returned error: {detail_response.status_code}")
                        return [TextContent(type="text", text=f"Failed to get product details: Status {detail_response.status_code}")]
                    
                    # Parse HTML response
                    response_text = detail_response.text
                    soup = BeautifulSoup(response_text, 'html.parser')
                    
                    # Build product information string
                    product_info = "**TCI Chemicals Product Details**\n\n"
                    product_info += f"**Brand:** TCI\n\n"
                    
                    # Remove scripts and styles
                    for script in soup(["script", "style"]):
                        script.decompose()
                    
                    # Extract product information
                    # Product name/title
                    product_title = soup.find('h1') or soup.find(class_=re.compile(r'product.*title|title', re.I))
                    if product_title:
                        title_text = product_title.get_text(strip=True)
                        if title_text:
                            product_info += f"**Product Name:** {title_text}\n\n"
                    
                    # Product code and CAS from search results structure (if available)
                    # Also look for pricing table
                    pricing_table = soup.find('table', id='PricingTable') or soup.find('table', class_=re.compile(r'pricing|table-pricing', re.I))
                    
                    if pricing_table:
                        product_info += "**Pricing & Stock Information:**\n\n"
                        rows = pricing_table.find_all('tr')
                        headers = []
                        header_row = rows[0] if rows else None
                        if header_row:
                            headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
                        
                        for row in rows[1:] if headers else rows:
                            cells = row.find_all(['td', 'th'])
                            if cells:
                                row_data = {}
                                for idx, cell in enumerate(cells):
                                    data_attr = cell.get('data-attr', '')
                                    cell_text = cell.get_text(strip=True)
                                    if data_attr:
                                        row_data[data_attr.replace(':', '').strip()] = cell_text
                                    elif headers and idx < len(headers):
                                        row_data[headers[idx]] = cell_text
                                    else:
                                        row_data[f"Column {idx+1}"] = cell_text
                                
                                if row_data:
                                    for key, value in row_data.items():
                                        if value and value not in ['', 'N/A']:
                                            product_info += f"  - **{key}:** {value}\n"
                                    product_info += "\n"
                    
                    # Look for product specifications/details table
                    spec_tables = soup.find_all('table')
                    for table in spec_tables:
                        if table == pricing_table:
                            continue
                        rows = table.find_all('tr')
                        if rows:
                            product_info += "**Product Specifications:**\n\n"
                            for row in rows:
                                cells = row.find_all(['td', 'th'])
                                if len(cells) >= 2:
                                    label = cells[0].get_text(strip=True)
                                    value = cells[1].get_text(strip=True)
                                    if label and value:
                                        product_info += f"  - **{label}:** {value}\n"
                            product_info += "\n"
                            break
                    
                    # Extract additional text information if available
                    text_content = soup.get_text(strip=True, separator='\n')
                    if text_content and len(text_content) > 10:
                        # Look for important sections
                        lines = [line.strip() for line in text_content.split('\n') if line.strip() and len(line.strip()) > 3]
                        # Filter out common navigation/menu items
                        important_lines = [line for line in lines if not any(skip in line.lower() for skip in ['cookie', 'privacy', 'menu', 'search', 'login', 'cart'])]
                        if important_lines and len(important_lines) > 0:
                            # Only add if we don't have much info yet
                            if len(product_info.split('\n')) < 20:
                                product_info += "**Additional Information:**\n\n"
                                for line in important_lines[:15]:  # Limit to first 15 lines
                                    product_info += f"  - {line}\n"
                    
                    logger.info(f"Successfully retrieved product details from URL: {product_url}")
                    elapsed_time = time.time() - start_time
                    logger.info(f"✅ Tool 'get_tci_product_details' completed successfully in {elapsed_time:.2f}s")
                    logger.info("=" * 60)
                    return [TextContent(type="text", text=product_info)]
                    
            except httpx.TimeoutException:
                logger.error(f"TCI product details request timed out for URL: {product_url}")
                return [TextContent(type="text", text="Request timed out. Please try again.")]
            except httpx.ConnectError as e:
                logger.error(f"Could not connect to TCI Chemicals: {e}")
                return [TextContent(type="text", text=f"Could not connect to TCI Chemicals: {str(e)}")]
            except Exception as e:
                logger.error(f"Error getting TCI product details: {str(e)}", exc_info=True)
                return [TextContent(type="text", text=f"Error getting product details: {str(e)}")]
        
        else:
            logger.warning(f"❌ Unknown tool requested: {name}")
            elapsed_time = time.time() - start_time
            logger.info(f"⏱️  Tool '{name}' completed in {elapsed_time:.2f}s (UNKNOWN TOOL)")
            logger.info("=" * 60)
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"❌ Unexpected error in call_tool for {name}: {str(e)}", exc_info=True)
        logger.info(f"⏱️  Tool '{name}' failed after {elapsed_time:.2f}s")
        logger.info("=" * 60)
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
