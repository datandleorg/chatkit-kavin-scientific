import re
import httpx
from bs4 import BeautifulSoup
from langchain_core.tools import tool
from urllib.parse import quote_plus, urlparse

TCI_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
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
    "sec-ch-ua-platform": '"Windows"',
}


@tool
async def search_tci(search_term: str) -> str:
    """Search for products from TCI Chemicals by search term. Returns matching products with codes and CAS numbers. Use get_tci_product_details with product_url to get pricing and stock."""
    search_term = search_term.strip()
    if not search_term:
        return "Error: search_term is required"

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(
                f"https://www.tcichemicals.com/IN/en/search/?text={quote_plus(search_term)}",
                headers=TCI_HEADERS,
            )

            if resp.status_code != 200:
                return f"Search failed with status {resp.status_code}"

            soup = BeautifulSoup(resp.text, "html.parser")
            products = []
            seen = set()

            product_items = soup.find_all("div", class_="prductlist")
            for item in product_items:
                pid = item.get("data-id", "").strip()
                pcode = item.get("data-product-code1", "").strip() or pid
                cas = item.get("data-casno", "").strip()

                if not pid:
                    continue

                title_link = item.find("a", class_="product-title")
                if title_link:
                    name = title_link.get_text(strip=True)
                    url = title_link.get("href", "")
                else:
                    link = item.find("a", href=True, title=True)
                    if not link:
                        continue
                    name = link.get("title", "").strip() or link.get_text(strip=True)
                    url = link.get("href", "")

                if not name or not url:
                    continue

                if not url.startswith("/"):
                    if "tcichemicals.com" in url:
                        url = urlparse(url).path

                key = (pid, name)
                if key not in seen:
                    seen.add(key)
                    products.append({
                        "product_id": pid,
                        "product_code": pcode,
                        "product_name": name,
                        "cas_number": cas,
                        "product_url": url,
                    })

            if not products:
                return f"No products found for '{search_term}' in TCI Chemicals catalog."

            search_url = f"https://www.tcichemicals.com/IN/en/search/?text={quote_plus(search_term)}"

            results = []
            for idx, p in enumerate(products, 1):
                full_url = p['product_url']
                if full_url.startswith("/"):
                    full_url = f"https://www.tcichemicals.com{full_url}"

                info = f"**Product {idx}**\n"
                info += f"**Product Name:** {p['product_name']}\n"
                info += f"**Product Code:** {p['product_code']}\n"
                if p["cas_number"]:
                    info += f"**CAS Number:** {p['cas_number']}\n"
                info += "**Brand:** TCI\n"
                info += f"**Source:** [TCI Chemicals - {p['product_code']}]({full_url})\n"
                results.append(info)

            text = f"**TCI Chemicals Products for '{search_term}' (Found {len(results)} products):**\n"
            text += f"**Search URL:** [tcichemicals.com]({search_url})\n\n"
            text += "\n".join(results)
            text += "\n\n*Use get_tci_product_details with the Product URL to get pricing, stock, and pack sizes.*"
            return text

    except httpx.TimeoutException:
        return "Search request timed out. Please try again."
    except Exception as e:
        return f"Error during TCI search: {e}"


@tool
async def get_tci_product_details(product_url: str) -> str:
    """Get detailed product information from TCI Chemicals including stock, pricing, and pack sizes. Requires product_url from search_tci (e.g. '/IN/en/p/A0638')."""
    product_url = product_url.strip()
    if not product_url:
        return "Error: product_url is required"

    if not product_url.startswith("http"):
        if product_url.startswith("/"):
            product_url = f"https://www.tcichemicals.com{product_url}"
        else:
            product_url = f"https://www.tcichemicals.com/IN/en/p/{product_url}"

    try:
        headers = {**TCI_HEADERS, "Referer": "https://www.tcichemicals.com/IN/en/search/"}

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(product_url, headers=headers)

            if resp.status_code != 200:
                return f"Failed to get product details: Status {resp.status_code}"

            soup = BeautifulSoup(resp.text, "html.parser")
            for s in soup(["script", "style"]):
                s.decompose()

            info = "**TCI Chemicals Product Details**\n\n"
            info += "**Brand:** TCI\n"
            info += f"**Source:** [TCI Chemicals Product Page]({product_url})\n\n"

            title = soup.find("h1") or soup.find(class_=re.compile(r"product.*title|title", re.I))
            if title:
                info += f"**Product Name:** {title.get_text(strip=True)}\n\n"

            pricing_table = soup.find("table", id="PricingTable") or soup.find("table", class_=re.compile(r"pricing|table-pricing", re.I))
            if pricing_table:
                info += "**Pricing & Stock Information:**\n\n"
                rows = pricing_table.find_all("tr")
                hdrs = []
                if rows:
                    hdrs = [th.get_text(strip=True) for th in rows[0].find_all(["th", "td"])]
                for row in rows[1:] if hdrs else rows:
                    cells = row.find_all(["td", "th"])
                    row_data = {}
                    for ci, cell in enumerate(cells):
                        da = cell.get("data-attr", "")
                        txt = cell.get_text(strip=True)
                        if da:
                            row_data[da.replace(":", "").strip()] = txt
                        elif hdrs and ci < len(hdrs):
                            row_data[hdrs[ci]] = txt
                        else:
                            row_data[f"Column {ci+1}"] = txt
                    if row_data:
                        for k, v in row_data.items():
                            if v and v not in ("", "N/A"):
                                info += f"  - **{k}:** {v}\n"
                        info += "\n"

            spec_tables = soup.find_all("table")
            for table in spec_tables:
                if table == pricing_table:
                    continue
                rows = table.find_all("tr")
                if rows:
                    info += "**Product Specifications:**\n\n"
                    for row in rows:
                        cells = row.find_all(["td", "th"])
                        if len(cells) >= 2:
                            label = cells[0].get_text(strip=True)
                            value = cells[1].get_text(strip=True)
                            if label and value:
                                info += f"  - **{label}:** {value}\n"
                    info += "\n"
                    break

            return info

    except httpx.TimeoutException:
        return "Request timed out. Please try again."
    except Exception as e:
        return f"Error getting TCI product details: {e}"
