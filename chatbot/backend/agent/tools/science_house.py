"""Science House vendor tool: search the Science House knowledge base (no web scraping)."""
from langchain_core.tools import tool


@tool
async def search_science_house(search_term: str) -> str:
    """Search the Science House vendor knowledge base (ingested documents) by search term. Returns relevant chunks from the KB."""
    search_term = search_term.strip()
    if not search_term:
        return "Error: search_term is required"

    from knowledge_base import get_kb_id_by_vendor_name, hybrid_search

    kb_id = await get_kb_id_by_vendor_name("Science House")
    if not kb_id:
        kb_id = await get_kb_id_by_vendor_name("The Science House")
    if not kb_id:
        return "The Science House knowledge base is not set up or has no documents. Create a KB for vendor 'Science House' and ingest documents first."

    chunks = await hybrid_search(kb_id, search_term, top_k=20)
    if not chunks:
        return f"No relevant documents found in the Science House knowledge base for '{search_term}'."

    header = f"**Science House (Knowledge Base) results for '{search_term}':**\n\n"
    return header + "\n---\n".join(chunks)
