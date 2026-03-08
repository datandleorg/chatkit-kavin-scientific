"""MongoDB service module for conversation and message persistence."""

import uuid
from datetime import datetime, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient

from config import MONGODB_URI, MONGODB_DB

client: AsyncIOMotorClient = AsyncIOMotorClient(MONGODB_URI)
db = client[MONGODB_DB]

conversations_col = db["conversations"]
messages_col = db["messages"]
saved_quotes_col = db["saved_quotes"]


async def ensure_indexes():
    try:
        await messages_col.create_index("conversation_id")
        await conversations_col.create_index([("updated_at", -1)])
        await saved_quotes_col.create_index([("created_at", -1)])
    except Exception:
        pass


async def create_conversation(title: str) -> dict:
    doc = {
        "_id": str(uuid.uuid4()),
        "title": title[:80] if title else "New conversation",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    await conversations_col.insert_one(doc)
    return doc


async def list_conversations(limit: int = 50) -> list[dict]:
    cursor = conversations_col.find(
        {}, {"_id": 1, "title": 1, "updated_at": 1}
    ).sort("updated_at", -1).limit(limit)
    results = []
    async for doc in cursor:
        results.append({
            "id": doc["_id"],
            "title": doc["title"],
            "updated_at": doc["updated_at"].isoformat() if isinstance(doc["updated_at"], datetime) else doc["updated_at"],
        })
    return results


async def get_conversation(conv_id: str) -> dict | None:
    doc = await conversations_col.find_one({"_id": conv_id})
    return doc


async def delete_conversation(conv_id: str):
    await messages_col.delete_many({"conversation_id": conv_id})
    await conversations_col.delete_one({"_id": conv_id})


async def update_conversation_title(conv_id: str, title: str):
    await conversations_col.update_one(
        {"_id": conv_id},
        {"$set": {"title": title[:80]}},
    )


async def update_conversation_summary(conv_id: str, summary: str, msg_count: int):
    await conversations_col.update_one(
        {"_id": conv_id},
        {"$set": {"summary": summary, "summary_msg_count": msg_count}},
    )


async def touch_conversation(conv_id: str):
    await conversations_col.update_one(
        {"_id": conv_id},
        {"$set": {"updated_at": datetime.now(timezone.utc)}},
    )


async def add_message(
    conversation_id: str,
    role: str,
    content: str,
    blocks: list[dict[str, Any]] | None = None,
    usage: dict[str, int] | None = None,
) -> dict:
    doc = {
        "_id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
        "blocks": blocks or [],
        "created_at": datetime.now(timezone.utc),
    }
    if usage:
        doc["usage"] = {k: v for k, v in usage.items() if v is not None}
    await messages_col.insert_one(doc)
    await touch_conversation(conversation_id)
    return doc


async def get_messages(conversation_id: str) -> list[dict]:
    cursor = messages_col.find(
        {"conversation_id": conversation_id}
    ).sort("created_at", 1)
    results = []
    async for doc in cursor:
        out = {
            "id": doc["_id"],
            "conversation_id": doc["conversation_id"],
            "role": doc["role"],
            "content": doc["content"],
            "blocks": doc.get("blocks", []),
            "created_at": doc["created_at"].isoformat() if isinstance(doc["created_at"], datetime) else doc["created_at"],
        }
        if "usage" in doc and doc["usage"]:
            out["usage"] = doc["usage"]
        results.append(out)
    return results


async def get_usage_aggregates() -> dict:
    """Return token usage aggregated by day and by conversation for dashboard."""
    pipeline_by_day = [
        {"$match": {"usage": {"$exists": True}, "usage.input_tokens": {"$exists": True}}},
        {
            "$project": {
                "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                "usage": 1,
            }
        },
        {
            "$group": {
                "_id": "$date",
                "input_tokens": {"$sum": "$usage.input_tokens"},
                "output_tokens": {"$sum": "$usage.output_tokens"},
                "total_tokens": {"$sum": "$usage.total_tokens"},
                "cache_tokens": {"$sum": "$usage.cache_tokens"},
                "message_count": {"$sum": 1},
            }
        },
        {"$sort": {"_id": 1}},
        {
            "$project": {
                "_id": 0,
                "date": "$_id",
                "input_tokens": 1,
                "output_tokens": 1,
                "total_tokens": 1,
                "cache_tokens": 1,
                "message_count": 1,
            }
        },
    ]
    cursor_by_day = messages_col.aggregate(pipeline_by_day)
    by_day = []
    async for doc in cursor_by_day:
        by_day.append({
            "date": doc["date"],
            "input_tokens": doc.get("input_tokens", 0),
            "output_tokens": doc.get("output_tokens", 0),
            "total_tokens": doc.get("total_tokens", 0),
            "cache_tokens": doc.get("cache_tokens", 0),
            "message_count": doc.get("message_count", 0),
        })
    totals = {
        "input_tokens": sum(d["input_tokens"] for d in by_day),
        "output_tokens": sum(d["output_tokens"] for d in by_day),
        "total_tokens": sum(d["total_tokens"] for d in by_day),
        "cache_tokens": sum(d["cache_tokens"] for d in by_day),
    }
    by_tool_calls = await _aggregate_tool_calls()
    return {
        "totals": totals,
        "by_day": by_day,
        "by_tool_calls": by_tool_calls,
    }


def _is_tool_failure(result: str | None) -> bool:
    if not result:
        return False
    lower = result.lower()
    return any(kw in lower for kw in ("error", "failed", "timeout"))


async def _aggregate_tool_calls() -> list[dict]:
    """Aggregate tool call counts by tool name with success/failure."""
    cursor = messages_col.find(
        {"blocks": {"$exists": True, "$ne": []}},
        {"blocks": 1},
    )
    agg: dict[str, dict[str, int]] = {}
    async for doc in cursor:
        for block in doc.get("blocks") or []:
            if block.get("type") != "tool":
                continue
            tc = block.get("toolCall") or {}
            name = tc.get("name") or "unknown"
            result = tc.get("result") or ""
            failed = _is_tool_failure(str(result))
            if name not in agg:
                agg[name] = {"success_count": 0, "failure_count": 0}
            if failed:
                agg[name]["failure_count"] += 1
            else:
                agg[name]["success_count"] += 1
    return [
        {"tool_name": name, "success_count": d["success_count"], "failure_count": d["failure_count"]}
        for name, d in sorted(agg.items(), key=lambda x: -(x[1]["success_count"] + x[1]["failure_count"]))
    ]


async def save_quote(
    conversation_id: str | None,
    file_name: str,
    rows: list[dict],
    message_prompt: str | None = None,
) -> dict:
    doc = {
        "_id": str(uuid.uuid4()),
        "conversation_id": conversation_id or "",
        "file_name": file_name if file_name.endswith(".xlsx") else f"{file_name}.xlsx",
        "rows": rows,
        "message_prompt": (message_prompt or "").strip() or None,
        "created_at": datetime.now(timezone.utc),
    }
    if doc["message_prompt"] is None:
        del doc["message_prompt"]
    await saved_quotes_col.insert_one(doc)
    return doc


async def list_saved_quotes(limit: int = 50) -> list[dict]:
    cursor = saved_quotes_col.find({}).sort("created_at", -1).limit(limit)
    results = []
    async for doc in cursor:
        results.append({
            "id": doc["_id"],
            "conversation_id": doc.get("conversation_id", ""),
            "file_name": doc.get("file_name", "quote.xlsx"),
            "rows_count": len(doc.get("rows") or []),
            "message_prompt": doc.get("message_prompt"),
            "created_at": doc["created_at"].isoformat() if isinstance(doc["created_at"], datetime) else doc["created_at"],
        })
    return results


async def get_saved_quote(quote_id: str) -> dict | None:
    doc = await saved_quotes_col.find_one({"_id": quote_id})
    return doc
