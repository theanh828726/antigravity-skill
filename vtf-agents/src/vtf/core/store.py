from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import AuditLog, Case, Evidence


async def next_case_code(s: AsyncSession) -> str:
    year = dt.datetime.now().year
    prefix = f"HS-{year}-"
    n = await s.scalar(select(func.count()).select_from(Case).where(Case.code.like(prefix + "%")))
    return f"{prefix}{(n or 0) + 1:04d}"


async def create_case(s: AsyncSession, title: str, branch: str = "VP", owner: str | None = None,
                      source: str | None = None) -> Case:
    case = Case(code=await next_case_code(s), title=title, branch=branch, owner=owner, source=source)
    s.add(case)
    await s.flush()
    return case


async def get_case(s: AsyncSession, code_or_id: str | int | None) -> Case | None:
    if code_or_id in (None, ""):
        return None
    if isinstance(code_or_id, int) or str(code_or_id).isdigit():
        return await s.get(Case, int(code_or_id))
    return await s.scalar(select(Case).where(Case.code == str(code_or_id).upper()))


async def add_evidence(s: AsyncSession, agent: str, kind: str, ref: str | None = None,
                       detail: str | None = None, case_id: int | None = None) -> Evidence:
    ev = Evidence(agent=agent, kind=kind, ref=ref, detail=detail, case_id=case_id)
    s.add(ev)
    await s.flush()
    return ev


async def audit(s: AsyncSession, actor: str, event: str, detail: dict[str, Any] | None = None) -> None:
    s.add(AuditLog(actor=actor, event=event, detail=detail))
