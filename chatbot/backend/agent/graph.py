from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from agent.state import ChatState, WorkflowState
from agent.tools import ALL_TOOLS

SYSTEM_PROMPT = (
    "You are a chemical procurement assistant for a scientific lab. "
    "Help users find chemicals, compare prices across vendors "
    "(Hyma Synthesis, Spectrochem, Glosil Scientific, TCI Chemicals), and generate procurement reports.\n\n"
    "You have 9 tools — a search tool and a details tool for each vendor, plus a quote table tool:\n"
    "- search_hyma → get_hyma_product_details (by ItemCode/catalog number)\n"
    "- search_spectrochem → get_spectrochem_product_details (by product_id + product_name)\n"
    "- search_glosil → get_glosil_product_details (by product_id + product_url)\n"
    "- search_tci → get_tci_product_details (by product_url)\n"
    "- prepare_quote_table → renders an editable procurement table in the UI\n\n"
    "When a user asks about a chemical:\n"
    "1. First, use the 4 search tools in parallel to find matching products across all vendors.\n"
    "2. Then, call the detail tools for the most relevant results to get pricing and stock.\n"
    "3. Call prepare_quote_table with the structured product list. DO NOT write a markdown table.\n"
    "   Each product object must have: name, catalog_no, hsn, brand, unit (pack size), rate (price as number, 0 if POR/unknown), discount (default 0), qty (default 1), gst_percent, source_url.\n"
    "   Extract numeric prices from the tool results (e.g. '₹9,900' → 9900). Use 0 for POR/unknown prices.\n"
    "4. After the table tool call, write a brief recommendation as plain text.\n\n"
    "IMPORTANT — Citation requirements:\n"
    "- Every tool result includes a **Source:** field with a URL. Include source_url in each row passed to prepare_quote_table.\n"
    "- In your recommendation text, mention vendor names as markdown links.\n\n"
    "Be concise and helpful. If the user uploads files, extracted chemicals are provided in context."
)


def _build_chat_graph() -> StateGraph:
    """Build the LangGraph ReAct agent for chat with tool calling."""
    llm = ChatAnthropic(
        model=CLAUDE_MODEL,
        api_key=ANTHROPIC_API_KEY,
        max_tokens=4096,
        streaming=True,
    )
    llm_with_tools = llm.bind_tools(ALL_TOOLS)

    tool_node = ToolNode(ALL_TOOLS)

    def chatbot(state: ChatState):
        system = SYSTEM_PROMPT
        if state.get("context"):
            system += f"\n\nSession context:\n{state['context']}"

        messages = state["messages"]
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=system)] + list(messages)

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
