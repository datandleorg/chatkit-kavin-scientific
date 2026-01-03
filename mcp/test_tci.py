#!/usr/bin/env python3
"""
Test script for TCI Chemicals search functionality
Tests the search_tci and get_tci_product_details tools
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import from mcp_server_stdio
sys.path.insert(0, str(Path(__file__).parent))

import httpx
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urlparse
import re

async def test_search_tci(search_term: str = "acetone"):
    """Test the search_tci functionality"""
    print(f"\n{'='*60}")
    print(f"Testing search_tci for: '{search_term}'")
    print(f"{'='*60}\n")
    
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
            search_url = f"https://www.tcichemicals.com/IN/en/search/?text={quote_plus(search_term)}"
            
            print(f"Search URL: {search_url}\n")
            
            search_response = await client.get(search_url, headers=headers)
            
            print(f"Response Status: {search_response.status_code}\n")
            
            if search_response.status_code != 200:
                print(f"❌ Search failed with status {search_response.status_code}")
                return None
            
            # Parse HTML response
            html_content = search_response.text
            soup = BeautifulSoup(html_content, 'html.parser')
            
            products = []
            seen_products = set()
            
            # Find product items - they're in divs with class "prductlist selectProduct"
            product_items = soup.find_all('div', class_='prductlist')
            print(f"Found {len(product_items)} product item(s) in HTML\n")
            
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
                        
                        print(f"✅ Found product:")
                        print(f"   Product Name: {product_name}")
                        print(f"   Product Code: {product_code}")
                        if cas_number:
                            print(f"   CAS Number: {cas_number}")
                        print(f"   Product URL: {product_url}\n")
                except Exception as e:
                    print(f"⚠️  Error parsing product item: {e}")
                    continue
            
            if not products:
                print(f"❌ No products found for search term: {search_term}")
                # Save HTML for debugging
                with open('tci_search_debug.html', 'w', encoding='utf-8') as f:
                    f.write(html_content)
                print("💾 Saved HTML response to 'tci_search_debug.html' for debugging")
                return None
            
            print(f"{'='*60}")
            print(f"✅ Search successful! Found {len(products)} product(s)")
            print(f"{'='*60}\n")
            
            return products
            
    except httpx.TimeoutException:
        print(f"❌ TCI search request timed out for: {search_term}")
        return None
    except httpx.ConnectError as e:
        print(f"❌ Could not connect to TCI Chemicals: {e}")
        return None
    except Exception as e:
        print(f"❌ Error during TCI search: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


async def test_get_product_details(product_url: str):
    """Test the get_tci_product_details functionality"""
    print(f"\n{'='*60}")
    print(f"Testing get_tci_product_details")
    print(f"Product URL: {product_url}")
    print(f"{'='*60}\n")
    
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
            
            print(f"Fetching product details from URL: {product_url}\n")
            
            detail_response = await client.get(product_url, headers=headers)
            
            print(f"Response Status: {detail_response.status_code}\n")
            
            if detail_response.status_code != 200:
                print(f"❌ Request failed with status {detail_response.status_code}")
                return None
            
            # Parse HTML response
            response_text = detail_response.text
            soup = BeautifulSoup(response_text, 'html.parser')
            
            print("✅ TCI Chemicals Product Details:\n")
            print(f"Brand: TCI\n")
            
            # Remove scripts and styles
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Extract product information
            # Product name/title
            product_title = soup.find('h1') or soup.find(class_=re.compile(r'product.*title|title', re.I))
            if product_title:
                title_text = product_title.get_text(strip=True)
                if title_text:
                    print(f"**Product Name:** {title_text}\n")
            
            # Look for pricing table
            pricing_table = soup.find('table', id='PricingTable') or soup.find('table', class_=re.compile(r'pricing|table-pricing', re.I))
            
            if pricing_table:
                print("**Pricing & Stock Information:**\n")
                rows = pricing_table.find_all('tr')
                headers = []
                header_row = rows[0] if rows else None
                if header_row:
                    headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
                    if headers:
                        print(f"Headers: {' | '.join(headers)}\n")
                
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
                                    print(f"  - **{key}:** {value}")
                            print()
            
            # Look for product specifications/details table
            spec_tables = soup.find_all('table')
            for table in spec_tables:
                if table == pricing_table:
                    continue
                rows = table.find_all('tr')
                if rows:
                    print("**Product Specifications:**\n")
                    for row in rows:
                        cells = row.find_all(['td', 'th'])
                        if len(cells) >= 2:
                            label = cells[0].get_text(strip=True)
                            value = cells[1].get_text(strip=True)
                            if label and value:
                                print(f"  - **{label}:** {value}")
                    print()
                    break
            
            print(f"{'='*60}")
            print("✅ Product details retrieved successfully")
            print(f"{'='*60}\n")
            
            return True
            
    except httpx.TimeoutException:
        print(f"❌ TCI product details request timed out for URL: {product_url}")
        return None
    except httpx.ConnectError as e:
        print(f"❌ Could not connect to TCI Chemicals: {e}")
        return None
    except Exception as e:
        print(f"❌ Error getting TCI product details: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """Run tests"""
    print("\n" + "="*60)
    print("TCI CHEMICALS API TEST SUITE")
    print("="*60)
    
    # Test 1: Search for products
    search_term = "acetone"
    if len(sys.argv) > 1:
        search_term = sys.argv[1]
    
    products = await test_search_tci(search_term)
    
    if products and len(products) > 0:
        # Test 2: Get details for the first product
        first_product = products[0]
        await test_get_product_details(first_product['product_url'])
    else:
        print("\n⚠️  Skipping product details test - no products found")
    
    print("\n✅ All tests completed!\n")


if __name__ == "__main__":
    asyncio.run(main())

