import re
import httpx
from bs4 import BeautifulSoup
from langchain_core.tools import tool
from urllib.parse import urlparse, parse_qs, quote_plus

GLOSIL_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
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
    "sec-ch-ua-platform": '"Windows"',
}


@tool
async def search_glosil(search_term: str) -> str:
    """Search for products from Glosil Scientific by search term. Returns matching products with IDs. Use get_glosil_product_details with product_id and product_url to get pricing."""
    search_term = search_term.strip()
    if not search_term:
        return "Error: search_term is required"

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.post(
                "https://www.glosilscientific.com/search.php",
                data={"search": search_term},
                headers=GLOSIL_HEADERS,
            )

            if resp.status_code != 200:
                return f"Search failed with status {resp.status_code}"

            soup = BeautifulSoup(resp.text, "html.parser")
            products = []
            seen = set()

            product_items = soup.find_all("div", class_="ltn__product-item")
            for item in product_items:
                link = item.find("a", href=True)
                if not link:
                    continue
                url = link.get("href", "")
                if "productdesc.php" not in url:
                    continue

                parsed = urlparse(url)
                qp = parse_qs(parsed.query)
                pid = qp.get("pid", [None])[0]
                if not pid:
                    continue

                title_elem = item.find("h2", class_="product-title")
                if title_elem:
                    a = title_elem.find("a")
                    name = a.get_text(strip=True) if a else title_elem.get_text(strip=True)
                else:
                    name = link.get_text(strip=True) or link.get("title", "")

                if not name:
                    continue

                key = (pid, name)
                if key not in seen:
                    seen.add(key)
                    full_url = url if url.startswith("http") else f"https://www.glosilscientific.com/{url}"
                    products.append({"product_id": pid, "product_name": name, "product_url": full_url})

            if not products:
                return f"No products found for '{search_term}' in Glosil Scientific catalog."

            results = []
            for idx, p in enumerate(products, 1):
                info = f"**Product {idx}**\n"
                info += f"**Product Name:** {p['product_name']}\n"
                info += f"**Product ID:** {p['product_id']}\n"
                info += "**Brand:** GLOSIL\n"
                info += f"**Source:** [Glosil Scientific - {p['product_name']}]({p['product_url']})\n"
                results.append(info)

            text = f"**Glosil Scientific Products for '{search_term}' (Found {len(results)} products):**\n"
            text += f"**Search URL:** [glosilscientific.com](https://www.glosilscientific.com/search.php?search={quote_plus(search_term)})\n\n"
            text += "\n".join(results)
            text += "\n\n*Use get_glosil_product_details with the Product ID and Product URL to get pricing and details.*"
            return text

    except httpx.TimeoutException:
        return "Search request timed out. Please try again."
    except Exception as e:
        return f"Error during Glosil search: {e}"


@tool
async def get_glosil_product_details(product_id: str, product_url: str) -> str:
    """Get detailed product information from Glosil Scientific including price and specifications. Requires product_id and product_url from search_glosil."""
    product_id = product_id.strip()
    product_url = product_url.strip()
    if not product_id or not product_url:
        return "Error: product_id and product_url are required"

    if not product_url.startswith("http"):
        product_url = f"https://www.glosilscientific.com/{product_url}"

    try:
        headers = {**GLOSIL_HEADERS}
        headers["Referer"] = "https://www.glosilscientific.com/search.php"
        headers.pop("Content-Type", None)

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(product_url, headers=headers)

            if resp.status_code != 200:
                return f"Failed to get product details: Status {resp.status_code}"

            soup = BeautifulSoup(resp.text, "html.parser")
            for s in soup(["script", "style"]):
                s.decompose()

            info = "**Glosil Scientific Product Details**\n\n"
            info += f"**Brand:** GLOSIL\n"
            info += f"**Product ID:** {product_id}\n"
            info += f"**Source:** [Glosil Scientific - {product_id}]({product_url})\n\n"

            title = soup.find("h1", class_=re.compile(r"product.*title|title", re.I)) or soup.find("h1")
            if title:
                info += f"**Product Name:** {title.get_text(strip=True)}\n\n"

            price_elem = soup.find(class_=re.compile(r"price", re.I))
            if price_elem:
                info += f"**Price:** {price_elem.get_text(strip=True)}\n\n"

            desc = soup.find(class_=re.compile(r"description|detail|specification", re.I))
            if desc:
                lines = [l.strip() for l in desc.get_text(strip=True, separator="\n").split("\n") if l.strip() and len(l.strip()) > 3]
                if lines:
                    info += "**Description:**\n"
                    for l in lines[:20]:
                        info += f"  - {l}\n"
                    info += "\n"

            tables = soup.find_all("table")
            if tables:
                info += "**Product Information:**\n\n"
                for table in tables:
                    for row in table.find_all("tr"):
                        cells = row.find_all(["td", "th"])
                        if len(cells) >= 2:
                            label = cells[0].get_text(strip=True)
                            value = cells[1].get_text(strip=True)
                            if label and value:
                                info += f"  - **{label}:** {value}\n"

            return info

    except httpx.TimeoutException:
        return "Request timed out. Please try again."
    except Exception as e:
        return f"Error getting Glosil product details: {e}"
