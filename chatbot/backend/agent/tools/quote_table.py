import json
from langchain_core.tools import tool


@tool
def prepare_quote_table(products: list[dict], file_name: str = "") -> str:
    """Render an editable procurement quote table in the UI.

    Call this AFTER gathering product details from vendors. Pass the COMPLETE list: every product for which you fetched details must appear as one row. Do not omit, cap, or sample — retain all relevant search result items so nothing is missed. Omitting products is incorrect.
    Each item in products should have these fields (use empty string or 0 for missing values):
      - name: str          (product name)
      - catalog_no: str    (catalog / product code)
      - hsn: str           (HSN code, if known)
      - brand: str         (vendor / brand name)
      - unit: str          (pack size, e.g. "25g", "100ml")
      - rate: float        (price per unit in INR, 0 if POR/unknown)
      - discount: float    (discount percentage, default 0)
      - qty: int           (quantity, default 1)
      - gst_percent: float (GST percentage, e.g. 18)
      - source_url: str    (vendor page URL for citation)

    Optional file_name: suggest a short, descriptive filename for the quote export (e.g. "Lab_chemicals_quote", "Formic_acid_vendors"). Based on the products or user request. Omit .xlsx; it will be added. If empty, a default name is used.
    """
    if not products:
        return json.dumps([])

    cleaned = []
    for p in products:
        cleaned.append({
            "name": str(p.get("name", "")),
            "catalog_no": str(p.get("catalog_no", "")),
            "hsn": str(p.get("hsn", "")),
            "brand": str(p.get("brand", "")),
            "unit": str(p.get("unit", "")),
            "rate": float(p.get("rate", 0) or 0),
            "discount": float(p.get("discount", 0) or 0),
            "qty": int(p.get("qty", 1) or 1),
            "gst_percent": float(p.get("gst_percent", 0) or 0),
            "source_url": str(p.get("source_url", "")),
        })

    return json.dumps(cleaned)
