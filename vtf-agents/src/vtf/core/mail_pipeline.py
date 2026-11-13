"""Luồng tự động: thư đến → agent đọc/lập hồ sơ/soạn dự thảo → trình Telegram → Duyệt / Làm lại / Từ chối."""
from __future__ import annotations

import logging
import re
from typing import Awaitable, Callable

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..agents import intake
from ..config import Settings
from ..db.models import Approval, ProcessedMail
from ..integrations.base import Integrations, MailMessage
from .context import Ctx
from .llm import LLM
from .store import audit
from .tools import run_agent

log = logging.getLogger(__name__)
# notify(chat_id, approval_ids, text): bot gửi tin kèm nút cho các yêu cầu duyệt
Notify = Callable[[int, list[int], str], Awaitable[None]]
_IGNORE = re.compile(r"(no-?reply|do-?not-?reply|mailer-daemon|postmaster|notification[s]?@)", re.I)


class MailPipeline:
    def __init__(self, llm: LLM, s: Settings, sm: async_sessionmaker[AsyncSession],
                 integ: Integrations, notify: Notify):
        self.llm, self.s, self.sm, self.integ, self.notify = llm, s, sm, integ, notify
        self.agent = intake.build()

    def _ctx(self, **extra) -> Ctx:
        chat = self.s.owner_ids[0]
        return Ctx(self.s, self.sm, self.integ, chat_id=chat, user_id=0, role="system", extra=extra)

    async def poll_once(self) -> int:
        n = 0
        for m in await self.integ.mail.list_unread(limit=20):
            if await self._claim(m):
                n += 1
                await self._process(m)
        return n

    async def _claim(self, m: MailMessage) -> bool:
        async with self.sm() as s:
            try:
                async with s.begin():
                    status = "ignored" if _IGNORE.search(m.sender or "") else "processing"
                    s.add(ProcessedMail(message_id=m.id, sender=m.sender, subject=m.subject, status=status,
                                        note="thư tự động" if status == "ignored" else None))
            except IntegrityError:
                return False
        return status == "processing"

    async def _set(self, message_id: str, **vals) -> None:
        async with self.sm() as s, s.begin():
            await s.execute(update(ProcessedMail).where(ProcessedMail.message_id == message_id).values(**vals))

    async def _process(self, m: MailMessage) -> None:
        ctx = self._ctx(source_message_id=m.id)
        brief = (f"Xử lý thư đến. id thư: {m.id}\nNgười gửi: {m.sender}\nTiêu đề: {m.subject}\n"
                 f"Nhận lúc: {m.received_at}\nThời điểm hiện tại: {ctx.now():%Y-%m-%d %H:%M}")
        chat = ctx.chat_id
        try:
            await run_agent(self.agent, self.llm, ctx, [{"role": "user", "content": brief}], self.s.max_agent_iterations)
        except Exception as e:
            log.exception("Xử lý thư %s lỗi", m.id)
            await self._set(m.id, status="failed", note=f"{type(e).__name__}: {e}")
            await self.notify(chat, [], f"⚠️ Em chưa xử lý được thư từ {m.sender} - \"{m.subject}\" ({type(e).__name__}). "
                                        "Anh xử lý thủ công hoặc nhắn em làm lại.")
            return
        async with self.sm() as s, s.begin():
            await audit(s, "agent:intake", "mail_processed", {"id": m.id, "approvals": ctx.pending_approval_ids})
        if ctx.pending_approval_ids:
            case_id = await self._case_of(ctx.pending_approval_ids[0])
            await self._set(m.id, status="proposed", case_id=case_id)
            await self.notify(chat, ctx.pending_approval_ids,
                              f"📩 <b>Thư đến cần phản hồi</b>\nTừ: {_e(m.sender)}\nTiêu đề: {_e(m.subject)}")
        elif "no_action" in ctx.extra:
            await self._set(m.id, status="no_action", note=ctx.extra["no_action"])
            await self.notify(chat, [], f"ℹ️ Thư từ {_e(m.sender)} - \"{_e(m.subject)}\": không cần phản hồi "
                                        f"({_e(ctx.extra['no_action'])}).")
        else:
            await self._set(m.id, status="failed", note="agent không đưa ra kết luận")
            await self.notify(chat, [], f"⚠️ Em chưa kết luận được cách xử lý thư từ {_e(m.sender)} - "
                                        f"\"{_e(m.subject)}\". Anh xem giúp em.")

    async def _case_of(self, approval_id: int) -> int | None:
        async with self.sm() as s:
            a = await s.get(Approval, approval_id)
            return a.case_id if a else None

    async def revise(self, approval_id: int, feedback: str) -> list[int]:
        """Làm lại dự thảo theo góp ý. Trả về id yêu cầu duyệt mới (rỗng nếu thất bại, bản cũ được khôi phục)."""
        async with self.sm() as s, s.begin():
            a = await s.get(Approval, approval_id, with_for_update=True)
            if a is None or a.action != "send_reply":
                raise ValueError("Yêu cầu này không phải dự thảo thư trả lời")
            if a.status not in ("pending", "rejected"):
                raise ValueError(f"Yêu cầu #{approval_id} đã ở trạng thái {a.status}, không làm lại được")
            old_status, p = a.status, dict(a.payload)
            if p.get("revision", 1) >= self.s.max_revisions:
                raise ValueError(f"Đã làm lại tối đa {self.s.max_revisions} lần; anh soạn tay hoặc /reset rồi nhắn em.")
            a.status = "revised"
            await audit(s, "telegram", "approval_revised", {"id": a.id, "feedback": feedback[:300]})
        ctx = self._ctx(source_message_id=p["message_id"], case_id=p.get("case_id"), revision=p.get("revision", 1) + 1)
        brief = (f"LÀM LẠI dự thảo trả lời thư id {p['message_id']} (hồ sơ id {p.get('case_id')}).\n"
                 f"Người nhận: {p['to']}\nTiêu đề: {p['subject']}\nTóm tắt thư đến: {p['request_summary']}\n\n"
                 f"=== DỰ THẢO TRƯỚC ===\n{p['body']}\n=== HẾT ===\n\n"
                 f"GÓP Ý CỦA GRAND MASTER: {feedback}\nThời điểm hiện tại: {ctx.now():%Y-%m-%d %H:%M}")
        try:
            await run_agent(self.agent, self.llm, ctx, [{"role": "user", "content": brief}], self.s.max_agent_iterations)
        except Exception:
            log.exception("Làm lại #%s lỗi", approval_id)
        if not ctx.pending_approval_ids:  # thất bại: trả bản cũ về trạng thái trước đó
            async with self.sm() as s, s.begin():
                await s.execute(update(Approval).where(Approval.id == approval_id).values(status=old_status))
            return []
        return ctx.pending_approval_ids


def _e(t: str | None) -> str:
    import html
    return html.escape(t or "")
