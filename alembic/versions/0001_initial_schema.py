"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 384


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "sources",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("source_type", sa.String(32), nullable=False, server_default="rss"),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("trust_weight", sa.Float, server_default="1.0"),
        sa.Column("is_active", sa.Boolean, server_default=sa.true()),
        sa.Column("last_polled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "stories",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("canonical_title", sa.Text, nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column("source_count", sa.Integer, server_default="1"),
        sa.Column("confidence_score", sa.Float, server_default="0.0"),
        sa.Column("importance_score", sa.Float, server_default="0.0"),
        sa.Column("status", sa.String(32), server_default="pending"),
        sa.Column("is_breaking", sa.Boolean, server_default=sa.false()),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_stories_status", "stories", ["status"])
    op.create_index("ix_stories_created_at", "stories", ["created_at"])
    op.execute(
        "CREATE INDEX ix_stories_embedding ON stories USING ivfflat (embedding vector_cosine_ops) "
        "WITH (lists = 100)"
    )

    op.create_table(
        "raw_articles",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "source_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.id"), nullable=False
        ),
        sa.Column("external_id", sa.String(512), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column(
            "story_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("stories.id"), nullable=True
        ),
        sa.Column("raw_payload", sa.JSON, nullable=True),
        sa.UniqueConstraint("source_id", "external_id", name="uq_source_external_id"),
    )
    op.create_index("ix_raw_articles_published_at", "raw_articles", ["published_at"])
    op.execute(
        "CREATE INDEX ix_raw_articles_embedding ON raw_articles USING ivfflat (embedding vector_cosine_ops) "
        "WITH (lists = 100)"
    )

    op.create_table(
        "story_sources",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "story_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("stories.id"), nullable=False
        ),
        sa.Column(
            "raw_article_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("raw_articles.id"),
            nullable=False,
        ),
        sa.Column("similarity_score", sa.Float, server_default="1.0"),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "tweets",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "story_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("stories.id"), nullable=False
        ),
        sa.Column("tweet_text", sa.Text, nullable=False),
        sa.Column("tweet_style", sa.String(64), nullable=True),
        sa.Column("is_dry_run", sa.Boolean, server_default=sa.true()),
        sa.Column("x_tweet_id", sa.String(64), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(32), server_default="pending_post"),
        sa.Column("failure_reason", sa.Text, nullable=True),
        sa.Column("retry_count", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "rejections",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "story_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("stories.id"), nullable=True
        ),
        sa.Column(
            "raw_article_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("raw_articles.id"),
            nullable=True,
        ),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("reason_code", sa.String(32), nullable=False),
        sa.Column("detail", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_type", sa.String(32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(32), server_default="success"),
        sa.Column("stats", sa.JSON, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("pipeline_runs")
    op.drop_table("rejections")
    op.drop_table("tweets")
    op.drop_table("story_sources")
    op.drop_index("ix_raw_articles_embedding", table_name="raw_articles")
    op.drop_index("ix_raw_articles_published_at", table_name="raw_articles")
    op.drop_table("raw_articles")
    op.drop_index("ix_stories_embedding", table_name="stories")
    op.drop_index("ix_stories_created_at", table_name="stories")
    op.drop_index("ix_stories_status", table_name="stories")
    op.drop_table("stories")
    op.drop_table("sources")
