"""
Product search tools for Kavin Scientific Agent
Includes tools for Hyma, Spectrochem, Glosil, and TCI product searches
"""
import logging
import re
import time
import uuid
from urllib.parse import quote_plus, urlparse, parse_qs

import httpx
from bs4 import BeautifulSoup
from agents import function_tool

logger = logging.getLogger(__name__)


@function_tool
def search_hyma(chemical_name: str) -> str:
    """
    Search for products from Hyma Synthesis brand by chemical name. 
    Returns a list of matching products with their catalog numbers (ItemCode). 
    Use get_hyma_product_details to get detailed information for specific products.
    
    Args:
        chemical_name: The chemical name to search for (e.g., 'acetone', 'formic acid')
    
    Returns:
        Formatted text with search results or error message
    """
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    logger.info("=" * 60)
    logger.info(f"🔧 [RequestID: {request_id}] Tool Call: search_hyma")
    logger.info(f"📥 [RequestID: {request_id}] Chemical name: '{chemical_name}'")
    logger.info("=" * 60)
    
    chemical_name = chemical_name.strip()
    if not chemical_name:
        logger.warning(f"[RequestID: {request_id}] search_hyma called without chemical_name")
        return "Error: chemical_name is required"
    
    try:
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
        
        with httpx.Client(timeout=30.0) as client:
            logger.debug(f"[RequestID: {request_id}] Calling Hyma Synthesis search API")
            search_url = "https://hymasynthesis.com/webservices/api/Values/GetProductsBasedOnChemicalName"
            search_data = {"ChemicalName": chemical_name}
            
            search_response = client.post(search_url, data=search_data, headers=headers)
            
            logger.debug(f"[RequestID: {request_id}] Hyma search API response status: {search_response.status_code}")
            
            if search_response.status_code != 200:
                error_detail = search_response.text
                logger.error(f"[RequestID: {request_id}] Hyma search API returned error: {search_response.status_code}")
                return f"Search failed: {error_detail}"
            
            products = search_response.json()
            
            if not products or len(products) == 0:
                logger.info(f"[RequestID: {request_id}] No products found for chemical: {chemical_name}")
                return f"No products found for '{chemical_name}' in Hyma Synthesis catalog."
            
            logger.info(f"[RequestID: {request_id}] Found {len(products)} product(s)")
            
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
                return f"Found products for '{chemical_name}' but could not extract Catalog Numbers."
            
            result_text = f"**Hyma Synthesis Products for '{chemical_name}' (Found {len(results)} products):**\n\n" + "\n".join(results)
            result_text += "\n\n*Use get_hyma_product_details with the Catalog Number (ItemCode) to get detailed product information including stock, price, and specifications.*"
            
            elapsed_time = time.time() - start_time
            logger.info(f"✅ [RequestID: {request_id}] Tool 'search_hyma' completed successfully in {elapsed_time:.2f}s")
            logger.info("=" * 60)
            return result_text
            
    except httpx.TimeoutException:
        logger.error(f"[RequestID: {request_id}] Hyma search request timed out")
        return "Search request timed out. Please try again."
    except httpx.ConnectError as e:
        logger.error(f"[RequestID: {request_id}] Could not connect to Hyma Synthesis API: {e}")
        return f"Could not connect to Hyma Synthesis API: {str(e)}"
    except Exception as e:
        logger.error(f"[RequestID: {request_id}] Error during Hyma search: {str(e)}", exc_info=True)
        return f"Error during Hyma search: {str(e)}"


@function_tool
def get_hyma_product_details(item_code: str) -> str:
    """
    Get detailed product information from Hyma Synthesis including stock availability, price, pack size, 
    CAS number, purity, and specifications. Requires the ItemCode (catalog number) from a search_hyma result.
    
    Args:
        item_code: The ItemCode (catalog number) of the product to get details for
    
    Returns:
        Formatted text with detailed product information or error message
    """
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    logger.info("=" * 60)
    logger.info(f"🔧 [RequestID: {request_id}] Tool Call: get_hyma_product_details")
    logger.info(f"📥 [RequestID: {request_id}] ItemCode: '{item_code}'")
    logger.info("=" * 60)
    
    item_code = item_code.strip()
    if not item_code:
        logger.warning(f"[RequestID: {request_id}] get_hyma_product_details called without item_code")
        return "Error: item_code is required"
    
    try:
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
        
        with httpx.Client(timeout=30.0) as client:
            logger.debug(f"[RequestID: {request_id}] Fetching product details for ItemCode: {item_code}")
            
            stock_url = "https://hymasynthesis.com/webservices/api/Values/GetWebStockItemMstBasedOnId"
            stock_response = client.get(stock_url, params={"ItemCode": item_code}, headers=headers)
            
            spec_url = "https://hymasynthesis.com/webservices/api/Values/GetProductSpecificationOnCatalogNo"
            spec_response = client.get(spec_url, params={"ItemCode": item_code}, headers=headers)
            
            stock_response_data = stock_response.json() if stock_response.status_code == 200 else {}
            spec_data = spec_response.json() if spec_response.status_code == 200 else {}
            
            if not stock_response_data and not spec_data:
                logger.warning(f"[RequestID: {request_id}] No product details found for ItemCode: {item_code}")
                return f"No product details found for ItemCode '{item_code}'."
            
            product_info = "**Hyma Synthesis Product Details**\n\n"
            product_info += f"**Brand:** HYMA\n"
            product_info += f"**Catalog Number (ItemCode):** {item_code}\n\n"
            
            if stock_response_data:
                item_info = stock_response_data.get("Item", [])
                if item_info and len(item_info) > 0:
                    item = item_info[0]
                    product_info += f"**Product Name:** {item.get('ItemName', item.get('itemName', 'N/A'))}\n"
                    product_info += f"**CAS Number:** {item.get('CAS', item.get('cas', 'N/A'))}\n"
                    product_info += f"**Stockable:** {item.get('Stockable', item.get('stockable', 'N/A'))}\n"
                    product_info += f"**Active:** {item.get('Active', item.get('active', 'N/A'))}\n"
                    product_info += "\n"
                
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
            
            if spec_data:
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
            
            logger.info(f"[RequestID: {request_id}] Successfully retrieved product details")
            elapsed_time = time.time() - start_time
            logger.info(f"✅ [RequestID: {request_id}] Tool 'get_hyma_product_details' completed successfully in {elapsed_time:.2f}s")
            logger.info("=" * 60)
            return product_info
            
    except httpx.TimeoutException:
        logger.error(f"[RequestID: {request_id}] Request timed out")
        return "Request timed out. Please try again."
    except httpx.ConnectError as e:
        logger.error(f"[RequestID: {request_id}] Could not connect to Hyma Synthesis API: {e}")
        return f"Could not connect to Hyma Synthesis API: {str(e)}"
    except Exception as e:
        logger.error(f"[RequestID: {request_id}] Error getting product details: {str(e)}", exc_info=True)
        return f"Error getting product details: {str(e)}"


@function_tool
def search_spectrochem(chemical_name: str) -> str:
    """
    Search for products from Spectrochem brand by chemical name. 
    Returns a list of matching products with their product IDs and names. 
    Use get_spectrochem_product_details to get detailed information for specific products.
    
    Args:
        chemical_name: The chemical name to search for (e.g., 'acetone', 'formic acid', 'hydro')
    
    Returns:
        Formatted text with search results or error message
    """
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    logger.info("=" * 60)
    logger.info(f"🔧 [RequestID: {request_id}] Tool Call: search_spectrochem")
    logger.info(f"📥 [RequestID: {request_id}] Chemical name: '{chemical_name}'")
    logger.info("=" * 60)
    
    chemical_name = chemical_name.strip()
    if not chemical_name:
        logger.warning(f"[RequestID: {request_id}] search_spectrochem called without chemical_name")
        return "Error: chemical_name is required"
    
    try:
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
        
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            logger.debug(f"[RequestID: {request_id}] Calling Spectrochem search")
            search_url = f"https://spectrochem.in/?s={quote_plus(chemical_name)}"
            search_response = client.get(search_url, headers=headers)
            
            logger.debug(f"[RequestID: {request_id}] Spectrochem search response status: {search_response.status_code}")
            
            if search_response.status_code != 200:
                logger.error(f"[RequestID: {request_id}] Spectrochem search returned error: {search_response.status_code}")
                return f"Search failed with status {search_response.status_code}"
            
            html_content = search_response.text
            soup = BeautifulSoup(html_content, 'html.parser')
            
            products = []
            seen_products = set()
            
            prod_table = soup.find('table', id='prod_result')
            
            if prod_table:
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
                        logger.debug(f"[RequestID: {request_id}] Error parsing stock check link: {e}")
                        continue
                
                if not products:
                    rows = prod_table.find_all('tr')
                    for row in rows:
                        try:
                            if row.find('th') or 'categoryTr' in row.get('class', []):
                                continue
                            
                            tds = row.find_all('td')
                            if len(tds) < 2:
                                continue
                            
                            product_code_td = None
                            product_name_td = None
                            
                            for td in tds:
                                data_title = td.get('data-title', '')
                                if data_title == 'Product Code':
                                    product_code_td = td
                                elif data_title == 'Product Name':
                                    product_name_td = td
                            
                            product_id = product_code_td.get_text(strip=True) if product_code_td else ""
                            product_name = product_name_td.get_text(separator=' ', strip=True) if product_name_td else ""
                            
                            if product_id and product_name:
                                product_key = (product_id, product_name)
                                if product_key not in seen_products:
                                    seen_products.add(product_key)
                                    products.append({
                                        "product_id": product_id,
                                        "product_name": product_name
                                    })
                        except Exception as e:
                            logger.debug(f"[RequestID: {request_id}] Error parsing table row: {e}")
                            continue
            
            if not products:
                logger.info(f"[RequestID: {request_id}] No products found for chemical: {chemical_name}")
                return f"No products found for '{chemical_name}' in Spectrochem catalog."
            
            logger.info(f"[RequestID: {request_id}] Found {len(products)} product(s)")
            
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
            logger.info(f"✅ [RequestID: {request_id}] Tool 'search_spectrochem' completed successfully in {elapsed_time:.2f}s")
            logger.info("=" * 60)
            return result_text
            
    except httpx.TimeoutException:
        logger.error(f"[RequestID: {request_id}] Search request timed out")
        return "Search request timed out. Please try again."
    except httpx.ConnectError as e:
        logger.error(f"[RequestID: {request_id}] Could not connect to Spectrochem: {e}")
        return f"Could not connect to Spectrochem: {str(e)}"
    except Exception as e:
        logger.error(f"[RequestID: {request_id}] Error during Spectrochem search: {str(e)}", exc_info=True)
        return f"Error during Spectrochem search: {str(e)}"


@function_tool
def get_spectrochem_product_details(product_id: str, product_name: str) -> str:
    """
    Get detailed product information from Spectrochem including stock availability, price, and specifications. 
    Requires the product_id and product_name from a search_spectrochem result.
    
    Args:
        product_id: The product ID (catalog number) of the product to get details for
        product_name: The product name of the product to get details for
    
    Returns:
        Formatted text with detailed product information or error message
    """
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    logger.info("=" * 60)
    logger.info(f"🔧 [RequestID: {request_id}] Tool Call: get_spectrochem_product_details")
    logger.info(f"📥 [RequestID: {request_id}] Product ID: '{product_id}', Name: '{product_name}'")
    logger.info("=" * 60)
    
    product_id = product_id.strip()
    product_name = product_name.strip()
    
    if not product_id or not product_name:
        logger.warning(f"[RequestID: {request_id}] Missing required parameters")
        return "Error: product_id and product_name are required"
    
    try:
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
        
        form_data = {
            "action": "load_stock_list",
            "product_id": product_id,
            "product_name": product_name
        }
        
        with httpx.Client(timeout=30.0) as client:
            logger.debug(f"[RequestID: {request_id}] Fetching product details")
            stock_url = "https://spectrochem.in/wp-admin/admin-ajax.php"
            stock_response = client.post(stock_url, data=form_data, headers=headers)
            
            logger.debug(f"[RequestID: {request_id}] Spectrochem stock API response status: {stock_response.status_code}")
            
            if stock_response.status_code != 200:
                logger.error(f"[RequestID: {request_id}] Spectrochem stock API returned error: {stock_response.status_code}")
                return f"Failed to get product details: Status {stock_response.status_code}"
            
            response_text = stock_response.text
            product_info = "**Spectrochem Product Details**\n\n"
            product_info += f"**Brand:** SPECTROCHEM\n"
            product_info += f"**Product ID:** {product_id}\n"
            product_info += f"**Product Name:** {product_name}\n\n"
            
            soup = BeautifulSoup(response_text, 'html.parser')
            
            for script in soup(["script", "style"]):
                script.decompose()
            
            data_found = False
            
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
                    
                    for row in rows[1:] if headers else rows:
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
            
            if not data_found:
                text_content = soup.get_text(strip=True, separator='\n')
                if text_content and len(text_content) > 10:
                    lines = [line.strip() for line in text_content.split('\n') if line.strip() and len(line.strip()) > 3]
                    filtered_lines = []
                    prev_line = None
                    for line in lines:
                        if line != prev_line:
                            filtered_lines.append(line)
                        prev_line = line
                    
                    if filtered_lines:
                        product_info += "**Stock/Pricing Information:**\n\n"
                        for line in filtered_lines[:30]:
                            product_info += f"  - {line}\n"
                else:
                    product_info += "*Stock information not available.*\n"
            
            logger.info(f"[RequestID: {request_id}] Successfully retrieved product details")
            elapsed_time = time.time() - start_time
            logger.info(f"✅ [RequestID: {request_id}] Tool 'get_spectrochem_product_details' completed successfully in {elapsed_time:.2f}s")
            logger.info("=" * 60)
            return product_info
            
    except httpx.TimeoutException:
        logger.error(f"[RequestID: {request_id}] Request timed out")
        return "Request timed out. Please try again."
    except httpx.ConnectError as e:
        logger.error(f"[RequestID: {request_id}] Could not connect to Spectrochem: {e}")
        return f"Could not connect to Spectrochem: {str(e)}"
    except Exception as e:
        logger.error(f"[RequestID: {request_id}] Error getting product details: {str(e)}", exc_info=True)
        return f"Error getting product details: {str(e)}"


@function_tool
def search_glosil(search_term: str) -> str:
    """
    Search for products from Glosil Scientific brand by search term. 
    Returns a list of matching products with their product IDs (encoded) and names. 
    Use get_glosil_product_details to get detailed information for specific products.
    
    Args:
        search_term: The search term to search for (e.g., 'thermo', 'anemometer', 'balance')
    
    Returns:
        Formatted text with search results or error message
    """
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    logger.info("=" * 60)
    logger.info(f"🔧 [RequestID: {request_id}] Tool Call: search_glosil")
    logger.info(f"📥 [RequestID: {request_id}] Search term: '{search_term}'")
    logger.info("=" * 60)
    
    search_term = search_term.strip()
    if not search_term:
        logger.warning(f"[RequestID: {request_id}] search_glosil called without search_term")
        return "Error: search_term is required"
    
    try:
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
        
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            logger.debug(f"[RequestID: {request_id}] Calling Glosil Scientific search")
            search_url = "https://www.glosilscientific.com/search.php"
            form_data = {"search": search_term}
            search_response = client.post(search_url, data=form_data, headers=headers)
            
            logger.debug(f"[RequestID: {request_id}] Glosil search response status: {search_response.status_code}")
            
            if search_response.status_code != 200:
                logger.error(f"[RequestID: {request_id}] Glosil search returned error: {search_response.status_code}")
                return f"Search failed with status {search_response.status_code}"
            
            html_content = search_response.text
            soup = BeautifulSoup(html_content, 'html.parser')
            
            products = []
            seen_products = set()
            
            product_items = soup.find_all('div', class_='ltn__product-item')
            
            for item in product_items:
                try:
                    product_link = item.find('a', href=True)
                    if not product_link:
                        continue
                    
                    product_url = product_link.get('href', '')
                    if not product_url or 'productdesc.php' not in product_url:
                        continue
                    
                    parsed_url = urlparse(product_url)
                    query_params = parse_qs(parsed_url.query)
                    product_id = query_params.get('pid', [None])[0] if query_params.get('pid') else None
                    
                    if not product_id:
                        continue
                    
                    product_title_elem = item.find('h2', class_='product-title')
                    if product_title_elem:
                        title_link = product_title_elem.find('a')
                        product_name = title_link.get_text(strip=True) if title_link else product_title_elem.get_text(strip=True)
                    else:
                        product_name = product_link.get_text(strip=True) or product_link.get('title', '')
                    
                    if not product_name:
                        continue
                    
                    product_key = (product_id, product_name)
                    if product_key not in seen_products:
                        seen_products.add(product_key)
                        products.append({
                            "product_id": product_id,
                            "product_name": product_name,
                            "product_url": product_url if product_url.startswith('http') else f"https://www.glosilscientific.com/{product_url}"
                        })
                except Exception as e:
                    logger.debug(f"[RequestID: {request_id}] Error parsing product item: {e}")
                    continue
            
            if not products:
                logger.info(f"[RequestID: {request_id}] No products found for search term: {search_term}")
                return f"No products found for '{search_term}' in Glosil Scientific catalog."
            
            logger.info(f"[RequestID: {request_id}] Found {len(products)} product(s)")
            
            results = []
            for idx, product in enumerate(products, 1):
                product_info = f"**Product {idx}**\n"
                product_info += f"**Product Name:** {product['product_name']}\n"
                product_info += f"**Product ID:** {product['product_id']}\n"
                product_info += f"**Brand:** GLOSIL\n"
                results.append(product_info)
            
            result_text = f"**Glosil Scientific Products for '{search_term}' (Found {len(results)} products):**\n\n" + "\n".join(results)
            result_text += "\n\n*Use get_glosil_product_details with the Product ID and Product URL to get detailed product information including stock and pricing.*"
            
            elapsed_time = time.time() - start_time
            logger.info(f"✅ [RequestID: {request_id}] Tool 'search_glosil' completed successfully in {elapsed_time:.2f}s")
            logger.info("=" * 60)
            return result_text
            
    except httpx.TimeoutException:
        logger.error(f"[RequestID: {request_id}] Search request timed out")
        return "Search request timed out. Please try again."
    except httpx.ConnectError as e:
        logger.error(f"[RequestID: {request_id}] Could not connect to Glosil Scientific: {e}")
        return f"Could not connect to Glosil Scientific: {str(e)}"
    except Exception as e:
        logger.error(f"[RequestID: {request_id}] Error during Glosil search: {str(e)}", exc_info=True)
        return f"Error during Glosil search: {str(e)}"


@function_tool
def get_glosil_product_details(product_id: str, product_url: str) -> str:
    """
    Get detailed product information from Glosil Scientific including stock availability, price, and specifications. 
    Requires the product_id (encoded pid from search_glosil result) and product_url.
    
    Args:
        product_id: The product ID (encoded pid, e.g., 'Nw==') from a search_glosil result
        product_url: The product URL (e.g., 'productdesc.php?pid=Nw==') from a search_glosil result
    
    Returns:
        Formatted text with detailed product information or error message
    """
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    logger.info("=" * 60)
    logger.info(f"🔧 [RequestID: {request_id}] Tool Call: get_glosil_product_details")
    logger.info(f"📥 [RequestID: {request_id}] Product ID: '{product_id}'")
    logger.info("=" * 60)
    
    product_id = product_id.strip()
    product_url = product_url.strip()
    
    if not product_id or not product_url:
        logger.warning(f"[RequestID: {request_id}] Missing required parameters")
        return "Error: product_id and product_url are required"
    
    try:
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
        
        if not product_url.startswith('http'):
            product_url = f"https://www.glosilscientific.com/{product_url}"
        
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            logger.debug(f"[RequestID: {request_id}] Fetching product details from URL: {product_url}")
            detail_response = client.get(product_url, headers=headers)
            
            logger.debug(f"[RequestID: {request_id}] Glosil product details response status: {detail_response.status_code}")
            
            if detail_response.status_code != 200:
                logger.error(f"[RequestID: {request_id}] Glosil product details API returned error: {detail_response.status_code}")
                return f"Failed to get product details: Status {detail_response.status_code}"
            
            response_text = detail_response.text
            soup = BeautifulSoup(response_text, 'html.parser')
            
            product_info = "**Glosil Scientific Product Details**\n\n"
            product_info += f"**Brand:** GLOSIL\n"
            product_info += f"**Product ID:** {product_id}\n\n"
            
            for script in soup(["script", "style"]):
                script.decompose()
            
            data_found = False
            
            product_title = soup.find('h1', class_=re.compile(r'product.*title|title', re.I))
            if not product_title:
                product_title = soup.find('h1')
            if product_title:
                title_text = product_title.get_text(strip=True)
                if title_text:
                    product_info += f"**Product Name:** {title_text}\n\n"
                    data_found = True
            
            price_elem = soup.find(class_=re.compile(r'price', re.I))
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                if price_text:
                    product_info += f"**Price:** {price_text}\n\n"
                    data_found = True
            
            desc_elem = soup.find(class_=re.compile(r'description|detail|specification', re.I))
            if desc_elem:
                desc_text = desc_elem.get_text(strip=True, separator='\n')
                if desc_text and len(desc_text) > 10:
                    product_info += "**Description:**\n"
                    lines = [line.strip() for line in desc_text.split('\n') if line.strip() and len(line.strip()) > 3]
                    for line in lines[:20]:
                        product_info += f"  - {line}\n"
                    product_info += "\n"
                    data_found = True
            
            tables = soup.find_all('table')
            if tables:
                data_found = True
                product_info += "**Product Information:**\n\n"
                for table in tables:
                    rows = table.find_all('tr')
                    for row in rows:
                        cells = row.find_all(['td', 'th'])
                        if len(cells) >= 2:
                            label = cells[0].get_text(strip=True)
                            value = cells[1].get_text(strip=True)
                            if label and value:
                                product_info += f"  - **{label}:** {value}\n"
            
            if not data_found:
                text_content = soup.get_text(strip=True, separator='\n')
                if text_content and len(text_content) > 10:
                    lines = [line.strip() for line in text_content.split('\n') if line.strip() and len(line.strip()) > 3]
                    if lines:
                        product_info += "**Product Information:**\n\n"
                        for line in lines[:30]:
                            product_info += f"  - {line}\n"
            
            logger.info(f"[RequestID: {request_id}] Successfully retrieved product details")
            elapsed_time = time.time() - start_time
            logger.info(f"✅ [RequestID: {request_id}] Tool 'get_glosil_product_details' completed successfully in {elapsed_time:.2f}s")
            logger.info("=" * 60)
            return product_info
            
    except httpx.TimeoutException:
        elapsed_time = time.time() - start_time
        logger.error(f"[RequestID: {request_id}] Request timed out")
        logger.info(f"⏱️  [RequestID: {request_id}] Tool 'get_glosil_product_details' timed out after {elapsed_time:.2f}s")
        logger.info("=" * 60)
        return "Request timed out. Please try again."
    except httpx.ConnectError as e:
        logger.error(f"[RequestID: {request_id}] Could not connect to Glosil Scientific: {e}")
        return f"Could not connect to Glosil Scientific: {str(e)}"
    except Exception as e:
        logger.error(f"[RequestID: {request_id}] Error getting product details: {str(e)}", exc_info=True)
        return f"Error getting product details: {str(e)}"


@function_tool
def search_tci(search_term: str) -> str:
    """
    Search for products from TCI Chemicals brand by search term. 
    Returns a list of matching products with their product IDs, codes, CAS numbers, and names. 
    Use get_tci_product_details to get detailed information for specific products.
    
    Args:
        search_term: The search term to search for (e.g., 'acetone', 'formic acid', 'sodium')
    
    Returns:
        Formatted text with search results or error message
    """
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    logger.info("=" * 60)
    logger.info(f"🔧 [RequestID: {request_id}] Tool Call: search_tci")
    logger.info(f"📥 [RequestID: {request_id}] Search term: '{search_term}'")
    logger.info("=" * 60)
    
    search_term = search_term.strip()
    if not search_term:
        logger.warning(f"[RequestID: {request_id}] search_tci called without search_term")
        return "Error: search_term is required"
    
    try:
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
        
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            logger.debug(f"[RequestID: {request_id}] Calling TCI Chemicals search")
            search_url = f"https://www.tcichemicals.com/IN/en/search/?text={quote_plus(search_term)}"
            search_response = client.get(search_url, headers=headers)
            
            logger.debug(f"[RequestID: {request_id}] TCI search response status: {search_response.status_code}")
            
            if search_response.status_code != 200:
                logger.error(f"[RequestID: {request_id}] TCI search returned error: {search_response.status_code}")
                return f"Search failed with status {search_response.status_code}"
            
            html_content = search_response.text
            soup = BeautifulSoup(html_content, 'html.parser')
            
            products = []
            seen_products = set()
            
            product_items = soup.find_all('div', class_='prductlist')
            
            for item in product_items:
                try:
                    product_id = item.get('data-id', '').strip()
                    product_code = item.get('data-product-code1', '').strip() or product_id
                    cas_number = item.get('data-casno', '').strip()
                    
                    if not product_id:
                        continue
                    
                    product_title_link = item.find('a', class_='product-title')
                    if product_title_link:
                        product_name = product_title_link.get_text(strip=True)
                        product_url = product_title_link.get('href', '')
                    else:
                        product_link = item.find('a', href=True, title=True)
                        if product_link:
                            product_name = product_link.get('title', '').strip() or product_link.get_text(strip=True)
                            product_url = product_link.get('href', '')
                        else:
                            continue
                    
                    if not product_name or not product_url:
                        continue
                    
                    if not product_url.startswith('/'):
                        if 'tcichemicals.com' in product_url:
                            parsed = urlparse(product_url)
                            product_url = parsed.path
                    
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
                    logger.debug(f"[RequestID: {request_id}] Error parsing product item: {e}")
                    continue
            
            if not products:
                logger.info(f"[RequestID: {request_id}] No products found for search term: {search_term}")
                return f"No products found for '{search_term}' in TCI Chemicals catalog."
            
            logger.info(f"[RequestID: {request_id}] Found {len(products)} product(s)")
            
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
            logger.info(f"✅ [RequestID: {request_id}] Tool 'search_tci' completed successfully in {elapsed_time:.2f}s")
            logger.info("=" * 60)
            return result_text
            
    except httpx.TimeoutException:
        logger.error(f"[RequestID: {request_id}] Search request timed out")
        return "Search request timed out. Please try again."
    except httpx.ConnectError as e:
        logger.error(f"[RequestID: {request_id}] Could not connect to TCI Chemicals: {e}")
        return f"Could not connect to TCI Chemicals: {str(e)}"
    except Exception as e:
        logger.error(f"[RequestID: {request_id}] Error during TCI search: {str(e)}", exc_info=True)
        return f"Error during TCI search: {str(e)}"


@function_tool
def get_tci_product_details(product_url: str) -> str:
    """
    Get detailed product information from TCI Chemicals including stock availability, price, pack sizes, and specifications. 
    Requires the product_url from a search_tci result.
    
    Args:
        product_url: The product URL (e.g., '/IN/en/p/A0638') from a search_tci result
    
    Returns:
        Formatted text with detailed product information or error message
    """
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    logger.info("=" * 60)
    logger.info(f"🔧 [RequestID: {request_id}] Tool Call: get_tci_product_details")
    logger.info(f"📥 [RequestID: {request_id}] Product URL: '{product_url}'")
    logger.info("=" * 60)
    
    product_url = product_url.strip()
    if not product_url:
        logger.warning(f"[RequestID: {request_id}] get_tci_product_details called without product_url")
        return "Error: product_url is required"
    
    try:
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
        
        if not product_url.startswith('http'):
            if product_url.startswith('/'):
                product_url = f"https://www.tcichemicals.com{product_url}"
            else:
                product_url = f"https://www.tcichemicals.com/IN/en/p/{product_url}"
        
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            logger.debug(f"[RequestID: {request_id}] Fetching product details from URL: {product_url}")
            detail_response = client.get(product_url, headers=headers)
            
            logger.debug(f"[RequestID: {request_id}] TCI product details response status: {detail_response.status_code}")
            
            if detail_response.status_code != 200:
                logger.error(f"[RequestID: {request_id}] TCI product details API returned error: {detail_response.status_code}")
                return f"Failed to get product details: Status {detail_response.status_code}"
            
            response_text = detail_response.text
            soup = BeautifulSoup(response_text, 'html.parser')
            
            product_info = "**TCI Chemicals Product Details**\n\n"
            product_info += f"**Brand:** TCI\n\n"
            
            for script in soup(["script", "style"]):
                script.decompose()
            
            product_title = soup.find('h1') or soup.find(class_=re.compile(r'product.*title|title', re.I))
            if product_title:
                title_text = product_title.get_text(strip=True)
                if title_text:
                    product_info += f"**Product Name:** {title_text}\n\n"
            
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
            
            text_content = soup.get_text(strip=True, separator='\n')
            if text_content and len(text_content) > 10:
                lines = [line.strip() for line in text_content.split('\n') if line.strip() and len(line.strip()) > 3]
                important_lines = [line for line in lines if not any(skip in line.lower() for skip in ['cookie', 'privacy', 'menu', 'search', 'login', 'cart'])]
                if important_lines and len(important_lines) > 0:
                    if len(product_info.split('\n')) < 20:
                        product_info += "**Additional Information:**\n\n"
                        for line in important_lines[:15]:
                            product_info += f"  - {line}\n"
            
            logger.info(f"[RequestID: {request_id}] Successfully retrieved product details")
            elapsed_time = time.time() - start_time
            logger.info(f"✅ [RequestID: {request_id}] Tool 'get_tci_product_details' completed successfully in {elapsed_time:.2f}s")
            logger.info("=" * 60)
            return product_info
            
    except httpx.TimeoutException:
        logger.error(f"[RequestID: {request_id}] Request timed out")
        return "Request timed out. Please try again."
    except httpx.ConnectError as e:
        logger.error(f"[RequestID: {request_id}] Could not connect to TCI Chemicals: {e}")
        return f"Could not connect to TCI Chemicals: {str(e)}"
    except Exception as e:
        logger.error(f"[RequestID: {request_id}] Error getting product details: {str(e)}", exc_info=True)
        return f"Error getting product details: {str(e)}"

