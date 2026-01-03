#!/usr/bin/env python3
"""
Test script for Spectrochem search functionality
Tests the search_spectrochem and get_spectrochem_product_details tools
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import from mcp_server_stdio
sys.path.insert(0, str(Path(__file__).parent))

import httpx
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

async def test_search_spectrochem(chemical_name: str = "hydro"):
    """Test the search_spectrochem functionality"""
    print(f"\n{'='*60}")
    print(f"Testing search_spectrochem for: '{chemical_name}'")
    print(f"{'='*60}\n")
    
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
            search_url = f"https://spectrochem.in/?s={quote_plus(chemical_name)}"
            print(f"Search URL: {search_url}")
            
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
            
            # Find the product results table with id="prod_result"
            prod_table = soup.find('table', id='prod_result')
            
            if prod_table:
                print("✅ Found product results table (id='prod_result')")
                
                # Find all stock check links with data-id and data-name attributes
                stock_check_links = prod_table.find_all('a', class_='stockCheck')
                print(f"Found {len(stock_check_links)} stock check links\n")
                
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
                                print(f"✅ Found product:")
                                print(f"   Product ID: {product_id}")
                                print(f"   Product Name: {product_name}\n")
                    except Exception as e:
                        print(f"⚠️  Error parsing stock check link: {e}")
                        continue
                
                # If no stock check links found, try parsing table rows directly
                if not products:
                    print("⚠️  No stock check links found, trying to parse table rows directly...\n")
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
                                    print(f"✅ Found product (from table row):")
                                    print(f"   Product ID: {product_id}")
                                    print(f"   Product Name: {product_name}\n")
                        except Exception as e:
                            continue
            else:
                print("❌ Product results table (id='prod_result') not found in HTML")
                # Save HTML for debugging
                with open('spectrochem_search_debug.html', 'w', encoding='utf-8') as f:
                    f.write(html_content)
                print("💾 Saved HTML response to 'spectrochem_search_debug.html' for debugging")
                return None
            
            if not products:
                print(f"❌ No products found for '{chemical_name}'")
                return None
            
            print(f"\n{'='*60}")
            print(f"✅ Search successful! Found {len(products)} product(s)")
            print(f"{'='*60}\n")
            
            return products
            
    except Exception as e:
        print(f"❌ Error during search: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


async def test_get_product_details(product_id: str, product_name: str):
    """Test the get_spectrochem_product_details functionality"""
    print(f"\n{'='*60}")
    print(f"Testing get_spectrochem_product_details")
    print(f"Product ID: {product_id}")
    print(f"Product Name: {product_name}")
    print(f"{'='*60}\n")
    
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
            # Prepare form data
            form_data = {
                "action": "load_stock_list",
                "product_id": product_id,
                "product_name": product_name
            }
            
            stock_url = "https://spectrochem.in/wp-admin/admin-ajax.php"
            print(f"Stock URL: {stock_url}")
            print(f"Form Data: {form_data}\n")
            
            stock_response = await client.post(stock_url, data=form_data, headers=headers)
            print(f"Response Status: {stock_response.status_code}\n")
            
            if stock_response.status_code != 200:
                print(f"❌ Request failed with status {stock_response.status_code}")
                return None
            
            # Parse HTML response
            response_text = stock_response.text
            soup = BeautifulSoup(response_text, 'html.parser')
            
            # Remove scripts and styles
            for script in soup(["script", "style"]):
                script.decompose()
            
            print("✅ Product Details Response:\n")
            print("Brand: SPECTROCHEM")
            print(f"Product ID: {product_id}")
            print(f"Product Name: {product_name}\n")
            
            # Try to extract stock/pricing information from HTML
            data_found = False
            
            # Method 1: Look for tables (common for stock/pricing data)
            tables = soup.find_all('table')
            if tables:
                data_found = True
                print("**Stock/Pricing Information (from tables):**\n")
                for table_idx, table in enumerate(tables, 1):
                    if table_idx > 1:
                        print(f"\n**Table {table_idx}:**\n")
                    
                    rows = table.find_all('tr')
                    headers = []
                    header_row = rows[0] if rows else None
                    if header_row:
                        headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
                        if headers:
                            print(f"Headers: {' | '.join(headers)}\n")
                    
                    for row_idx, row in enumerate(rows[1:] if headers else rows, 1):
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
                                print(f"  - {' | '.join(row_data)}")
            
            # Method 2: Look for lists (ul/ol) with stock information
            if not data_found:
                lists = soup.find_all(['ul', 'ol'])
                if lists:
                    data_found = True
                    print("**Stock/Pricing Information (from lists):**\n")
                    for list_elem in lists:
                        items = list_elem.find_all('li')
                        for item in items:
                            item_text = item.get_text(strip=True, separator=' ')
                            if item_text and len(item_text) > 3:
                                print(f"  - {item_text}")
            
            # Method 3: Extract all meaningful text if structured data not found
            if not data_found:
                text_content = soup.get_text(strip=True, separator='\n')
                if text_content and len(text_content) > 10:
                    lines = [line.strip() for line in text_content.split('\n') if line.strip() and len(line.strip()) > 3]
                    if lines:
                        print("**Stock/Pricing Information (from text):**\n")
                        for line in lines[:30]:  # Limit to first 30 lines
                            print(f"  - {line}")
                else:
                    print("⚠️  No structured stock/pricing information found in response")
                    # Save HTML for debugging
                    with open('spectrochem_stock_debug.html', 'w', encoding='utf-8') as f:
                        f.write(response_text)
                    print("💾 Saved HTML response to 'spectrochem_stock_debug.html' for debugging")
            
            print(f"\n{'='*60}")
            print("✅ Product details retrieved successfully")
            print(f"{'='*60}\n")
            
            return True
            
    except Exception as e:
        print(f"❌ Error getting product details: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """Run tests"""
    print("\n" + "="*60)
    print("SPECTROCHEM API TEST SUITE")
    print("="*60)
    
    # Test 1: Search for products
    chemical_name = "hydro"
    if len(sys.argv) > 1:
        chemical_name = sys.argv[1]
    
    products = await test_search_spectrochem(chemical_name)
    
    if products and len(products) > 0:
        # Test 2: Get details for the first product
        first_product = products[0]
        await test_get_product_details(
            first_product['product_id'],
            first_product['product_name']
        )
    else:
        print("\n⚠️  Skipping product details test - no products found")
    
    print("\n✅ All tests completed!\n")


if __name__ == "__main__":
    asyncio.run(main())

