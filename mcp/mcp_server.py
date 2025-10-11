import asyncio
import os
from typing import Any, Dict, List

import httpx
import boto3
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.fastmcp import FastMCP

# --- Quote Generator Server Setup ---

# Template file path and output directory
TEMPLATE_PATH = "/Users/saravanan/openai-agentkit-demo/mcp/quote.xlsx"
OUTPUT_DIR = "/Users/saravanan/openai-agentkit-demo/mcp"

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

# Initialize MCP server for quote generation
mcp = FastMCP(
    name="quote-generator",
    instructions="A server that generates Excel quotes for products"
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
        except Exception as upload_error:
            upload_info = f"\n\n❌ UPLOAD FAILED:\n{str(upload_error)}"
        
        total_amt = sum(float(p.get('price', 0)) * (1 - float(p.get('tax', 0)) / 100) * 1 * (1 + 0.18) for p in products)
        return (
            f"Quote generated successfully!\n"
            f"File saved to: {output_path}\n"
            f"Products processed: {len(products)}\n"
            f"Total G.Amt: ${total_amt:.2f}"
            f"{image_info}"
            f"{upload_info}"
        )
    except Exception as e:
        return f"Error generating quote: {str(e)}"

# --- FastAPI App with SSE ---

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the MCP SSE app
sse_app = mcp.sse_app(mount_path="/messages/")
app.mount("/messages/", sse_app)

# Main entry point
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
