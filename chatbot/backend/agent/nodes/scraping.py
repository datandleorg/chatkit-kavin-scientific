import asyncio
from agent.state import WorkflowState
from agent.tools.hyma import search_hyma
from agent.tools.spectrochem import search_spectrochem
from agent.tools.glosil import search_glosil
from agent.tools.science_house import search_science_house
from agent.tools.tci import search_tci


async def scraping_node(state: WorkflowState) -> dict:
    """Search all five vendors for each chemical in parallel (Hyma, Spectrochem, Glosil, Science House, TCI)."""
    chemicals = state.get("chemical_list", [])
    if not chemicals:
        return {"scraping_results": [], "error": "No chemicals to search"}

    all_results: list[dict] = []

    async def search_one(chemical: str) -> list:
        tasks = [
            search_hyma.ainvoke({"chemical_name": chemical}),
            search_spectrochem.ainvoke({"chemical_name": chemical}),
            search_glosil.ainvoke({"search_term": chemical}),
            search_science_house.ainvoke({"search_term": chemical}),
            search_tci.ainvoke({"search_term": chemical}),
        ]
        return await asyncio.gather(*tasks, return_exceptions=True)

    for chemical in chemicals:
        results = await search_one(chemical)
        for r in results:
            if isinstance(r, str):
                all_results.append({"chemical": chemical, "raw_result": r})
            elif isinstance(r, Exception):
                all_results.append({"chemical": chemical, "error": str(r)})

    return {"scraping_results": all_results}
