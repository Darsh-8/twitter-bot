"""Upsert the MVP RSS source registry into the database.

Usage: python scripts/seed_sources.py
"""

import asyncio

from sqlalchemy import select

from newsbot.adapters.persistence.db import session_scope
from newsbot.adapters.persistence.models_orm import SourceORM
from newsbot.adapters.sources.source_registry import MVP_RSS_SOURCES


async def seed() -> None:
    registry_names = {entry["name"] for entry in MVP_RSS_SOURCES}
    async with session_scope() as session:
        for entry in MVP_RSS_SOURCES:
            existing = await session.execute(select(SourceORM).where(SourceORM.name == entry["name"]))
            row = existing.scalar_one_or_none()
            if row is None:
                session.add(SourceORM(**entry))
                print(f"created source: {entry['name']}")
            else:
                row.url = entry["url"]
                row.category = entry["category"]
                row.trust_weight = entry["trust_weight"]
                row.source_type = entry["source_type"]
                row.is_active = True
                print(f"updated source: {entry['name']}")

        all_sources = await session.execute(select(SourceORM))
        for row in all_sources.scalars().all():
            if row.name not in registry_names and row.is_active:
                row.is_active = False
                print(f"deactivated source (no longer in registry): {row.name}")


if __name__ == "__main__":
    asyncio.run(seed())
