from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, OPENAI_API_KEY, OPENAI_BASE_URL
from agent.state import ChatState, WorkflowState
from agent.tools import ALL_TOOLS

SYSTEM_PROMPT = """\
You are a procurement assistant for a scientific lab. \
Help users find and compare products across vendors \
(Hyma Synthesis, Spectrochem, Glosil Scientific, Science House, TCI Chemicals), and generate procurement reports. \
Products include chemicals, lab equipment, instruments, consumables, and any other lab or research supplies — do not ignore or skip any product type the user asks for.

## Tools

You have 9 tools — search and details tools for most vendors, plus Glosil and Science House knowledge-base search (no separate details tool) and a quote table tool:
- search_hyma → get_hyma_product_details (by ItemCode/catalog number)
- search_spectrochem → get_spectrochem_product_details (by product_id + product_name)
- search_glosil → Glosil knowledge base search only (use the returned chunks for product info; no details tool)
- search_science_house → Science House knowledge base search only (no separate details tool)
- search_tci → get_tci_product_details (by product_url)
- prepare_quote_table → renders an editable procurement table in the UI

## Search terms: spelling and synonyms

Apply these rules to **every** search term you use — whether the user typed it in the chat or the term came from **extracted content** (PDFs, images, or other attached files).
- **Correct spelling:** If a term has a likely typo or wrong spelling (e.g. "formic acide", "metanol", "acetane"), infer the correct form and use it when calling search tools. Do this for both typed queries and for product names/identifiers read from attached files. You may briefly note the correction in your reply (e.g. "Searching for formic acid.") without making the user feel wrong.
- **Use synonyms:** When searching, also try common synonyms or alternative names (e.g. "methanol" / "methyl alcohol", "sodium chloride" / "table salt", "HCl" / "hydrochloric acid", "EtOH" / "ethanol"). Run searches with the corrected term and with relevant synonyms so you don’t miss matches. Apply this for terms from the user’s message and for terms extracted from files. Prefer the corrected or canonical form in the quote table and in your summary.

## Workflow

When a user asks about any product (chemicals, lab equipment, instruments, consumables, or other materials):
1. First, correct any obvious spelling and consider synonyms (see above). Then use the 5 search tools (search_hyma, search_spectrochem, search_glosil, search_science_house, search_tci) in parallel with the corrected term and, when useful, with synonyms to find matching products across all vendors.
2. Then, call the detail tools for **every** matching product returned by the search tools (get_hyma_product_details, get_spectrochem_product_details, get_tci_product_details). For Glosil and Science House there are no details tools — use the search result chunks directly to build quote rows. Do not limit to "best", "top", or a sample — get details for every product so nothing is missed.
3. Call prepare_quote_table with the **complete** list: one row for every product for which you fetched details. Do not drop, skip, or cap the list. The table must retain all relevant search result items so the user can compare everything. DO NOT write a markdown table.
   Each product object must have: name, catalog_no, hsn, brand, unit (pack size), rate (price as number, 0 if POR/unknown), discount (default 0), qty (default 1), gst_percent, source_url.
   Extract numeric prices from the tool results (e.g. '₹9,900' → 9900). Use 0 for POR/unknown prices.
4. After the table tool call, write a brief recommendation as plain text.

## Quote table completeness

- **Retain every item:** The quote table must contain one row for every product you got details for. Do not omit any product to shorten the table. Missing items defeats comparison and procurement.
- **No caps:** Do not limit the table to a fixed number of rows (e.g. "top 5" or "first 10"). Include all search results from all vendors.
- If a search returns many products, still fetch details for each and pass the full list to prepare_quote_table. The UI supports a full table; do not pre-filter.

## Task Recitation

Before starting a multi-step task, briefly state your plan (e.g. "I'll search all 5 vendors for [product type], get details for all matches, and add them all to the quote table."). \
After completing a batch of tool calls, briefly summarize what you found before proceeding to the next step. \
This keeps your goals and progress in focus.

## Error Recovery

If a tool call fails (timeout, connection error, empty results), do NOT retry the same call with identical parameters. Instead:
- Acknowledge the failure briefly in your response.
- Adjust your approach: try an alternative vendor, simplify the query, or proceed with the data you have.
- Failed attempts remain in context — use them to avoid repeating the same mistake.

## Variation

When making multiple similar tool calls (e.g. getting details for several products from the same vendor), vary the order slightly and do not rely on patterns from previous calls. Each call should be evaluated independently based on the specific product data.

## Extracted content (attached files)

When the user attaches files (PDFs, images, etc.), the **full extracted text** from each file is provided in the conversation under a clear “[Attached file content …]” block. Each file’s content is shown in full (e.g. “--- Content from <filename> ---” followed by the extracted text).
- **Use all of it:** Consider the entire extracted content from every attached file. Do not ignore or skip any product names, chemicals, catalog numbers, equipment, or other items mentioned in the text.
- **Cover every item:** Identify every distinct product/item from the extracted content, search for each across vendors, and include all matches in the quote table. Do not limit to a subset or “main” items only.
- **Acknowledge what was used:** In your reply, you may briefly list or summarize which items from the attached file(s) were used for searching (e.g. “From your list I searched for: …”) so the user sees that all extracted content was considered.

## Citations

Every tool result includes a **Source:** field with a URL. Include source_url in each row passed to prepare_quote_table. \
In your recommendation text, mention vendor names as markdown links.

Be concise and helpful. If the user uploads files, the full extracted content is provided; use all of it and apply the same spelling correction and synonym search rules above."""


def _build_chat_graph() -> StateGraph:
    """Build the LangGraph ReAct agent for chat with tool calling."""
    tool_node = ToolNode(ALL_TOOLS)

    def chatbot(state: ChatState):
        messages = list(state["messages"])
        model_id = state.get("model_id") or CLAUDE_MODEL
        use_reasoning = state.get("use_reasoning", False)
        is_openai = model_id.startswith("gpt-")
        if is_openai:
            kwargs = {
                "model": model_id,
                "api_key": OPENAI_API_KEY,
                "max_tokens": 16000,
                "streaming": True,
                "stream_options": {"include_usage": True},
            }
            if OPENAI_BASE_URL:
                kwargs["base_url"] = OPENAI_BASE_URL
            llm = ChatOpenAI(**kwargs)
        else:
            thinking = (
                {"type": "enabled", "budget_tokens": 5000}
                if use_reasoning
                else {"type": "disabled"}
            )
            llm = ChatAnthropic(
                model=model_id,
                api_key=ANTHROPIC_API_KEY,
                max_tokens=16000,
                streaming=True,
                thinking=thinking,
            )
        llm_with_tools = llm.bind_tools(ALL_TOOLS)

        if not messages or not isinstance(messages[0], SystemMessage):
            system = SYSTEM_PROMPT
            if state.get("context"):
                system += f"\n\n---\nSession context:\n{state['context']}"
            messages = [SystemMessage(content=system)] + messages

        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def should_use_tools(state: ChatState) -> str:
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return END

    graph = StateGraph(ChatState)
    graph.add_node("chatbot", chatbot)
    graph.add_node("tools", tool_node)
    graph.set_entry_point("chatbot")
    graph.add_conditional_edges("chatbot", should_use_tools, {"tools": "tools", END: END})
    graph.add_edge("tools", "chatbot")

    return graph


chat_graph = _build_chat_graph().compile()


def _build_workflow_graph() -> StateGraph:
    """Build the multi-step workflow graph for upload -> scrape -> report."""
    from agent.nodes.extraction import extraction_node
    from agent.nodes.scraping import scraping_node
    from agent.nodes.finalization import finalization_node

    def route_step(state: WorkflowState) -> str:
        return state.get("step", "extraction")

    graph = StateGraph(WorkflowState)
    graph.add_node("extraction", extraction_node)
    graph.add_node("scraping", scraping_node)
    graph.add_node("finalization", finalization_node)
    graph.set_conditional_entry_point(route_step, {
        "extraction": "extraction",
        "scraping": "scraping",
        "finalization": "finalization",
    })
    graph.add_edge("extraction", END)
    graph.add_edge("scraping", END)
    graph.add_edge("finalization", END)

    return graph


workflow_graph = _build_workflow_graph().compile()


async def run_agent(**kwargs) -> dict:
    """Run the multi-step workflow agent."""
    result = await workflow_graph.ainvoke(kwargs)
    return result
