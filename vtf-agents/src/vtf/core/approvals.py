from __future__ import annotations

import datetime as dt
from typing import Any, Awaitable, Callable

from ..db.models import Approval
from .context import Ctx
from .store import add_evidence, audit

# action -> executor(ctx, payload) -> (kết quả hiển thị, evidence_kind, evidence_ref)
Executor = Callable[[Ctx, dict[str, Any]], Awaitable[tuple[str, str, str]]]
EXECUTORS: dict[str, Executor] = {}


def executor(action: str):
    def deco(fn: Executor) -> Executor:
        EXECUTORS[action] = fn
        return fn
    return deco


async def request_approval(ctx: Ctx, agent: str, action: str, summary: str, payload: dict,
                           case_id: int | None = None) -> int:
    async with ctx.sessionmaker() as s, s.begin():
        a = Approval(agent=agent, action=action, summary=summary, payload=payload,
                     case_id=case_id if isinstance(case_id, int) else None, chat_id=ctx.chat_id)
        s.add(a)
        await s.flush()
        await audit(s, f"agent:{agent}", "approval_requested", {"id": a.id, "action": action})
        ctx.pending_approval_ids.append(a.id)
        return a.id


async def decide(ctx: Ctx, approval_id: int, approve: bool) -> tuple[str, str]:
    """Quyết định một yêu cầu. Chỉ owner được duyệt. Trả về (trạng thái, nội dung thông báo)."""
    if ctx.role != "owner":
        return "denied", "Chỉ Grand Master mới có quyền phê duyệt."
    async with ctx.sessionmaker() as s, s.begin():
        a = await s.get(Approval, approval_id, with_for_update=True)
        if a is None:
            return "missing", f"Không tìm thấy yêu cầu #{approval_id}."
        if a.status != "pending":  # chống bấm đúp / thực thi hai lần
            return a.status, f"Yêu cầu #{approval_id} đã ở trạng thái {a.status}."
        a.decided_by, a.decided_at = ctx.user_id, dt.datetime.now(dt.timezone.utc)
        if not approve:
            a.status = "rejected"
            await audit(s, f"telegram:{ctx.user_id}", "approval_rejected", {"id": a.id})
            return "rejected", f"Đã từ chối #{a.id}: {a.summary}"
        a.status = "approved"
        action, payload, agent, case_id = a.action, dict(a.payload), a.agent, a.case_id
    try:
        text, kind, ref = await EXECUTORS[action](ctx, payload)
    except Exception as e:
        async with ctx.sessionmaker() as s, s.begin():
            a = await s.get(Approval, approval_id)
            a.status, a.result = "failed", f"{type(e).__name__}: {e}"
            await audit(s, f"agent:{agent}", "approval_failed", {"id": approval_id, "error": str(e)})
        return "failed", f"Thực thi #{approval_id} thất bại: {e}"
    async with ctx.sessionmaker() as s, s.begin():
        a = await s.get(Approval, approval_id)
        a.status, a.result = "executed", text
        await add_evidence(s, agent, kind, ref, text, case_id)
        await audit(s, f"agent:{agent}", "approval_executed", {"id": approval_id, "ref": ref})
    return "executed", f"Đã thực hiện #{approval_id}. {text}"
