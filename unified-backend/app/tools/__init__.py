"""
Tools module for Kavin Scientific Agent
Contains all function tools that the agent can use directly
"""
from app.tools.quote_tools import generate_quote_for_products
from app.tools.search_tools import file_search
from app.tools.product_tools import (
    search_hyma,
    get_hyma_product_details,
    search_spectrochem,
    get_spectrochem_product_details,
    search_glosil,
    get_glosil_product_details,
    search_tci,
    get_tci_product_details,
)

__all__ = [
    "generate_quote_for_products",
    "file_search",
    "search_hyma",
    "get_hyma_product_details",
    "search_spectrochem",
    "get_spectrochem_product_details",
    "search_glosil",
    "get_glosil_product_details",
    "search_tci",
    "get_tci_product_details",
]
