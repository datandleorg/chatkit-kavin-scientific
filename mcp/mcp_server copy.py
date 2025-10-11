#!/usr/bin/env python3
"""
MCP Server for Product Quote Generation
Generates Excel quotes using a template file for a list of products.
"""

import asyncio
import json
import logging
import os
import shutil
import sys
from typing import Any, Dict, List
from datetime import datetime

import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter
import xlsxwriter
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import Response

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize MCP server
server = Server("quote-generator")

# Template file path
TEMPLATE_PATH = "/Users/saravanan/openai-agentkit-demo/mcp/quote.xlsx"
OUTPUT_DIR = "/Users/saravanan/openai-agentkit-demo/mcp"

# The old openpyxl-based approach has been replaced by XML-based generator
# No post-processing needed - XMLQuoteGenerator handles everything
    

@server.list_tools()
async def list_tools() -> List[Tool]:
    """List available tools."""
    return [
        Tool(
            name="generate_quote_for_products",
            description="Generate a quote in Excel format for a list of products with specified details",
            inputSchema={
                "type": "object",
                "properties": {
                    "products": {
                        "type": "array",
                        "description": "List of products to quote, each with relevant details",
                        "items": {
                            "type": "object",
                            "required": [
                                "name",
                                "cas_number",
                                "packing",
                                "price",
                                "part",
                                "hs_code",
                                "tax"
                            ],
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "description": "Product name"
                                },
                                "cas_number": {
                                    "type": "string",
                                    "description": "CAS (Chemical Abstracts Service) number for the product"
                                },
                                "packing": {
                                    "type": "string",
                                    "description": "Product packing information, such as packaging type or size"
                                },
                                "price": {
                                    "type": "number",
                                    "description": "Product price"
                                },
                                "part": {
                                    "type": "string",
                                    "description": "Product part number or identifier"
                                },
                                "hs_code": {
                                    "type": "string",
                                    "description": "Harmonized System Code for product classification"
                                },
                                "tax": {
                                    "type": "number",
                                    "description": "Applicable tax rate or amount for the product"
                                }
                            },
                            "additionalProperties": False
                        }
                    },
                    "file_name": {
                        "type": "string",
                        "description": "Desired filename for the generated Excel quote"
                    }
                },
                "required": [
                    "products",
                    "file_name"
                ],
                "additionalProperties": False
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls."""
    if name == "generate_quote_for_products":
        try:
            products = arguments.get("products", [])
            file_name = arguments.get("file_name", "")
            
            # Validate inputs
            if not products:
                raise ValueError("Products list cannot be empty")
            
            if not file_name:
                raise ValueError("File name cannot be empty")
            
            # Validate product structure
            for i, product in enumerate(products):
                required_fields = ["name", "cas_number", "packing", "price", "part", "hs_code", "tax"]
                missing_fields = [field for field in required_fields if field not in product]
                if missing_fields:
                    raise ValueError(f"Product {i+1} missing required fields: {missing_fields}")
            
            # Check if template exists
            if not os.path.exists(TEMPLATE_PATH):
                raise FileNotFoundError(f"Template file not found: {TEMPLATE_PATH}")
            
            # Generate quote using XML-based method (preserves images AND data)
            from xml_quote_generator import XMLQuoteGenerator
            generator = XMLQuoteGenerator(TEMPLATE_PATH)
            output_path = generator.generate_quote(products, file_name)
            
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
            except:
                pass
            
            return [
                TextContent(
                    type="text",
                    text=f"Quote generated successfully!\n"
                         f"File saved to: {output_path}\n"
                         f"Products processed: {len(products)}\n"
                         f"Total G.Amt: ${sum(float(p.get('price', 0)) * (1 - float(p.get('tax', 0)) / 100) * 1 * (1 + 0.18) for p in products):.2f}"
                         f"{image_info}"
                )
            ]
            
        except Exception as e:
            logger.error(f"Error in generate_quote_for_products: {str(e)}")
            return [
                TextContent(
                    type="text",
                    text=f"Error generating quote: {str(e)}"
                )
            ]
    
    else:
        raise ValueError(f"Unknown tool: {name}")

async def main_stdio():
    """Run MCP server in stdio mode (for local use)."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

async def handle_sse(request):
    """Handle SSE connections for HTTP mode."""
    async with SseServerTransport("/messages") as transport:
        await server.run(
            transport.read_stream,
            transport.write_stream,
            server.create_initialization_options()
        )
    return Response()

async def handle_messages(request):
    """Handle message endpoint for HTTP mode."""
    return Response()

def create_sse_app():
    """Create Starlette app for HTTP mode."""
    from starlette.requests import Request
    
    # Create SSE transport
    transport = SseServerTransport("/messages")
    
    async def handle_sse_endpoint(request: Request):
        """Handle SSE endpoint for streaming events."""
        try:
            # Use the transport's SSE connection method
            async with transport.connect_sse(request.scope, request.receive, request._send) as (read_stream, write_stream):
                # Run the MCP server with the streams
                await server.run(
                    read_stream,
                    write_stream,
                    server.create_initialization_options()
                )
        except Exception as e:
            logger.error(f"Error in SSE endpoint: {e}")
            import traceback
            traceback.print_exc()
            return Response(f"SSE connection failed: {str(e)}", status_code=500)
    
    async def handle_messages_endpoint(request: Request):
        """Handle POST messages endpoint."""
        try:
            # Handle the POST message through the transport
            response = await transport.handle_post_message(
                request.scope,
                request.receive,
                request._send
            )
            return response
        except Exception as e:
            logger.error(f"Error in messages endpoint: {e}")
            import traceback
            traceback.print_exc()
            return Response(f"Message handling failed: {str(e)}", status_code=500)
    
    app = Starlette(
        debug=True,
        routes=[
            Route("/sse", endpoint=handle_sse_endpoint),
            Route("/messages", endpoint=handle_messages_endpoint, methods=["POST"]),
        ]
    )
    
    return app

# Create the FastAPI app for uvicorn
app = create_sse_app()

def main():
    """Main entry point - supports both stdio and HTTP modes."""
    import argparse
    
    parser = argparse.ArgumentParser(description='MCP Quote Generator Server')
    parser.add_argument('--http', action='store_true', help='Run in HTTP mode (default: stdio)')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (HTTP mode only)')
    parser.add_argument('--port', type=int, default=8000, help='Port to bind to (HTTP mode only)')
    
    args = parser.parse_args()
    
    if args.http:
        # Run in HTTP mode
        import uvicorn
        logger.info(f"Starting MCP server in HTTP mode on {args.host}:{args.port}")
        logger.info(f"Connect via: http://{args.host}:{args.port}/sse")
        
        uvicorn.run(app, host=args.host, port=args.port)
    else:
        # Run in stdio mode
        logger.info("Starting MCP server in stdio mode")
        asyncio.run(main_stdio())

if __name__ == "__main__":
    main()
