"""
This is the main entry point for the agent.
It defines the workflow graph, state, tools, nodes and edges.
"""

from typing import Any, List
import os
import httpx
from typing_extensions import Literal
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, BaseMessage
from langchain_core.runnables import RunnableConfig
from langchain.tools import tool
from langgraph.graph import StateGraph, END
from langgraph.types import Command
from langgraph.graph import MessagesState
from langgraph.prebuilt import ToolNode

class AgentState(MessagesState):
    """
    Here we define the state of the agent

    In this instance, we're inheriting from CopilotKitState, which will bring in
    the CopilotKitState fields. We're also adding a custom field, `language`,
    which will be used to set the language of the agent.
    """
    proverbs: List[str] = []
    tools: List[Any]
    # your_custom_agent_state: str = ""




@tool
def search_design_documents(query: str):
    """
    Search and retrieve furniture design documentation (drawings, specifications,
    bill of materials, materials/finishes, dimensions, joinery, hardware, etc.)
    from the RAG service and return the most relevant results.

    Args:
        query: The search or question text to send to the RAG service.

    The request is sent as a POST with JSON body {"query": query} to a
    configured URL. By default, it uses the provided ngrok endpoint with
    fixed query parameters. You can override the full URL via the
    RAG_SEARCH_URL environment variable.

    Guidance for the assistant:
    - Use this tool whenever the user asks about furniture design documents,
      technical details, drawings, standards, or needs citations from source
      documents.
    - Return concise, directly useful answers grounded in retrieved content.
    """
    url = os.getenv(
        "RAG_SEARCH_URL",
        "http://localhost:8001/search?document_id=63d8da51-3d68-4278-88b5-84f7b3d26c81&collection_name=documents&limit=10&text_only=false&llm_format=false&llm_provider=openai&score_threshold=0.2&type=image",
    )

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                url,
                headers={"Content-Type": "application/json"},
                json={"query": query},
            )
            response.raise_for_status()
            # Prefer JSON if available; fall back to text
            try:
                result = response.json()
            except Exception:
                result = response.text
            print("[tool:search_design_documents] response:", result)
            return result
    except httpx.HTTPError as http_err:
        error_result = {"error": f"HTTP error from RAG service: {str(http_err)}"}
        print("[tool:search_design_documents] response:", error_result)
        return error_result
    except Exception as err:
        error_result = {"error": f"Unexpected error calling RAG service: {str(err)}"}
        print("[tool:search_design_documents] response:", error_result)
        return error_result


# Register RAG tool in backend tools so model tool calls are handled server-side
backend_tools = [
    search_design_documents,
    # your_tool_here
]

# Extract tool names from backend_tools for comparison
backend_tool_names = [tool.name for tool in backend_tools]


async def chat_node(state: AgentState, config: RunnableConfig) -> Command[Literal["tool_node", "__end__"]]:
    """
    Standard chat node based on the ReAct design pattern. It handles:
    - The model to use (and binds in CopilotKit actions and the tools defined above)
    - The system prompt
    - Getting a response from the model
    - Handling tool calls

    For more about the ReAct design pattern, see:
    https://www.perplexity.ai/search/react-agents-NcXLQhreS0WDzpVaS4m9Cg
    """

    # 1. Define the model
    model = ChatOpenAI(model="gpt-4o")

    # 2. Bind the tools to the model
    model_with_tools = model.bind_tools(
        [
            *state.get("tools", []), # bind tools defined by ag-ui
            *backend_tools,
            # your_tool_here
        ],

        # 2.1 Disable parallel tool calls to avoid race conditions,
        #     enable this for faster performance if you want to manage
        #     the complexity of running tool calls in parallel.
        parallel_tool_calls=False,
    )

    # 3. Define the system message by which the chat model will be run
    system_message = SystemMessage(
        content=(
            "You are a helpful furniture design documentation assistant. "
            "If the user asks anything about documentation (e.g., drawings, specifications, bill of materials, materials/finishes, dimensions, joinery, hardware, standards, or implementation details), you must call the 'search_design_documents' tool before answering. "
            "Do not answer documentation questions from memory; always ground responses using the tool's results and provide concise citations or summaries. "
            f"Proverbs/context: {state.get('proverbs', [])}."
        )
    )

    # 4. Run the model to generate a response
    response = await model_with_tools.ainvoke([
        system_message,
        *state["messages"],
    ], config)

    # only route to tool node if tool is not in the tools list
    if route_to_tool_node(response):
        print("routing to tool node")
        return Command(
            goto="tool_node",
            update={
                "messages": [response],
            }
        )

    # 5. We've handled all tool calls, so we can end the graph.
    return Command(
        goto=END,
        update={
            "messages": [response],
        }
    )

def route_to_tool_node(response: BaseMessage):
    """
    Route to tool node if any tool call in the response matches a backend tool name.
    """
    tool_calls = getattr(response, "tool_calls", None)
    if not tool_calls:
        return False

    for tool_call in tool_calls:
        if tool_call.get("name") in backend_tool_names:
            return True
    return False

# Define the workflow graph
workflow = StateGraph(AgentState)
workflow.add_node("chat_node", chat_node)
workflow.add_node("tool_node", ToolNode(tools=backend_tools))
workflow.add_edge("tool_node", "chat_node")
workflow.set_entry_point("chat_node")

graph = workflow.compile()
