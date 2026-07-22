"""add council votes

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-22

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "council_votes",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "story_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("stories.id"), nullable=False
        ),
        sa.Column("persona_name", sa.String(64), nullable=False),
        sa.Column("approve", sa.Boolean, nullable=False),
        sa.Column("reasoning", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_council_votes_story_id", "council_votes", ["story_id"])


def downgrade() -> None:
    op.drop_index("ix_council_votes_story_id", table_name="council_votes")
    op.drop_table("council_votes")
