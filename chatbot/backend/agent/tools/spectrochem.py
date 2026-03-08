import httpx
from bs4 import BeautifulSoup
from langchain_core.tools import tool
from urllib.parse import quote_plus

SPECTROCHEM_SEARCH_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9",
    "referer": "https://spectrochem.in/",
    "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
}

SPECTROCHEM_AJAX_HEADERS = {
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
    "origin": "https://spectrochem.in",
    "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    "x-requested-with": "XMLHttpRequest",
}


@tool
async def search_spectrochem(chemical_name: str) -> str:
    """Search for products from Spectrochem by chemical name. Returns matching products with IDs. Use get_spectrochem_product_details with product_id and product_name to get pricing and stock."""
    chemical_name = chemical_name.strip()
    if not chemical_name:
        return "Error: chemical_name is required"

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, verify=False) as client:
            resp = await client.get(
                f"https://spectrochem.in/?s={quote_plus(chemical_name)}",
                headers=SPECTROCHEM_SEARCH_HEADERS,
            )

            if resp.status_code != 200:
                return f"Search failed with status {resp.status_code}"

            soup = BeautifulSoup(resp.text, "html.parser")
            products = []
            seen = set()

            prod_table = soup.find("table", id="prod_result")
            if not prod_table:
                return f"No products found for '{chemical_name}' in Spectrochem catalog."

            stock_links = prod_table.find_all("a", class_="stockCheck")
            for link in stock_links:
                pid = link.get("data-id", "").strip()
                pname = link.get("data-name", "").strip()
                if pid and pname and (pid, pname) not in seen:
                    seen.add((pid, pname))
                    products.append({"product_id": pid, "product_name": pname})

            if not products:
                rows = prod_table.find_all("tr")
                for row in rows:
                    if row.find("th") or "categoryTr" in row.get("class", []):
                        continue
                    tds = row.find_all("td")
                    pid, pname = "", ""
                    for td in tds:
                        dt = td.get("data-title", "")
                        if dt == "Product Code":
                            pid = td.get_text(strip=True)
                        elif dt == "Product Name":
                            pname = td.get_text(separator=" ", strip=True)
                    if pid and pname and (pid, pname) not in seen:
                        seen.add((pid, pname))
                        products.append({"product_id": pid, "product_name": pname})

            if not products:
                return f"No products found for '{chemical_name}' in Spectrochem catalog."

            search_url = f"https://spectrochem.in/?s={quote_plus(chemical_name)}"

            results = []
            for idx, p in enumerate(products, 1):
                info = f"**Product {idx}**\n"
                info += f"**Product Name:** {p['product_name']}\n"
                info += f"**Product ID:** {p['product_id']}\n"
                info += "**Brand:** SPECTROCHEM\n"
                info += f"**Source:** [Spectrochem - {p['product_id']}]({search_url})\n"
                results.append(info)

            text = f"**Spectrochem Products for '{chemical_name}' (Found {len(results)} products):**\n"
            text += f"**Search URL:** [spectrochem.in]({search_url})\n\n"
            text += "\n".join(results)
            text += "\n\n*Use get_spectrochem_product_details with the Product ID and Product Name to get stock and pricing.*"
            return text

    except httpx.TimeoutException:
        return "Search request timed out. Please try again."
    except Exception as e:
        return f"Error during Spectrochem search: {e}"


@tool
async def get_spectrochem_product_details(product_id: str, product_name: str) -> str:
    """Get detailed product information from Spectrochem including stock and pricing. Requires product_id and product_name from search_spectrochem."""
    product_id = product_id.strip()
    product_name = product_name.strip()
    if not product_id or not product_name:
        return "Error: product_id and product_name are required"

    try:
        headers = {
            **SPECTROCHEM_AJAX_HEADERS,
            "referer": f"https://spectrochem.in/?s={quote_plus(product_name)}",
        }

        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            resp = await client.post(
                "https://spectrochem.in/wp-admin/admin-ajax.php",
                data={
                    "action": "load_stock_list",
                    "product_id": product_id,
                    "product_name": product_name,
                },
                headers=headers,
            )

            if resp.status_code != 200:
                return f"Failed to get product details: Status {resp.status_code}"

            soup = BeautifulSoup(resp.text, "html.parser")
            for s in soup(["script", "style"]):
                s.decompose()

            source_url = f"https://spectrochem.in/?s={quote_plus(product_name)}"

            info = "**Spectrochem Product Details**\n\n"
            info += f"**Brand:** SPECTROCHEM\n"
            info += f"**Product ID:** {product_id}\n"
            info += f"**Product Name:** {product_name}\n"
            info += f"**Source:** [Spectrochem - {product_id}]({source_url})\n\n"

            tables = soup.find_all("table")
            if tables:
                info += "**Stock/Pricing Information:**\n\n"
                for table in tables:
                    rows = table.find_all("tr")
                    hdrs = []
                    if rows:
                        hdrs = [th.get_text(strip=True) for th in rows[0].find_all(["th", "td"])]
                    for row in rows[1:] if hdrs else rows:
                        cells = row.find_all(["td", "th"])
                        parts = []
                        for ci, cell in enumerate(cells):
                            txt = cell.get_text(strip=True, separator=" ")
                            if txt:
                                parts.append(f"{hdrs[ci]}: {txt}" if hdrs and ci < len(hdrs) else txt)
                        if parts:
                            info += f"  - {' | '.join(parts)}\n"
                return info

            lists = soup.find_all(["ul", "ol"])
            if lists:
                info += "**Stock/Pricing Information:**\n\n"
                for ul in lists:
                    for li in ul.find_all("li"):
                        txt = li.get_text(strip=True, separator=" ")
                        if txt and len(txt) > 3:
                            info += f"  - {txt}\n"
                return info

            text = soup.get_text(strip=True, separator="\n")
            lines = [l.strip() for l in text.split("\n") if l.strip() and len(l.strip()) > 3]
            seen = []
            for l in lines:
                if l not in seen:
                    seen.append(l)
            if seen:
                info += "**Stock/Pricing Information:**\n\n"
                for l in seen[:30]:
                    info += f"  - {l}\n"
            else:
                info += "*Stock information not available.*\n"

            return info

    except httpx.TimeoutException:
        return "Request timed out. Please try again."
    except Exception as e:
        return f"Error getting Spectrochem product details: {e}"
