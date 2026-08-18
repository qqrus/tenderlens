from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tenderlens.db.base import Base
from tenderlens.domain.documents import DocumentStatus


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100), default="application/pdf")
    sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(
        String(20),
        default=DocumentStatus.UPLOADED.value,
        index=True,
    )
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    pages: Mapped[list["DocumentPage"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('uploaded', 'processing', 'ready', 'failed')",
            name="valid_status",
        ),
        CheckConstraint("size_bytes > 0", name="positive_size"),
    )


class DocumentPage(Base):
    __tablename__ = "document_pages"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    page_number: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    char_count: Mapped[int] = mapped_column(Integer)

    document: Mapped[Document] = relationship(back_populates="pages")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="page",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint("document_id", "page_number"),
        CheckConstraint("page_number > 0", name="positive_page_number"),
        CheckConstraint("char_count >= 0", name="non_negative_char_count"),
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    page_id: Mapped[UUID] = mapped_column(
        ForeignKey("document_pages.id", ondelete="CASCADE"), index=True
    )
    page_number: Mapped[int] = mapped_column(Integer)
    chunk_index: Mapped[int] = mapped_column(Integer)
    start_char: Mapped[int] = mapped_column(Integer)
    end_char: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)

    document: Mapped[Document] = relationship(back_populates="chunks")
    page: Mapped[DocumentPage] = relationship(back_populates="chunks")

    __table_args__ = (
        UniqueConstraint("document_id", "page_number", "chunk_index"),
        CheckConstraint("page_number > 0", name="positive_page_number"),
        CheckConstraint("chunk_index >= 0", name="non_negative_chunk_index"),
        CheckConstraint("start_char >= 0", name="non_negative_start_char"),
        CheckConstraint("end_char > start_char", name="valid_char_range"),
        Index("ix_document_chunks_document_page", "document_id", "page_number"),
    )
