"""VP-01 | Quản lý công việc: sổ việc chung, người phụ trách, thời hạn, tiến độ, nhắc việc, KPI."""
from __future__ import annotations

from sqlalchemy import func, select

from ..core.context import Ctx
from ..core.store import add_evidence, audit, create_case, get_case
from ..core.tools import AgentDef, Tool
from ..db.models import Case, Task

SYSTEM = """Bạn là VP-01 | Quản lý công việc của hệ thống AI Agent Liên đoàn Taekwondo Việt Nam (VTF).
Nhiệm vụ: lập và theo dõi sổ việc chung: người phụ trách, thời hạn, tiến độ, nhắc việc, dữ liệu KPI.
Quy tắc:
- Mỗi việc phải gắn với một hồ sơ (mã HS-YYYY-NNNN). Chưa có thì tạo hồ sơ trước, hoặc hỏi lại nếu mơ hồ.
- Thời hạn dùng ISO 8601 (múi giờ Việt Nam nếu không nói rõ). Không tự bịa người phụ trách hoặc hạn.
- Chỉ báo số liệu lấy từ công cụ; không ước đoán KPI.
- Trả lời ngắn gọn, tiếng Việt, nêu mã hồ sơ/mã việc."""


def _task_row(t: Task) -> dict:
    return {"id": t.id, "case_id": t.case_id, "title": t.title, "assignee": t.assignee,
            "due_at": t.due_at.isoformat() if t.due_at else None, "status": t.status,
            "progress": t.progress, "note": t.note}


async def create_case_tool(ctx: Ctx, title: str, branch: str = "VP", owner: str | None = None,
                           source: str | None = None):
    async with ctx.sessionmaker() as s, s.begin():
        c = await create_case(s, title, branch, owner, source or f"telegram:{ctx.user_id}")
        await add_evidence(s, "VP-01", "case_created", c.code, title, c.id)
        await audit(s, "agent:VP-01", "case_created", {"code": c.code})
        return {"case_id": c.id, "code": c.code, "title": c.title}


async def list_cases_tool(ctx: Ctx, status: str = "open", limit: int = 20):
    async with ctx.sessionmaker() as s:
        rows = (await s.scalars(select(Case).where(Case.status == status)
                                .order_by(Case.id.desc()).limit(limit))).all()
        return [{"case_id": c.id, "code": c.code, "title": c.title, "branch": c.branch,
                 "owner": c.owner, "status": c.status} for c in rows]


async def create_task_tool(ctx: Ctx, title: str, case: str | None = None, assignee: str | None = None,
                           due_at: str | None = None, kpi_tag: str | None = None, note: str | None = None):
    async with ctx.sessionmaker() as s, s.begin():
        c = await get_case(s, case)
        if case and c is None:
            raise ValueError(f"Không tìm thấy hồ sơ {case}")
        t = Task(case_id=c.id if c else None, title=title, assignee=assignee,
                 due_at=ctx.parse_dt(due_at) if due_at else None, kpi_tag=kpi_tag, note=note,
                 remind_chat_id=ctx.chat_id or None)
        s.add(t)
        await s.flush()
        await add_evidence(s, "VP-01", "task_created", f"task:{t.id}", title, c.id if c else None)
        return _task_row(t)


async def update_task_tool(ctx: Ctx, task_id: int, status: str | None = None, progress: int | None = None,
                           assignee: str | None = None, due_at: str | None = None, note: str | None = None):
    async with ctx.sessionmaker() as s, s.begin():
        t = await s.get(Task, task_id)
        if t is None:
            raise ValueError(f"Không có việc #{task_id}")
        if status:
            t.status = status
            if status == "done":
                t.progress = 100
        if progress is not None:
            t.progress = max(0, min(100, progress))
        if assignee:
            t.assignee = assignee
        if due_at:
            t.due_at, t.last_reminded_at = ctx.parse_dt(due_at), None
        if note:
            t.note = note
        await add_evidence(s, "VP-01", "task_updated", f"task:{t.id}", f"status={t.status} progress={t.progress}",
                           t.case_id)
        return _task_row(t)


async def list_tasks_tool(ctx: Ctx, assignee: str | None = None, status: str | None = None,
                          case: str | None = None, overdue_only: bool = False, limit: int = 30):
    async with ctx.sessionmaker() as s:
        q = select(Task).order_by(Task.due_at.is_(None), Task.due_at).limit(limit)
        if assignee:
            q = q.where(Task.assignee.ilike(f"%{assignee}%"))
        if status:
            q = q.where(Task.status == status)
        else:
            q = q.where(Task.status != "done")
        if case:
            c = await get_case(s, case)
            q = q.where(Task.case_id == (c.id if c else -1))
        if overdue_only:
            q = q.where(Task.due_at < ctx.now())
        return [_task_row(t) for t in (await s.scalars(q)).all()]


async def kpi_tool(ctx: Ctx):
    async with ctx.sessionmaker() as s:
        total = await s.scalar(select(func.count()).select_from(Task)) or 0
        done = await s.scalar(select(func.count()).select_from(Task).where(Task.status == "done")) or 0
        overdue = await s.scalar(select(func.count()).select_from(Task)
                                 .where(Task.status != "done", Task.due_at < ctx.now())) or 0
        by_assignee = (await s.execute(
            select(Task.assignee, func.count()).where(Task.status != "done").group_by(Task.assignee))).all()
        return {"tong_viec": total, "hoan_thanh": done, "qua_han": overdue,
                "ty_le_hoan_thanh_%": round(100 * done / total, 1) if total else None,
                "dang_mo_theo_nguoi": {a or "(chưa giao)": n for a, n in by_assignee}}


def build() -> AgentDef:
    return AgentDef("VP-01", "Quản lý công việc", SYSTEM, [
        Tool("create_case", "Tạo hồ sơ công việc chung mới, trả về mã HS-YYYY-NNNN.",
             {"title": {"type": "string"}, "branch": {"type": "string", "enum": ["VP", "HV", "SK", "TT"]},
              "owner": {"type": "string", "description": "Người chủ trì"}, "source": {"type": "string"}},
             ["title"], create_case_tool),
        Tool("list_cases", "Liệt kê hồ sơ theo trạng thái (open/done/cancelled).",
             {"status": {"type": "string"}, "limit": {"type": "integer"}}, [], list_cases_tool),
        Tool("create_task", "Tạo việc, gắn hồ sơ (mã HS hoặc id), người phụ trách, hạn (ISO 8601).",
             {"title": {"type": "string"}, "case": {"type": "string"}, "assignee": {"type": "string"},
              "due_at": {"type": "string"}, "kpi_tag": {"type": "string"}, "note": {"type": "string"}},
             ["title"], create_task_tool),
        Tool("update_task", "Cập nhật trạng thái/tiến độ/người phụ trách/hạn/ghi chú của việc.",
             {"task_id": {"type": "integer"}, "status": {"type": "string", "enum": ["todo", "doing", "done", "blocked"]},
              "progress": {"type": "integer"}, "assignee": {"type": "string"}, "due_at": {"type": "string"},
              "note": {"type": "string"}}, ["task_id"], update_task_tool),
        Tool("list_tasks", "Liệt kê việc chưa xong (mặc định), lọc theo người, trạng thái, hồ sơ, quá hạn.",
             {"assignee": {"type": "string"}, "status": {"type": "string"}, "case": {"type": "string"},
              "overdue_only": {"type": "boolean"}, "limit": {"type": "integer"}}, [], list_tasks_tool),
        Tool("kpi_summary", "Số liệu KPI công việc: tổng, hoàn thành, quá hạn, theo người phụ trách.",
             {}, [], kpi_tool),
    ])
