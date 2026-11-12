from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Base(DeclarativeBase):
    pass


class Case(Base):
    """Hồ sơ công việc chung - trục dữ liệu mà mọi Agent cùng dùng."""

    __tablename__ = "cases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)  # HS-2026-0001
    title: Mapped[str] = mapped_column(String(300))
    branch: Mapped[str] = mapped_column(String(8), default="VP")  # VP/HV/SK/TT
    owner: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default="open")  # open/done/cancelled
    source: Mapped[str | None] = mapped_column(String(200))  # email/công văn/lịch/lệnh Telegram
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    tasks: Mapped[list["Task"]] = relationship(back_populates="case")


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id"))
    title: Mapped[str] = mapped_column(String(300))
    assignee: Mapped[str | None] = mapped_column(String(120))
    due_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="todo")  # todo/doing/done/blocked
    progress: Mapped[int] = mapped_column(Integer, default=0)  # 0-100
    note: Mapped[str | None] = mapped_column(Text)
    kpi_tag: Mapped[str | None] = mapped_column(String(60))
    remind_chat_id: Mapped[int | None] = mapped_column(BigInteger)
    last_reminded_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    case: Mapped[Case | None] = relationship(back_populates="tasks")


class Document(Base):
    """Công văn / dự thảo / báo cáo, có phiên bản và trạng thái trình duyệt."""

    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id"))
    direction: Mapped[str] = mapped_column(String(8), default="in")  # in=đến, out=đi, draft=dự thảo
    doc_no: Mapped[str | None] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(300))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft/under_review/approved
    file_path: Mapped[str | None] = mapped_column(String(500))
    drive_file_id: Mapped[str | None] = mapped_column(String(200))
    content: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class KnowledgeChunk(Base):
    """Đoạn tài liệu đã lập chỉ mục cho VP-05 (hỏi đáp có trích nguồn)."""

    __tablename__ = "knowledge_chunks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(300), index=True)  # tên tài liệu
    version: Mapped[str | None] = mapped_column(String(40))
    ref: Mapped[str | None] = mapped_column(String(120))  # trang / điều / mục
    text: Mapped[str] = mapped_column(Text)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))


class Approval(Base):
    """Mọi hành động có tác động ra ngoài đều đi qua đây trước khi thực thi."""

    __tablename__ = "approvals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id"))
    agent: Mapped[str] = mapped_column(String(16))
    action: Mapped[str] = mapped_column(String(60))  # send_email / create_event / ...
    summary: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/approved/rejected/executed/failed
    chat_id: Mapped[int | None] = mapped_column(BigInteger)
    decided_by: Mapped[int | None] = mapped_column(BigInteger)
    result: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    decided_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class Evidence(Base):
    """Bằng chứng: URL / mã thư / mã sự kiện / phiên bản tài liệu / kết quả thực thi."""

    __tablename__ = "evidence"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id"))
    agent: Mapped[str] = mapped_column(String(16))
    kind: Mapped[str] = mapped_column(String(40))
    ref: Mapped[str | None] = mapped_column(String(500))
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor: Mapped[str] = mapped_column(String(60))  # telegram:<id> hoặc agent
    event: Mapped[str] = mapped_column(String(60))
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ChatMessage(Base):
    """Ngữ cảnh hội thoại ngắn hạn theo chat Telegram (chỉ lưu văn bản)."""

    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    role: Mapped[str] = mapped_column(String(12))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
