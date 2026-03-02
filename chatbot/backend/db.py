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


async def ensure_indexes():
    try:
        await messages_col.create_index("conversation_id")
        await conversations_col.create_index([("updated_at", -1)])
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
) -> dict:
    doc = {
        "_id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
        "blocks": blocks or [],
        "created_at": datetime.now(timezone.utc),
    }
    await messages_col.insert_one(doc)
    await touch_conversation(conversation_id)
    return doc


async def get_messages(conversation_id: str) -> list[dict]:
    cursor = messages_col.find(
        {"conversation_id": conversation_id}
    ).sort("created_at", 1)
    results = []
    async for doc in cursor:
        results.append({
            "id": doc["_id"],
            "conversation_id": doc["conversation_id"],
            "role": doc["role"],
            "content": doc["content"],
            "blocks": doc.get("blocks", []),
            "created_at": doc["created_at"].isoformat() if isinstance(doc["created_at"], datetime) else doc["created_at"],
        })
    return results
