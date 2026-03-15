from agent.tools.hyma import search_hyma, get_hyma_product_details
from agent.tools.spectrochem import search_spectrochem, get_spectrochem_product_details
from agent.tools.glosil import search_glosil, get_glosil_product_details
from agent.tools.science_house import search_science_house
from agent.tools.tci import search_tci, get_tci_product_details
from agent.tools.quote_table import prepare_quote_table

ALL_TOOLS = [
    search_hyma,
    get_hyma_product_details,
    search_spectrochem,
    get_spectrochem_product_details,
    search_glosil,
    get_glosil_product_details,
    search_science_house,
    search_tci,
    get_tci_product_details,
    prepare_quote_table,
]

__all__ = [
    "search_hyma",
    "get_hyma_product_details",
    "search_spectrochem",
    "get_spectrochem_product_details",
    "search_glosil",
    "get_glosil_product_details",
    "search_science_house",
    "search_tci",
    "get_tci_product_details",
    "prepare_quote_table",
    "ALL_TOOLS",
]
