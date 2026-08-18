"""Add document ingestion tables.

Revision ID: 20260814_0002
Revises: 20260814_0001
Create Date: 2026-08-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260814_0002"
down_revision: str | None = "20260814_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('uploaded', 'processing', 'ready', 'failed')",
            name=op.f("ck_documents_valid_status"),
        ),
        sa.CheckConstraint("size_bytes > 0", name=op.f("ck_documents_positive_size")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
        sa.UniqueConstraint("sha256", name=op.f("uq_documents_sha256")),
    )
    op.create_index(op.f("ix_documents_sha256"), "documents", ["sha256"])
    op.create_index(op.f("ix_documents_status"), "documents", ["status"])

    op.create_table(
        "document_pages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "char_count >= 0", name=op.f("ck_document_pages_non_negative_char_count")
        ),
        sa.CheckConstraint("page_number > 0", name=op.f("ck_document_pages_positive_page_number")),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_document_pages_document_id_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_pages")),
        sa.UniqueConstraint(
            "document_id",
            "page_number",
            name=op.f("uq_document_pages_document_id"),
        ),
    )
    op.create_index(op.f("ix_document_pages_document_id"), "document_pages", ["document_id"])

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("page_id", sa.Uuid(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("start_char", sa.Integer(), nullable=False),
        sa.Column("end_char", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "chunk_index >= 0", name=op.f("ck_document_chunks_non_negative_chunk_index")
        ),
        sa.CheckConstraint(
            "end_char > start_char", name=op.f("ck_document_chunks_valid_char_range")
        ),
        sa.CheckConstraint("page_number > 0", name=op.f("ck_document_chunks_positive_page_number")),
        sa.CheckConstraint(
            "start_char >= 0", name=op.f("ck_document_chunks_non_negative_start_char")
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_document_chunks_document_id_documents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["page_id"],
            ["document_pages.id"],
            name=op.f("fk_document_chunks_page_id_document_pages"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_chunks")),
        sa.UniqueConstraint(
            "document_id",
            "page_number",
            "chunk_index",
            name=op.f("uq_document_chunks_document_id"),
        ),
    )
    op.create_index(op.f("ix_document_chunks_document_id"), "document_chunks", ["document_id"])
    op.create_index(
        "ix_document_chunks_document_page",
        "document_chunks",
        ["document_id", "page_number"],
    )
    op.create_index(op.f("ix_document_chunks_page_id"), "document_chunks", ["page_id"])


def downgrade() -> None:
    op.drop_table("document_chunks")
    op.drop_table("document_pages")
    op.drop_table("documents")
