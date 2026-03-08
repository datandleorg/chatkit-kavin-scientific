import httpx
from langchain_core.tools import tool
from urllib.parse import quote_plus, quote

HYMA_BASE_URL = "https://www.hymasynthesis.com"

HYMA_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
    "origin": "https://www.hymasynthesis.com",
    "referer": "https://www.hymasynthesis.com/",
    "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
}


@tool
async def search_hyma(chemical_name: str) -> str:
    """Search for products from Hyma Synthesis by chemical name. Returns matching products with catalog numbers. Use get_hyma_product_details with the Catalog Number to get pricing and stock."""
    chemical_name = chemical_name.strip()
    if not chemical_name:
        return "Error: chemical_name is required"

    try:
        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            resp = await client.post(
                "https://hymasynthesis.com/webservices/api/Values/GetProductsBasedOnChemicalName",
                data={"ChemicalName": chemical_name},
                headers=HYMA_HEADERS,
            )

            if resp.status_code != 200:
                return f"Search failed: HTTP {resp.status_code}"

            products = resp.json()
            if not products:
                return f"No products found for '{chemical_name}' in Hyma Synthesis catalog."

            search_url = f"{HYMA_BASE_URL}/search?q={quote(chemical_name)}"

            results = []
            for idx, product in enumerate(products, 1):
                catalog_no = product.get("CatalogNo") or product.get("catalogNo") or product.get("Catalog_No")
                item_name = product.get("ItemName") or product.get("itemName") or product.get("Item_Name", "")
                cas_number = product.get("CAS") or product.get("cas", "")
                hsn_code = product.get("HSNCode") or product.get("hsnCode", "")
                group_name = product.get("GroupName") or product.get("groupName", "")

                if not catalog_no:
                    continue

                product_url = f"{HYMA_BASE_URL}/product/{quote(catalog_no)}"

                info = f"**Product {idx}**\n"
                info += f"**Item Name:** {item_name}\n"
                info += f"**Catalog Number (ItemCode):** {catalog_no}\n"
                if cas_number:
                    info += f"**CAS Number:** {cas_number}\n"
                if hsn_code:
                    info += f"**HSN Code:** {hsn_code}\n"
                if group_name:
                    info += f"**Group:** {group_name}\n"
                info += "**Brand:** HYMA\n"
                info += f"**Source:** [Hyma Synthesis - {catalog_no}]({product_url})\n"
                results.append(info)

            if not results:
                return f"Found products for '{chemical_name}' but could not extract Catalog Numbers."

            text = f"**Hyma Synthesis Products for '{chemical_name}' (Found {len(results)} products):**\n"
            text += f"**Search URL:** [{HYMA_BASE_URL}]({search_url})\n\n"
            text += "\n".join(results)
            text += "\n\n*Use get_hyma_product_details with the Catalog Number (ItemCode) to get stock, price, and specifications.*"
            return text

    except httpx.TimeoutException:
        return "Search request timed out. Please try again."
    except Exception as e:
        return f"Error during Hyma search: {e}"


@tool
async def get_hyma_product_details(item_code: str) -> str:
    """Get detailed product information from Hyma Synthesis including stock, price, pack size, CAS, purity, and specifications. Requires the ItemCode (catalog number) from search_hyma."""
    item_code = item_code.strip()
    if not item_code:
        return "Error: item_code is required"

    try:
        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            stock_resp = await client.get(
                "https://hymasynthesis.com/webservices/api/Values/GetWebStockItemMstBasedOnId",
                params={"ItemCode": item_code},
                headers=HYMA_HEADERS,
            )
            spec_resp = await client.get(
                "https://hymasynthesis.com/webservices/api/Values/GetProductSpecificationOnCatalogNo",
                params={"ItemCode": item_code},
                headers=HYMA_HEADERS,
            )

            stock_data = stock_resp.json() if stock_resp.status_code == 200 else {}
            spec_data = spec_resp.json() if spec_resp.status_code == 200 else {}

            if not stock_data and not spec_data:
                return f"No product details found for ItemCode '{item_code}'."

            product_url = f"{HYMA_BASE_URL}/product/{quote(item_code)}"

            info = "**Hyma Synthesis Product Details**\n\n"
            info += f"**Brand:** HYMA\n"
            info += f"**Catalog Number (ItemCode):** {item_code}\n"
            info += f"**Source:** [Hyma Synthesis - {item_code}]({product_url})\n\n"

            if stock_data:
                item_info = stock_data.get("Item", [])
                if item_info:
                    item = item_info[0]
                    info += f"**Product Name:** {item.get('ItemName', item.get('itemName', 'N/A'))}\n"
                    info += f"**CAS Number:** {item.get('CAS', item.get('cas', 'N/A'))}\n"
                    info += f"**Stockable:** {item.get('Stockable', item.get('stockable', 'N/A'))}\n"
                    info += f"**Active:** {item.get('Active', item.get('active', 'N/A'))}\n\n"

                prod_det = stock_data.get("ProdDet", [])
                if prod_det:
                    info += "**Available Pack Sizes & Pricing:**\n\n"
                    for idx, pack in enumerate(prod_det, 1):
                        pack_size = pack.get("PackSize", pack.get("packSize", ""))
                        price = pack.get("Price", pack.get("price", ""))
                        qty = pack.get("Qty", pack.get("qty", ""))
                        qty_a = pack.get("QtyA", pack.get("qtyA", ""))
                        pack_code = pack.get("PackCode", pack.get("packCode", ""))
                        gst_tax = pack.get("GSTTAX", pack.get("gsttax", ""))

                        info += f"**Pack {idx}:**\n"
                        if pack_code:
                            info += f"  - Pack Code: {pack_code}\n"
                        if pack_size:
                            info += f"  - Pack Size: {pack_size}\n"
                        if price:
                            info += f"  - Price: ₹{price}\n"
                        if qty or qty_a:
                            info += f"  - Stock Quantity: {qty if qty else qty_a}\n"
                        if gst_tax:
                            info += f"  - GST: {gst_tax}%\n"
                        info += "\n"

            if spec_data:
                spec = spec_data[0] if isinstance(spec_data, list) and spec_data else spec_data if isinstance(spec_data, dict) else {}
                if spec:
                    info += "**Specifications:**\n"
                    cas = spec.get("CASNo") or spec.get("CAS_No") or spec.get("CASNumber")
                    if cas:
                        info += f"  - CAS Number: {cas}\n"
                    purity = spec.get("Purity") or spec.get("purity")
                    if purity:
                        info += f"  - Purity: {purity}\n"
                    formula = spec.get("MolecularFormula") or spec.get("Molecular_Formula")
                    if formula:
                        info += f"  - Molecular Formula: {formula}\n"
                    weight = spec.get("MolecularWeight") or spec.get("Molecular_Weight")
                    if weight:
                        info += f"  - Molecular Weight: {weight}\n"

            return info

    except httpx.TimeoutException:
        return "Request timed out. Please try again."
    except Exception as e:
        return f"Error getting Hyma product details: {e}"
