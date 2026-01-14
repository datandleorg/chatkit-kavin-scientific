"""
ChatKit Server implementation leveraging the official chatkit server abstraction.
This integrates the Agent with function tools (direct function calls, no MCP subprocess)
with ChatKitServer so the frontend receives standard ChatKit thread/item events.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime
import uuid
from typing import Any, AsyncIterator, Dict, List

from agents import Agent, RunConfig, Runner
from agents.model_settings import ModelSettings
from openai.types.shared import Reasoning
from openai.types.responses.response_reasoning_summary_text_delta_event import ResponseReasoningSummaryTextDeltaEvent
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

from app.chatkit.agent import AGENT_INSTRUCTIONS, create_agent

logger = logging.getLogger(__name__)


class MemoryStore(Store[dict]):
    """Simple in-memory store compatible with ChatKit Store interface."""

    def __init__(self):
        self.threads: Dict[str, ThreadMetadata] = {}
        self.items: Dict[str, List[ThreadItem]] = {}

    async def load_thread(self, thread_id: str, context: dict) -> ThreadMetadata:
        if thread_id not in self.threads:
            # Auto-create thread if it doesn't exist (for compatibility with ChatKit framework)
            logger.warning(f"Thread {thread_id} not found, auto-creating it")
            thread = ThreadMetadata(
                id=thread_id,
                created_at=datetime.utcnow(),
                status={"type": "active"},
                metadata={},
                title="Untitled",
            )
            await self.save_thread(thread, context)
            self.items[thread_id] = []  # Initialize empty items list
            return thread
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
    """ChatKitServer-based implementation using Agent with direct function tools."""

    def __init__(self):
        store = MemoryStore()
        super().__init__(store)
        self.store = store
        self.agent: Agent | None = None
        self.converter = SimpleThreadItemConverter()

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

    async def _ensure_agent(self, model: str = "gpt-5"):
        """Ensure agent is initialized. Reuses existing if available."""
        # Check if agent needs to be recreated for different model
        if self.agent is not None:
            # If model changed, recreate agent
            if hasattr(self.agent, 'model') and self.agent.model != model:
                logger.info(f"Model changed from {self.agent.model} to {model}, recreating agent...")
                self.agent = None
            else:
                logger.debug("Agent already initialized, reusing...")
                return
            
        try:
            logger.info("=" * 60)
            logger.info(f"🤖 Creating Agent with Function Tools (model: {model})...")
            self.agent = create_agent(model=model)
            logger.info("✅ Agent initialized successfully")
            logger.info("=" * 60)
        except Exception as e:
            logger.error(f"❌ Error initializing agent: {str(e)}", exc_info=True)
            self.agent = None
            logger.info("=" * 60)
            raise

    async def cleanup(self):
        """Clean up agent. Safe to call multiple times."""
        if self.agent is not None:
            logger.info("🧹 Cleaning up agent...")
            self.agent = None
            logger.info("✅ Agent reference cleared")

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
        # Ensure agent is initialized (reuse if exists)
        logger.info(f"Processing response for thread: {thread.id}")
        
        # Get model from context (set by API handler)
        model = context.get("model", "gpt-5")
        logger.info(f"Using model: {model}")
        
        try:
            logger.info("Ensuring agent is initialized...")
            await self._ensure_agent(model=model)
        except Exception as e:
            logger.error(f"Error ensuring agent is initialized, attempting cleanup and retry: {str(e)}")
            # If initialization fails, cleanup and try once more
            await self.cleanup()
            await self._ensure_agent(model=model)

        items_page = await self.store.load_thread_items(thread.id, None, 50, "desc", context)
        items = list(reversed(items_page.data))
        agent_input = await self.converter.to_agent_input(items)

        agent_context = AgentContext(
            thread=thread,
            store=self.store,
            request_context=context,
        )

        # Use the same model settings as the agent (which includes store=True for thinking tokens)
        # Note: For thinking tokens to work, you MUST use a model that supports them (o1, o3, or gpt-5 with reasoning)
        model = context.get("model", "gpt-5")
        logger.info(f"🔍 Using model: {model} for thinking tokens")
        
        # Configure reasoning settings for thinking tokens
        # This enables reasoning summaries that can be extracted as thinking tokens
        reasoning_config = Reasoning(
            effort="low",
            summary="concise"  # Options: "none", "concise", "detailed"
        )
        
        result = Runner.run_streamed(
            self.agent,  # type: ignore[arg-type]
            agent_input,
            context=agent_context,
            run_config=RunConfig(
                model_settings=ModelSettings(
                    store=True,
                    reasoning=reasoning_config
                )
            ),
        )

        # Extract reasoning/thinking tokens from the raw stream events
        # We need to create a wrapper that extracts reasoning while also allowing stream_agent_response to work
        thinking_deltas = []
        thinking_text_by_item = {}  # Group deltas by item_id
        
        logger.info("🔍 Setting up reasoning token extraction...")
        
        # Create a wrapper class that extracts reasoning tokens from stream_events()
        class ReasoningExtractor:
            """Wrapper that extracts reasoning tokens while preserving result interface"""
            def __init__(self, result):
                self._result = result
                self._thinking_deltas = []
            
            async def stream_events(self):
                """Stream events and extract reasoning tokens"""
                async for raw_event in self._result.stream_events():
                    # Check for reasoning summary text delta events
                    if hasattr(raw_event, 'type') and raw_event.type == "raw_response_event":
                        if hasattr(raw_event, 'data'):
                            event_data = raw_event.data
                            # Check if it's a ResponseReasoningSummaryTextDeltaEvent
                            event_type = getattr(event_data, 'type', None)
                            if event_type == 'response.reasoning_summary_text.delta' or isinstance(event_data, ResponseReasoningSummaryTextDeltaEvent):
                                # Extract the delta text
                                delta_text = getattr(event_data, 'delta', None) or getattr(event_data, 'text', None)
                                item_id = getattr(event_data, 'item_id', None)
                                
                                if delta_text:
                                    self._thinking_deltas.append(delta_text)
                                    thinking_deltas.append(delta_text)
                                    if item_id:
                                        if item_id not in thinking_text_by_item:
                                            thinking_text_by_item[item_id] = []
                                        thinking_text_by_item[item_id].append(delta_text)
                                    logger.debug(f"📝 Reasoning delta: {delta_text[:50]}...")
                    
                    # Always yield the event so stream_agent_response can process it
                    yield raw_event
            
            @property
            def thinking_deltas(self):
                return self._thinking_deltas
        
        # Create the wrapper
        reasoning_extractor = ReasoningExtractor(result)
        
        # Create a result-like object that uses our wrapper
        class WrappedResult:
            def __init__(self, extractor, original_result):
                self._extractor = extractor
                self._original = original_result
            
            def stream_events(self):
                return self._extractor.stream_events()
            
            # Delegate other attributes to original result
            def __getattr__(self, name):
                return getattr(self._original, name)
        
        wrapped_result = WrappedResult(reasoning_extractor, result)
        
        # Track if we've seen a workflow event and need to inject thinking
        workflow_event_seen = False
        workflow_item_id = None
        
        # Now pass the wrapped result to stream_agent_response
        # It will call stream_events() which will extract reasoning while also yielding events
        async for event in stream_agent_response(agent_context, wrapped_result):
            # Log all ChatKit events for debugging
            if hasattr(event, 'type'):
                event_type = str(event.type)
                logger.debug(f"📤 ChatKit event: {event_type}")
                
                # Check workflow events
                if 'workflow' in event_type.lower() or 'reasoning' in event_type.lower():
                    logger.info(f"🔧 Workflow/Reasoning event: {event_type}")
                    workflow_event_seen = True
                    
                    if hasattr(event, 'item'):
                        item = event.item
                        logger.info(f"   Item type: {getattr(item, 'type', 'unknown')}")
                        if hasattr(item, 'id'):
                            workflow_item_id = item.id
                        
                        if hasattr(item, 'workflow'):
                            workflow = item.workflow
                            logger.info(f"   Workflow type: {getattr(workflow, 'type', 'unknown')}")
                            if hasattr(workflow, 'tasks'):
                                tasks = workflow.tasks
                                logger.info(f"   Tasks: {len(tasks) if tasks else 0}")
                                if tasks:
                                    logger.info(f"   ✅ Workflow has {len(tasks)} tasks")
                                    logger.info(f"   First task preview: {str(tasks[0])[:100]}...")
                                else:
                                    # If we have thinking text but no tasks, try to populate them
                                    if thinking_deltas:
                                        full_thinking_text = "".join(thinking_deltas)
                                        logger.info(f"   📝 Populating workflow with thinking text ({len(full_thinking_text)} chars)...")
                                        
                                        # Split thinking text into logical chunks (tasks)
                                        if '\n\n' in full_thinking_text:
                                            task_texts = [t.strip() for t in full_thinking_text.split('\n\n') if t.strip()]
                                        else:
                                            # Split by sentences
                                            task_texts = [t.strip() for t in re.split(r'(?<=[.!?])\s+', full_thinking_text) if t.strip() and len(t.strip()) > 10]
                                        
                                        # Try to populate tasks
                                        try:
                                            if hasattr(workflow, '__dict__'):
                                                workflow.__dict__['tasks'] = [{"content": text} for text in task_texts[:20]]
                                                logger.info(f"   ✅ Populated workflow with {len(task_texts)} tasks")
                                            elif hasattr(workflow, 'tasks'):
                                                workflow.tasks = [{"content": text} for text in task_texts[:20]]
                                                logger.info(f"   ✅ Populated workflow with {len(task_texts)} tasks")
                                            else:
                                                logger.warning(f"   ⚠️  Could not modify workflow.tasks - object may be immutable")
                                        except Exception as e:
                                            logger.error(f"   ❌ Error populating workflow tasks: {e}")
                                    else:
                                        logger.warning(f"   ⚠️  Workflow has empty tasks array")
                                        logger.warning(f"   No thinking tokens were extracted")
            
            yield event
        
        # After streaming completes, log summary
        if thinking_deltas:
            full_thinking_text = "".join(thinking_deltas)
            logger.info(f"✅ Extracted {len(thinking_deltas)} reasoning deltas ({len(full_thinking_text)} chars total)")
        elif workflow_event_seen:
            logger.warning("⚠️  Workflow event was created but no thinking tokens were found")
            logger.warning("   Make sure reasoning is enabled in ModelSettings with Reasoning config")

    async def to_message_content(self, _input: Attachment):
        raise RuntimeError("Attachments are not supported.")

