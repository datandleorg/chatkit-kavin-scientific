#!/usr/bin/env python3
"""
Test script for Hyma Synthesis search functionality
Tests the search_hyma and get_hyma_product_details tools
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import from mcp_server_stdio
sys.path.insert(0, str(Path(__file__).parent))

import httpx
import json

async def test_search_hyma(chemical_name: str = "acetone"):
    """Test the search_hyma functionality"""
    print(f"\n{'='*60}")
    print(f"Testing search_hyma for: '{chemical_name}'")
    print(f"{'='*60}\n")
    
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
            search_url = "https://hymasynthesis.com/webservices/api/Values/GetProductsBasedOnChemicalName"
            search_data = {"ChemicalName": chemical_name}
            
            print(f"Search URL: {search_url}")
            print(f"Search Data: {search_data}\n")
            
            search_response = await client.post(
                search_url,
                data=search_data,
                headers=headers
            )
            
            print(f"Response Status: {search_response.status_code}\n")
            
            if search_response.status_code != 200:
                error_detail = search_response.text
                print(f"❌ Hyma search API returned error: {search_response.status_code}")
                print(f"Error detail: {error_detail[:500]}")
                return None
            
            products = search_response.json()
            
            if not products or len(products) == 0:
                print(f"❌ No products found for chemical: {chemical_name}")
                return None
            
            print(f"✅ Found {len(products)} product(s) for {chemical_name}\n")
            
            # Format search results
            results = []
            for idx, product in enumerate(products, 1):
                catalog_no = product.get("CatalogNo") or product.get("catalogNo") or product.get("Catalog_No")
                item_name = product.get("ItemName") or product.get("itemName") or product.get("Item_Name", "")
                cas_number = product.get("CAS") or product.get("cas", "")
                hsn_code = product.get("HSNCode") or product.get("hsnCode", "")
                group_name = product.get("GroupName") or product.get("groupName", "")
                
                if catalog_no:
                    product_info = {
                        "catalog_no": catalog_no,
                        "item_name": item_name,
                        "cas_number": cas_number,
                        "hsn_code": hsn_code,
                        "group_name": group_name
                    }
                    results.append(product_info)
                    
                    print(f"✅ Product {idx}:")
                    print(f"   Item Name: {item_name}")
                    print(f"   Catalog Number (ItemCode): {catalog_no}")
                    if cas_number:
                        print(f"   CAS Number: {cas_number}")
                    if hsn_code:
                        print(f"   HSN Code: {hsn_code}")
                    if group_name:
                        print(f"   Group: {group_name}")
                    print(f"   Brand: HYMA\n")
            
            if not results:
                print(f"❌ Found products but could not extract Catalog Numbers")
                return None
            
            print(f"{'='*60}")
            print(f"✅ Search successful! Found {len(results)} product(s)")
            print(f"{'='*60}\n")
            
            return results
            
    except httpx.TimeoutException:
        print(f"❌ Hyma search request timed out for: {chemical_name}")
        return None
    except httpx.ConnectError as e:
        print(f"❌ Could not connect to Hyma Synthesis API: {e}")
        return None
    except Exception as e:
        print(f"❌ Error during Hyma search: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


async def test_get_hyma_product_details(item_code: str):
    """Test the get_hyma_product_details functionality"""
    print(f"\n{'='*60}")
    print(f"Testing get_hyma_product_details")
    print(f"ItemCode: {item_code}")
    print(f"{'='*60}\n")
    
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
            print(f"Fetching product details for ItemCode: {item_code}\n")
            
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
            
            print(f"Stock API Response Status: {stock_response.status_code}")
            print(f"Spec API Response Status: {spec_response.status_code}\n")
            
            # Parse responses
            stock_response_data = stock_response.json() if stock_response.status_code == 200 else {}
            spec_data = spec_response.json() if spec_response.status_code == 200 else {}
            
            if not stock_response_data and not spec_data:
                print(f"❌ No product details found for ItemCode: {item_code}")
                return None
            
            # Build product information string
            print("✅ Hyma Synthesis Product Details:\n")
            print(f"Brand: HYMA")
            print(f"Catalog Number (ItemCode): {item_code}\n")
            
            # Parse stock data structure: {ProdDet: [...], Item: [...]}
            if stock_response_data:
                # Get basic item info from Item array
                item_info = stock_response_data.get("Item", [])
                if item_info and len(item_info) > 0:
                    item = item_info[0]
                    print("**Basic Product Information:**")
                    print(f"  Product Name: {item.get('ItemName', item.get('itemName', 'N/A'))}")
                    print(f"  CAS Number: {item.get('CAS', item.get('cas', 'N/A'))}")
                    print(f"  Stockable: {item.get('Stockable', item.get('stockable', 'N/A'))}")
                    print(f"  Active: {item.get('Active', item.get('active', 'N/A'))}\n")
                
                # Get stock and pricing info from ProdDet array (multiple pack sizes)
                prod_det = stock_response_data.get("ProdDet", [])
                if prod_det and len(prod_det) > 0:
                    print("**Available Pack Sizes & Pricing:**\n")
                    for idx, pack in enumerate(prod_det, 1):
                        pack_size = pack.get("PackSize", pack.get("packSize", ""))
                        price = pack.get("Price", pack.get("price", ""))
                        qty = pack.get("Qty", pack.get("qty", ""))
                        qty_a = pack.get("QtyA", pack.get("qtyA", ""))
                        pack_code = pack.get("PackCode", pack.get("packCode", ""))
                        gst_tax = pack.get("GSTTAX", pack.get("gsttax", ""))
                        
                        print(f"Pack {idx}:")
                        if pack_code:
                            print(f"  - Pack Code: {pack_code}")
                        if pack_size:
                            print(f"  - Pack Size: {pack_size}")
                        if price:
                            print(f"  - Price: ₹{price}")
                        if qty or qty_a:
                            print(f"  - Stock Quantity: {qty if qty else qty_a}")
                        if gst_tax:
                            print(f"  - GST: {gst_tax}%")
                        print()
            
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
                    print("**Specifications:**")
                    if spec.get("CASNo") or spec.get("CAS_No") or spec.get("CASNumber"):
                        cas_no = spec.get('CASNo') or spec.get('CAS_No') or spec.get('CASNumber', 'N/A')
                        print(f"  - CAS Number: {cas_no}")
                    if spec.get("Purity") or spec.get("purity"):
                        purity = spec.get('Purity') or spec.get('purity', 'N/A')
                        print(f"  - Purity: {purity}")
                    if spec.get("MolecularFormula") or spec.get("Molecular_Formula"):
                        mol_formula = spec.get('MolecularFormula') or spec.get('Molecular_Formula', 'N/A')
                        print(f"  - Molecular Formula: {mol_formula}")
                    if spec.get("MolecularWeight") or spec.get("Molecular_Weight"):
                        mol_weight = spec.get('MolecularWeight') or spec.get('Molecular_Weight', 'N/A')
                        print(f"  - Molecular Weight: {mol_weight}")
            
            print(f"\n{'='*60}")
            print("✅ Product details retrieved successfully")
            print(f"{'='*60}\n")
            
            return True
            
    except httpx.TimeoutException:
        print(f"❌ Hyma product details request timed out for ItemCode: {item_code}")
        return None
    except httpx.ConnectError as e:
        print(f"❌ Could not connect to Hyma Synthesis API: {e}")
        return None
    except Exception as e:
        print(f"❌ Error getting Hyma product details: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """Run tests"""
    print("\n" + "="*60)
    print("HYMA SYNTHESIS API TEST SUITE")
    print("="*60)
    
    # Test 1: Search for products
    chemical_name = "acetone"
    if len(sys.argv) > 1:
        chemical_name = sys.argv[1]
    
    products = await test_search_hyma(chemical_name)
    
    if products and len(products) > 0:
        # Test 2: Get details for the first product
        first_product = products[0]
        item_code = first_product.get('catalog_no')
        if item_code:
            await test_get_hyma_product_details(item_code)
        else:
            print("\n⚠️  Skipping product details test - no ItemCode found")
    else:
        print("\n⚠️  Skipping product details test - no products found")
    
    print("\n✅ All tests completed!\n")


if __name__ == "__main__":
    # Simple logger for debug messages
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    asyncio.run(main())

