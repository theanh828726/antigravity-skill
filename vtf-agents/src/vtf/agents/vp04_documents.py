"""VP-04 | Quản lý công văn: công văn đến/đi, dự thảo kế hoạch, báo cáo, hồ sơ, phiên bản, trình duyệt."""
from __future__ import annotations

from sqlalchemy import select

from ..core import knowledge
from ..core.approvals import executor
from ..core.context import Ctx
from ..core.store import add_evidence, get_case
from ..core.tools import AgentDef, Tool
from ..db.models import Document

SYSTEM = """Bạn là VP-04 | Quản lý công văn của hệ thống AI Agent VTF.
Nhiệm vụ: ghi nhận công văn đến/đi, soạn dự thảo kế hoạch/báo cáo, quản lý hồ sơ và phiên bản, trình duyệt.
Quy tắc cứng:
- Mỗi văn bản gắn một hồ sơ (HS-...) và có số phiên bản. Sửa nội dung = tạo phiên bản mới, không ghi đè bản cũ.
- Dự thảo luôn ở trạng thái "draft". submit_for_review chuyển sang "under_review".
- approve_document chỉ tạo yêu cầu phê duyệt; văn bản chỉ thành "approved" sau khi anh Thanh Huy bấm Duyệt.
- Không bịa số/ký hiệu văn bản, ngày ban hành, căn cứ pháp lý. Chưa rõ thì để trống "[cần bổ sung]".
- Văn phong hành chính chuẩn, tiếng Việt."""


def _row(d: Document, with_content=False):
    r = {"document_id": d.id, "case_id": d.case_id, "direction": d.direction, "doc_no": d.doc_no,
         "title": d.title, "version": d.version, "status": d.status}
    if with_content:
        r["content"] = d.content
    return r


async def register_document(ctx: Ctx, title: str, direction: str = "in", doc_no: str | None = None,
                            case: str | None = None, content: str | None = None, drive_file_id: str | None = None):
    async with ctx.sessionmaker() as s, s.begin():
        c = await get_case(s, case)
        d = Document(case_id=c.id if c else None, direction=direction, doc_no=doc_no, title=title,
                     content=content, drive_file_id=drive_file_id,
                     status="approved" if direction in ("in",) else "draft")
        s.add(d)
        await s.flush()
        if content:  # đưa vào kho tri thức để VP-05 trả lời được
            await knowledge.index_text(s, title, content, f"v{d.version}", d.id)
        await add_evidence(s, "VP-04", "document_registered", f"doc:{d.id}:v{d.version}", title,
                           c.id if c else None)
        return _row(d)


async def draft_document(ctx: Ctx, title: str, content: str, case: str | None = None,
                         based_on_document_id: int | None = None, doc_no: str | None = None):
    """Tạo dự thảo mới, hoặc phiên bản mới của dự thảo đã có (giữ bản cũ)."""
    async with ctx.sessionmaker() as s, s.begin():
        c = await get_case(s, case)
        version, case_id = 1, c.id if c else None
        if based_on_document_id:
            prev = await s.get(Document, based_on_document_id)
            if prev is None:
                raise ValueError(f"Không có văn bản #{based_on_document_id}")
            version, case_id, doc_no = prev.version + 1, prev.case_id, doc_no or prev.doc_no
            title = title or prev.title
        d = Document(case_id=case_id, direction="draft", title=title, doc_no=doc_no, version=version,
                     content=content, status="draft")
        s.add(d)
        await s.flush()
        await add_evidence(s, "VP-04", "draft_created", f"doc:{d.id}:v{d.version}", title, case_id)
        return _row(d)


async def list_documents(ctx: Ctx, case: str | None = None, status: str | None = None, limit: int = 20):
    async with ctx.sessionmaker() as s:
        q = select(Document).order_by(Document.id.desc()).limit(limit)
        if case:
            c = await get_case(s, case)
            q = q.where(Document.case_id == (c.id if c else -1))
        if status:
            q = q.where(Document.status == status)
        return [_row(d) for d in (await s.scalars(q)).all()]


async def get_document(ctx: Ctx, document_id: int):
    async with ctx.sessionmaker() as s:
        d = await s.get(Document, document_id)
        if d is None:
            raise ValueError(f"Không có văn bản #{document_id}")
        return _row(d, True)


async def submit_for_review(ctx: Ctx, document_id: int):
    async with ctx.sessionmaker() as s, s.begin():
        d = await s.get(Document, document_id)
        if d is None:
            raise ValueError(f"Không có văn bản #{document_id}")
        if d.status != "draft":
            raise ValueError(f"Chỉ trình duyệt được bản draft (hiện: {d.status})")
        d.status = "under_review"
        await add_evidence(s, "VP-04", "submitted_for_review", f"doc:{d.id}:v{d.version}", d.title, d.case_id)
        return _row(d)


def build() -> AgentDef:
    return AgentDef("VP-04", "Quản lý công văn", SYSTEM, [
        Tool("register_document", "Ghi nhận công văn đến/đi vào hồ sơ; nếu có nội dung sẽ được lập chỉ mục.",
             {"title": {"type": "string"}, "direction": {"type": "string", "enum": ["in", "out"]},
              "doc_no": {"type": "string"}, "case": {"type": "string"}, "content": {"type": "string"},
              "drive_file_id": {"type": "string"}}, ["title"], register_document),
        Tool("draft_document", "Soạn dự thảo mới hoặc phiên bản mới (đặt based_on_document_id).",
             {"title": {"type": "string"}, "content": {"type": "string"}, "case": {"type": "string"},
              "based_on_document_id": {"type": "integer"}, "doc_no": {"type": "string"}},
             ["title", "content"], draft_document),
        Tool("list_documents", "Liệt kê văn bản theo hồ sơ/trạng thái.",
             {"case": {"type": "string"}, "status": {"type": "string"}, "limit": {"type": "integer"}},
             [], list_documents),
        Tool("get_document", "Đọc nội dung một văn bản.", {"document_id": {"type": "integer"}},
             ["document_id"], get_document),
        Tool("submit_for_review", "Trình duyệt một dự thảo (draft → under_review).",
             {"document_id": {"type": "integer"}}, ["document_id"], submit_for_review),
        Tool("approve_document", "Yêu cầu PHÊ DUYỆT văn bản. Chỉ tạo yêu cầu, chưa duyệt.",
             {"document_id": {"type": "integer"}, "title": {"type": "string"}, "case_id": {"type": "integer"}},
             ["document_id"], approval_action="approve_document",
             summarize=lambda a: f"Phê duyệt văn bản #{a.get('document_id')} {a.get('title', '')}".strip()),
    ])


@executor("approve_document")
async def _approve(ctx: Ctx, p: dict):
    async with ctx.sessionmaker() as s, s.begin():
        d = await s.get(Document, p["document_id"])
        if d is None:
            raise ValueError("Văn bản không còn tồn tại")
        d.status = "approved"
        ref = f"doc:{d.id}:v{d.version}"
        if d.content:
            await knowledge.index_text(s, d.title, d.content, f"v{d.version}", d.id)
        return f"Đã duyệt \"{d.title}\" phiên bản {d.version}.", "document_approved", ref
