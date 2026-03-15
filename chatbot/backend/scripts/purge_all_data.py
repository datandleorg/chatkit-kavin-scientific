#!/usr/bin/env python3
"""
Purge all application data: MongoDB collections (conversations, messages, saved_quotes)
and optionally the uploads directory.

Run from the backend directory:
  uv run python scripts/purge_all_data.py
  uv run python scripts/purge_all_data.py --uploads   # also clear uploads directory
"""

import argparse
import asyncio
import shutil
import sys
from pathlib import Path

# Allow importing config from parent directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient

from config import MONGODB_URI, MONGODB_DB, UPLOAD_DIR


async def purge_mongo():
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[MONGODB_DB]
    collections = [
        ("conversations", db["conversations"]),
        ("messages", db["messages"]),
        ("saved_quotes", db["saved_quotes"]),
        
    ]
    for name, col in collections:
        result = await col.delete_many({})
        print(f"  {name}: deleted {result.deleted_count} document(s)")


def purge_uploads():
    if not UPLOAD_DIR.exists():
        print(f"  uploads: directory {UPLOAD_DIR} does not exist, skip")
        return
    count = 0
    for p in UPLOAD_DIR.iterdir():
        if p.is_dir():
            shutil.rmtree(p)
            count += 1
        else:
            p.unlink()
            count += 1
    print(f"  uploads: removed {count} item(s) under {UPLOAD_DIR}")


async def main():
    parser = argparse.ArgumentParser(description="Purge all tables and clear data")
    parser.add_argument(
        "--uploads",
        action="store_true",
        help="Also clear the uploads directory (stored files)",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmation prompt",
    )
    args = parser.parse_args()

    print("This will delete ALL data from:")
    print("  - MongoDB collections: conversations, messages, saved_quotes")
    if args.uploads:
        print(f"  - Uploads directory: {UPLOAD_DIR}")
    if not args.yes:
        try:
            r = input("Proceed? [y/N]: ").strip().lower()
            if r not in ("y", "yes"):
                print("Aborted.")
                return
        except EOFError:
            print("Aborted (no TTY).")
            return

    print("Purging MongoDB...")
    await purge_mongo()
    if args.uploads:
        print("Purging uploads...")
        purge_uploads()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
