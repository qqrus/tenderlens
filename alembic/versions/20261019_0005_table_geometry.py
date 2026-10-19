"""Add nullable geometry sidecar without reprocessing existing documents."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261019_0005"
down_revision: str | None = "20260824_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("table_geometry", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "table_geometry")
