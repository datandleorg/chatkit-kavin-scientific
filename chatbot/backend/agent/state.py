from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class ChatState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    session_id: str
    context: str
    model_id: str


class WorkflowState(TypedDict, total=False):
    step: str
    session_id: str
    file_paths: list[str]
    chemical_list: list[str]
    scraping_results: list[dict]
    final_report: str
    error: str
