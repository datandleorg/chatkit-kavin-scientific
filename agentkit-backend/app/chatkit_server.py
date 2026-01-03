"""
ChatKit Server implementation leveraging the official chatkit server abstraction.
This integrates the existing MCP-backed Agent with ChatKitServer so the frontend
receives standard ChatKit thread/item events.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
import uuid
from typing import Any, AsyncIterator, Dict, List

from agents import Agent, RunConfig, Runner
from agents.model_settings import ModelSettings
from chatkit.agents import AgentContext, ThreadItemConverter, stream_agent_response
from chatkit.server import ChatKitServer
from chatkit.store import Store, NotFoundError
from chatkit.types import (
    Attachment,
    Page,
    ThreadItem,
    ThreadMetadata,
    UserMessageItem,
)
from openai.types.responses import ResponseInputTextParam

from app.agent import AGENT_INSTRUCTIONS, create_mcp_server

logger = logging.getLogger(__name__)


class MemoryStore(Store[dict]):
    """Simple in-memory store compatible with ChatKit Store interface."""

    def __init__(self):
        self.threads: Dict[str, ThreadMetadata] = {}
        self.items: Dict[str, List[ThreadItem]] = {}

    async def load_thread(self, thread_id: str, context: dict) -> ThreadMetadata:
        if thread_id not in self.threads:
            raise NotFoundError(f"Thread {thread_id} not found")
        return self.threads[thread_id]

    async def save_thread(self, thread: ThreadMetadata, context: dict) -> None:
        self.threads[thread.id] = thread

    async def load_threads(
        self, limit: int, after: str | None, order: str, context: dict
    ) -> Page[ThreadMetadata]:
        threads = list(self.threads.values())
        threads = sorted(threads, key=lambda t: t.created_at, reverse=order == "desc")
        data = threads[:limit]
        has_more = len(threads) > limit
        after_cursor = data[-1].id if has_more else None
        return Page(data=data, has_more=has_more, after=after_cursor)

    async def load_thread_items(
        self, thread_id: str, after: str | None, limit: int, order: str, context: dict
    ) -> Page[ThreadItem]:
        items = self.items.get(thread_id, [])
        items = sorted(items, key=lambda i: i.created_at, reverse=order == "desc")
        data = items[:limit]
        has_more = len(items) > limit
        after_cursor = data[-1].id if has_more else None
        return Page(data=data, has_more=has_more, after=after_cursor)

    async def add_thread_item(self, thread_id: str, item: ThreadItem, context: dict) -> None:
        self.items.setdefault(thread_id, []).append(item)

    async def save_item(self, thread_id: str, item: ThreadItem, context: dict) -> None:
        await self.add_thread_item(thread_id, item, context)

    async def load_item(self, thread_id: str, item_id: str, context: dict) -> ThreadItem:
        for it in self.items.get(thread_id, []):
            if it.id == item_id:
                return it
        raise KeyError(item_id)

    async def delete_thread(self, thread_id: str, context: dict) -> None:
        self.threads.pop(thread_id, None)
        self.items.pop(thread_id, None)

    async def delete_thread_item(self, thread_id: str, item_id: str, context: dict) -> None:
        if thread_id in self.items:
            self.items[thread_id] = [i for i in self.items[thread_id] if i.id != item_id]

    async def save_attachment(self, attachment: Attachment, context: dict) -> None:
        raise NotImplementedError()

    async def load_attachment(self, attachment_id: str, context: dict) -> Attachment:
        raise NotImplementedError()

    async def delete_attachment(self, attachment_id: str, context: dict) -> None:
        raise NotImplementedError()


class SimpleThreadItemConverter(ThreadItemConverter):
    """Minimal converter to turn thread items into agent input."""

    async def to_agent_input(self, items: list[ThreadItem]) -> list[dict]:
        inputs: list[dict] = []
        for item in items:
            if getattr(item, "type", "") not in {"user_message", "assistant_message"}:
                continue
            role = "user" if item.type == "user_message" else "assistant"
            # combine text parts
            text_parts: list[str] = []
            if hasattr(item, "content"):
                for c in item.content:
                    # content may be a pydantic model with attributes
                    c_type = getattr(c, "type", None) or (c.get("type") if isinstance(c, dict) else None)
                    c_text = getattr(c, "text", None)
                    if c_type in ("input_text", "output_text"):
                        if c_text:
                            text_parts.append(c_text)
            text = " ".join(tp for tp in text_parts if tp)
            if text:
                # User messages use input_text, assistant messages use output_text
                content_type = "input_text" if role == "user" else "output_text"
                inputs.append(
                    {
                        "type": "message",
                        "role": role,
                        "content": [ResponseInputTextParam(type=content_type, text=text)],
                    }
                )
        return inputs


class KavinScientificServer(ChatKitServer[dict[str, Any]]):
    """ChatKitServer-based implementation using the MCP-backed Agent."""

    def __init__(self):
        store = MemoryStore()
        super().__init__(store)
        self.store = store
        self.agent: Agent | None = None
        self.converter = SimpleThreadItemConverter()
        self.mcp_server = None

    def list_threads(self) -> dict:
        """Return threads in ChatKit list shape."""
        entries = []
        for t in self.store.threads.values():
            entries.append(
                {
                    "title": getattr(t, "title", None) or "Untitled",
                    "id": t.id,
                    "created_at": t.created_at.isoformat() if hasattr(t.created_at, "isoformat") else str(t.created_at),
                    "status": {"type": "active"},
                    "metadata": getattr(t, "metadata", {}) or {},
                    "items": {"data": [], "has_more": False},
                }
            )
        entries.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        return {"data": entries, "has_more": False}

    async def create_thread(self, title: str | None = None) -> Dict[str, Any]:
        thread = ThreadMetadata(
            id=f"thr_{uuid.uuid4().hex[:8]}",
            created_at=datetime.utcnow(),
            status={"type": "active"},
            metadata={},
            title=title,
        )
        await self.store.save_thread(thread, {})
        return {
            "id": thread.id,
            "title": thread.title or "Untitled",
            "created_at": thread.created_at.isoformat(),
            "status": thread.status,
            "metadata": thread.metadata,
            "items": {"data": [], "has_more": False},
        }

    async def _ensure_agent(self):
        if self.agent is None:
            try:
                logger.info("Initializing MCP server and agent...")
                self.mcp_server = create_mcp_server()
                logger.info("MCP server instance created, entering context manager...")
                await self.mcp_server.__aenter__()
                logger.info("MCP server context entered successfully")
                
                logger.info("Creating Agent with MCP server...")
                self.agent = Agent(
                    name="Kavin Scientific Assistant",
                    instructions=AGENT_INSTRUCTIONS,
                    model="gpt-5",
                    model_settings=ModelSettings(store=True),
                    mcp_servers=[self.mcp_server],
                )
                logger.info("Agent and MCP server initialized successfully")
            except Exception as e:
                logger.error(f"Error initializing MCP server or agent: {str(e)}", exc_info=True)
                raise

    async def cleanup(self):
        if self.mcp_server is not None:
            try:
                logger.info("Cleaning up MCP server...")
                await self.mcp_server.__aexit__(None, None, None)
                logger.info("MCP server cleaned up successfully")
            except Exception as e:
                logger.error(f"Error during MCP server cleanup: {str(e)}", exc_info=True)
            finally:
                self.mcp_server = None
                self.agent = None
                logger.info("Agent and MCP server references cleared")

    async def ensure_thread(self, thread_id: str) -> ThreadMetadata:
        """Ensure a thread exists in the store; create if missing."""
        try:
            return await self.store.load_thread(thread_id, {})
        except Exception:
            thread = ThreadMetadata(
                id=thread_id,
                created_at=datetime.utcnow(),
                status={"type": "active"},
                metadata={},
                title="Untitled",
            )
            await self.store.save_thread(thread, {})
            self.store.items[thread_id] = []
            return thread

    async def respond(
        self,
        thread: ThreadMetadata,
        input_user_message: UserMessageItem | None,
        context: dict[str, Any],
    ) -> AsyncIterator[Any]:
        # Recreate agent/MCP each request to avoid stale/closed sessions
        logger.info(f"Processing response for thread: {thread.id}")
        await self.cleanup()
        logger.info("Ensuring agent and MCP server are initialized...")
        await self._ensure_agent()

        items_page = await self.store.load_thread_items(thread.id, None, 50, "desc", context)
        items = list(reversed(items_page.data))
        agent_input = await self.converter.to_agent_input(items)

        agent_context = AgentContext(
            thread=thread,
            store=self.store,
            request_context=context,
        )

        result = Runner.run_streamed(
            self.agent,  # type: ignore[arg-type]
            agent_input,
            context=agent_context,
            run_config=RunConfig(model_settings=ModelSettings()),
        )

        async for event in stream_agent_response(agent_context, result):
            yield event

    async def to_message_content(self, _input: Attachment):
        raise RuntimeError("Attachments are not supported.")

