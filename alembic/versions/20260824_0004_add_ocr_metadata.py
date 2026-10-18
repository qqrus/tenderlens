"""Add document OCR extraction metadata.

Revision ID: 20260824_0004
Revises: 20260816_0003
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260824_0004"
down_revision: str | None = "20260816_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("extraction_method", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("ocr_page_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_check_constraint(
        "non_negative_ocr_page_count",
        "documents",
        "ocr_page_count >= 0",
    )
    op.create_check_constraint(
        "valid_extraction_method",
        "documents",
        "extraction_method IS NULL OR extraction_method IN ('native', 'ocr', 'mixed')",
    )
    op.execute("UPDATE documents SET extraction_method = 'native' WHERE status = 'ready'")


def downgrade() -> None:
    op.drop_constraint("valid_extraction_method", "documents", type_="check")
    op.drop_constraint("non_negative_ocr_page_count", "documents", type_="check")
    op.drop_column("documents", "ocr_page_count")
    op.drop_column("documents", "extraction_method")
