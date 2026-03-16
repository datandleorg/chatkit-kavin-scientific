import re
import httpx
from bs4 import BeautifulSoup
from langchain_core.tools import tool

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
    """Search the Glosil Scientific vendor knowledge base (ingested documents) by search term. Returns relevant chunks from the KB; use the returned content for product info in the quote table."""
    search_term = search_term.strip()
    if not search_term:
        return "Error: search_term is required"

    from knowledge_base import get_kb_id_by_vendor_name, hybrid_search

    kb_id = await get_kb_id_by_vendor_name("Glosil")
    if not kb_id:
        kb_id = await get_kb_id_by_vendor_name("Glosil Scientific")
    if not kb_id:
        return "The Glosil Scientific knowledge base is not set up or has no documents. Create a KB for vendor 'Glosil' or 'Glosil Scientific' and ingest documents first."

    chunks = await hybrid_search(kb_id, search_term, top_k=20)
    if not chunks:
        return f"No relevant documents found in the Glosil Scientific knowledge base for '{search_term}'."

    header = f"**Glosil Scientific (Knowledge Base) results for '{search_term}':**\n\n"
    return header + "\n---\n".join(chunks)


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

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, verify=False) as client:
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
