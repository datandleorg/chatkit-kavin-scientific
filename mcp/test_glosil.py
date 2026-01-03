#!/usr/bin/env python3
"""
Test script for Glosil Scientific search functionality
Tests the search_glosil and get_glosil_product_details tools
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import from mcp_server_stdio
sys.path.insert(0, str(Path(__file__).parent))

import httpx
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs

async def test_search_glosil(search_term: str = "thermo"):
    """Test the search_glosil functionality"""
    print(f"\n{'='*60}")
    print(f"Testing search_glosil for: '{search_term}'")
    print(f"{'='*60}\n")
    
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
            search_url = "https://www.glosilscientific.com/search.php"
            form_data = {"search": search_term}
            
            print(f"Search URL: {search_url}")
            print(f"Form Data: {form_data}\n")
            
            search_response = await client.post(search_url, data=form_data, headers=headers)
            
            print(f"Response Status: {search_response.status_code}\n")
            
            if search_response.status_code != 200:
                print(f"❌ Search failed with status {search_response.status_code}")
                return None
            
            # Parse HTML response
            html_content = search_response.text
            soup = BeautifulSoup(html_content, 'html.parser')
            
            products = []
            seen_products = set()
            
            # Find product items - they're in divs with class "ltn__product-item"
            product_items = soup.find_all('div', class_='ltn__product-item')
            print(f"Found {len(product_items)} product item(s) in HTML\n")
            
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
                        full_url = product_url if product_url.startswith('http') else f"https://www.glosilscientific.com/{product_url}"
                        products.append({
                            "product_id": product_id,
                            "product_name": product_name,
                            "product_url": full_url
                        })
                        
                        print(f"✅ Found product:")
                        print(f"   Product Name: {product_name}")
                        print(f"   Product ID: {product_id}")
                        print(f"   Product URL: {full_url}\n")
                except Exception as e:
                    print(f"⚠️  Error parsing product item: {e}")
                    continue
            
            if not products:
                print(f"❌ No products found for search term: {search_term}")
                # Save HTML for debugging
                with open('glosil_search_debug.html', 'w', encoding='utf-8') as f:
                    f.write(html_content)
                print("💾 Saved HTML response to 'glosil_search_debug.html' for debugging")
                return None
            
            print(f"{'='*60}")
            print(f"✅ Search successful! Found {len(products)} product(s)")
            print(f"{'='*60}\n")
            
            return products
            
    except httpx.TimeoutException:
        print(f"❌ Glosil search request timed out for: {search_term}")
        return None
    except httpx.ConnectError as e:
        print(f"❌ Could not connect to Glosil Scientific: {e}")
        return None
    except Exception as e:
        print(f"❌ Error during Glosil search: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


async def test_get_product_details(product_id: str, product_url: str):
    """Test the get_glosil_product_details functionality"""
    print(f"\n{'='*60}")
    print(f"Testing get_glosil_product_details")
    print(f"Product ID: {product_id}")
    print(f"Product URL: {product_url}")
    print(f"{'='*60}\n")
    
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
            # Ensure URL is absolute
            if not product_url.startswith('http'):
                product_url = f"https://www.glosilscientific.com/{product_url}"
            
            print(f"Fetching product details from URL: {product_url}\n")
            
            detail_response = await client.get(product_url, headers=headers)
            
            print(f"Response Status: {detail_response.status_code}\n")
            
            if detail_response.status_code != 200:
                print(f"❌ Request failed with status {detail_response.status_code}")
                return None
            
            # Parse HTML response
            response_text = detail_response.text
            soup = BeautifulSoup(response_text, 'html.parser')
            
            print("✅ Glosil Scientific Product Details:\n")
            print(f"Brand: GLOSIL")
            print(f"Product ID: {product_id}\n")
            
            # Remove scripts and styles
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Try to extract product information
            data_found = False
            
            # Method 1: Look for product title
            import re
            product_title = soup.find('h1', class_=re.compile(r'product.*title|title', re.I))
            if not product_title:
                product_title = soup.find('h1')
            if product_title:
                title_text = product_title.get_text(strip=True)
                if title_text:
                    print(f"**Product Name:** {title_text}\n")
                    data_found = True
            
            # Method 2: Look for price information
            price_elem = soup.find(class_=re.compile(r'price', re.I))
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                if price_text:
                    print(f"**Price:** {price_text}\n")
                    data_found = True
            
            # Method 3: Look for product description/details
            desc_elem = soup.find(class_=re.compile(r'description|detail|specification', re.I))
            if desc_elem:
                desc_text = desc_elem.get_text(strip=True, separator='\n')
                if desc_text and len(desc_text) > 10:
                    print("**Description:**")
                    lines = [line.strip() for line in desc_text.split('\n') if line.strip() and len(line.strip()) > 3]
                    for line in lines[:20]:  # Limit to first 20 lines
                        print(f"  - {line}")
                    print()
                    data_found = True
            
            # Method 4: Look for tables with product information
            tables = soup.find_all('table')
            if tables:
                data_found = True
                print("**Product Information (from tables):**\n")
                for table_idx, table in enumerate(tables, 1):
                    rows = table.find_all('tr')
                    for row in rows:
                        cells = row.find_all(['td', 'th'])
                        if len(cells) >= 2:
                            label = cells[0].get_text(strip=True)
                            value = cells[1].get_text(strip=True)
                            if label and value:
                                print(f"  - **{label}:** {value}")
            
            # Method 5: Extract all meaningful text if structured data not found
            if not data_found:
                text_content = soup.get_text(strip=True, separator='\n')
                if text_content and len(text_content) > 10:
                    lines = [line.strip() for line in text_content.split('\n') if line.strip() and len(line.strip()) > 3]
                    if lines:
                        print("**Product Information (from text):**\n")
                        for line in lines[:30]:  # Limit to first 30 lines
                            print(f"  - {line}")
                else:
                    print("⚠️  No structured product information found in response")
                    # Save HTML for debugging
                    with open('glosil_product_debug.html', 'w', encoding='utf-8') as f:
                        f.write(response_text)
                    print("💾 Saved HTML response to 'glosil_product_debug.html' for debugging")
            
            print(f"\n{'='*60}")
            print("✅ Product details retrieved successfully")
            print(f"{'='*60}\n")
            
            return True
            
    except httpx.TimeoutException:
        print(f"❌ Glosil product details request timed out for Product ID: {product_id}")
        return None
    except httpx.ConnectError as e:
        print(f"❌ Could not connect to Glosil Scientific: {e}")
        return None
    except Exception as e:
        print(f"❌ Error getting Glosil product details: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """Run tests"""
    print("\n" + "="*60)
    print("GLOSIL SCIENTIFIC API TEST SUITE")
    print("="*60)
    
    # Test 1: Search for products
    search_term = "thermo"
    if len(sys.argv) > 1:
        search_term = sys.argv[1]
    
    products = await test_search_glosil(search_term)
    
    if products and len(products) > 0:
        # Test 2: Get details for the first product
        first_product = products[0]
        await test_get_product_details(
            first_product['product_id'],
            first_product['product_url']
        )
    else:
        print("\n⚠️  Skipping product details test - no products found")
    
    print("\n✅ All tests completed!\n")


if __name__ == "__main__":
    asyncio.run(main())

