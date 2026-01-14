"""
Quote generation tools for Kavin Scientific Agent
"""
import os
import logging
import time
import uuid
import json
from pathlib import Path
from typing import List, Dict, Any

import boto3
from agents import function_tool

logger = logging.getLogger(__name__)

# Configure paths
BASE_DIR = Path(__file__).parent.parent / "mcp"
TEMPLATE_PATH = str(BASE_DIR / "quote.xlsx")
OUTPUT_DIR = str(BASE_DIR)

# DigitalOcean Spaces configuration
DO_ACCESS_KEY = os.getenv("DO_ACCESS_KEY", "DO00DK7ZU22GLQVH767D")
DO_SECRET_KEY = os.getenv("DO_SECRET_KEY", "SPO1OnYRpw5pvBwh9dwSfec6c5eP+LNY1qYkxEY8TPs")
DO_SPACE_NAME = os.getenv("DO_SPACE_NAME", "optimus")
DO_REGION = os.getenv("DO_REGION", "ams3")
DO_ENDPOINT = os.getenv("DO_ENDPOINT", "ams3.digitaloceanspaces.com")


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
        
        # Determine content type based on file extension
        content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        if not file_name.endswith('.xlsx'):
            content_type = 'application/octet-stream'
        
        # Read file content and upload using put_object (better compatibility with DigitalOcean Spaces)
        # Note: DigitalOcean Spaces may not support ACL parameter - if bucket is public, ACL is not needed
        with open(file_path, 'rb') as file_data:
            s3_client.put_object(
                Bucket=DO_SPACE_NAME,
                Key=file_name,
                Body=file_data,
                ContentType=content_type
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
        
        return public_url
    except Exception as e:
        logger.error(f"Failed to upload to DigitalOcean Spaces: {str(e)}", exc_info=True)
        raise Exception(f"Failed to upload to DigitalOcean Spaces: {str(e)}")


@function_tool
def generate_quote_for_products(
    products_json: str,  # JSON string of list of product dicts with: name, cas_number, packing, price, part, hs_code, tax (optional: quantity, discount)
    file_name: str
) -> str:
    """
    Generate a quote in Excel format for a list of products with specified details.
    
    Args:
        products_json: JSON string containing list of product dictionaries with required fields (name, cas_number, packing, price, part, hs_code, tax)
        file_name: Desired filename for the generated Excel quote
    
    Returns:
        Success message with file path and total amount, or error message
    """
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    logger.info("=" * 60)
    logger.info(f"🔧 [RequestID: {request_id}] Tool Call: generate_quote_for_products")
    logger.info(f"📥 [RequestID: {request_id}] Products JSON length: {len(products_json)}, filename: {file_name}")
    logger.info("=" * 60)
    
    try:
        # Parse JSON string to list of dicts
        try:
            products = json.loads(products_json)
        except json.JSONDecodeError as e:
            logger.error(f"[RequestID: {request_id}] Invalid JSON in products_json: {e}")
            return f"Error: Invalid JSON format in products_json: {str(e)}"
        
        # Validate inputs
        if not products:
            logger.warning(f"[RequestID: {request_id}] Quote generation failed: Products list is empty")
            return "Error: Products list cannot be empty"
        if not isinstance(products, list):
            logger.warning(f"[RequestID: {request_id}] Quote generation failed: products_json must be a JSON array")
            return "Error: products_json must be a JSON array"
        if not file_name:
            logger.warning(f"[RequestID: {request_id}] Quote generation failed: File name is empty")
            return "Error: File name cannot be empty"
        
        required_fields = ["name", "cas_number", "packing", "price", "part", "hs_code", "tax"]
        for i, product in enumerate(products):
            missing_fields = [field for field in required_fields if field not in product]
            if missing_fields:
                logger.warning(f"[RequestID: {request_id}] Product {i+1} missing required fields: {missing_fields}")
                return f"Product {i+1} missing required fields: {missing_fields}"
        
        if not os.path.exists(TEMPLATE_PATH):
            logger.error(f"[RequestID: {request_id}] Template file not found: {TEMPLATE_PATH}")
            return f"Template file not found: {TEMPLATE_PATH}"
        
        logger.info(f"[RequestID: {request_id}] Using template: {TEMPLATE_PATH}")
        
        # Import XMLQuoteGenerator (need to add path for it)
        import sys
        mcp_path = str(BASE_DIR)
        if mcp_path not in sys.path:
            sys.path.insert(0, mcp_path)
        
        from xml_quote_generator import XMLQuoteGenerator
        
        generator = XMLQuoteGenerator(TEMPLATE_PATH, OUTPUT_DIR)
        logger.info(f"[RequestID: {request_id}] Generating quote using XMLQuoteGenerator...")
        output_path = generator.generate_quote(products, file_name)
        logger.info(f"[RequestID: {request_id}] Quote generated successfully: {output_path}")
        
        # Upload to DigitalOcean Spaces
        upload_file_name = file_name if file_name.endswith('.xlsx') else file_name + '.xlsx'
        
        try:
            public_url = upload_to_do_spaces(output_path, upload_file_name, delete_after_upload=True)
            upload_info = f"\n\n🌐 FILE UPLOADED TO CLOUD:\nPublic URL: {public_url}\n(Local file deleted after upload)"
        except Exception as upload_error:
            logger.error(f"[RequestID: {request_id}] Upload to DigitalOcean Spaces failed: {upload_error}", exc_info=True)
            upload_info = f"\n\n❌ UPLOAD FAILED:\n{str(upload_error)}\n(Local file kept: {output_path})"
        
        def _to_float(val, default=0.0):
            try:
                return float(val)
            except (TypeError, ValueError):
                return default

        logger.debug(f"[RequestID: {request_id}] Calculating totals for products...")
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
            logger.debug(f"[RequestID: {request_id}] Product {i} ({product.get('name', 'Unknown')}): ${amount + tax_amount:.2f}")
        
        result = (
            f"Quote generated successfully!\n"
            f"File saved to: {output_path}\n"
            f"Products processed: {len(products)}\n"
            f"Total G.Amt: ${total_amt:.2f}"
            f"{upload_info}"
        )
        
        logger.info(f"[RequestID: {request_id}] Quote generation completed successfully. Total amount: ${total_amt:.2f}")
        elapsed_time = time.time() - start_time
        logger.info(f"✅ [RequestID: {request_id}] Tool 'generate_quote_for_products' completed successfully in {elapsed_time:.2f}s")
        logger.info("=" * 60)
        return result
        
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"❌ [RequestID: {request_id}] Error generating quote: {str(e)}", exc_info=True)
        logger.info(f"⏱️  [RequestID: {request_id}] Tool 'generate_quote_for_products' failed after {elapsed_time:.2f}s")
        logger.info("=" * 60)
        return f"Error generating quote: {str(e)}"

