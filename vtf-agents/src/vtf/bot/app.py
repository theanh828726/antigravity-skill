from __future__ import annotations

import asyncio
import datetime as dt
import html
import logging
import uuid

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.chat_action import ChatActionSender
from sqlalchemy import select

from ..config import Settings
from ..core import knowledge
from ..core.approvals import decide
from ..core.context import Ctx
from ..core.orchestrator import Orchestrator
from ..core.store import add_evidence
from ..db.models import Approval, Case, Document, Task
from ..db.session import Database
from ..integrations.base import Integrations

log = logging.getLogger(__name__)
TG_LIMIT = 4000

HELP = (
    "<b>VTF AI Agent - TQ GoClaw</b>\n"
    "Nhắn tự nhiên, em sẽ phân công cho agent phù hợp.\n\n"
    "/cases - hồ sơ đang mở\n/tasks - việc chưa xong\n/pending - yêu cầu chờ duyệt\n"
    "/case HS-2026-0001 - tổng quan một hồ sơ\n/agents - sơ đồ agent\n/reset - xoá ngữ cảnh hội thoại\n"
    "Gửi tệp PDF/TXT/MD kèm chú thích để lưu vào kho tài liệu (VP-04) và cho VP-05 tra cứu."
)
AGENTS = (
    "<b>Sơ đồ</b>\nTQ Tổng quản\n• VP-01 Công việc  • VP-02 Email  • VP-03 Lịch\n"
    "• VP-04 Công văn  • VP-05 Hỏi đáp tài liệu\n"
    "Chưa kích hoạt: HV Hội viên, SK Sự kiện, TT Truyền thông"
)


def _chunks(text: str) -> list[str]:
    return [text[i:i + TG_LIMIT] for i in range(0, len(text), TG_LIMIT)] or [""]


def approval_kb(approval_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Duyệt", callback_data=f"ap:{approval_id}:y"),
        InlineKeyboardButton(text="❌ Từ chối", callback_data=f"ap:{approval_id}:n"),
    ]])


class VtfBot:
    def __init__(self, s: Settings, db: Database, integrations: Integrations, orch: Orchestrator):
        self.s, self.db, self.integ, self.orch = s, db, integrations, orch
        self.bot = Bot(s.telegram_bot_token)
        self.dp = Dispatcher()
        self._locks: dict[int, asyncio.Lock] = {}
        r = Router()
        self._register(r)
        self.dp.include_router(r)

    # ---------- quyền ----------
    def role_of(self, user_id: int) -> str | None:
        if user_id in self.s.owner_ids:
            return "owner"
        if user_id in self.s.staff_ids:
            return "staff"
        return None

    def ctx(self, chat_id: int, user_id: int, role: str) -> Ctx:
        return Ctx(self.s, self.db.session, self.integ, chat_id=chat_id, user_id=user_id, role=role)

    async def _send(self, chat_id: int, text: str, **kw) -> None:
        for part in _chunks(text):
            await self.bot.send_message(chat_id, part, **kw)

    async def _send_approvals(self, chat_id: int, ids: list[int]) -> None:
        if not ids:
            return
        async with self.db.session() as s:
            rows = (await s.scalars(select(Approval).where(Approval.id.in_(ids)))).all()
        for a in rows:
            await self.bot.send_message(
                chat_id, f"<b>Yêu cầu duyệt #{a.id}</b> ({a.agent})\n{html.escape(a.summary)}",
                parse_mode="HTML", reply_markup=approval_kb(a.id))

    # ---------- handlers ----------
    def _register(self, r: Router) -> None:
        def authorized(fn):
            # Không dùng functools.wraps: aiogram đọc chữ ký của wrapper và chỉ truyền `m`.
            async def wrapper(m: Message):
                role = self.role_of(m.from_user.id) if m.from_user else None
                if role is None:
                    log.warning("Từ chối user %s", m.from_user.id if m.from_user else "?")
                    await m.answer("Tài khoản này chưa được cấp quyền sử dụng hệ thống.")
                    return
                await fn(m, role)
            return wrapper

        @r.message(CommandStart())
        @r.message(Command("help"))
        @authorized
        async def start(m: Message, role: str):
            await m.answer(HELP, parse_mode="HTML")

        @r.message(Command("agents"))
        @authorized
        async def agents(m: Message, role: str):
            await m.answer(AGENTS, parse_mode="HTML")

        @r.message(Command("reset"))
        @authorized
        async def reset(m: Message, role: str):
            from sqlalchemy import delete
            from ..db.models import ChatMessage
            async with self.db.session() as s, s.begin():
                await s.execute(delete(ChatMessage).where(ChatMessage.chat_id == m.chat.id))
            await m.answer("Đã xoá ngữ cảnh hội thoại.")

        @r.message(Command("cases"))
        @authorized
        async def cases(m: Message, role: str):
            async with self.db.session() as s:
                rows = (await s.scalars(select(Case).where(Case.status == "open").order_by(Case.id.desc()).limit(20))).all()
            await m.answer("\n".join(f"<code>{c.code}</code> {html.escape(c.title)}" for c in rows) or "Chưa có hồ sơ.",
                           parse_mode="HTML")

        @r.message(Command("tasks"))
        @authorized
        async def tasks(m: Message, role: str):
            async with self.db.session() as s:
                rows = (await s.scalars(select(Task).where(Task.status != "done")
                                        .order_by(Task.due_at.is_(None), Task.due_at).limit(25))).all()
            lines = [f"#{t.id} {html.escape(t.title)} · {html.escape(t.assignee or '—')} · "
                     f"{t.due_at:%d/%m %H:%M}" if t.due_at else f"#{t.id} {html.escape(t.title)} · {html.escape(t.assignee or '—')}"
                     for t in rows]
            await m.answer("\n".join(lines) or "Không có việc tồn.", parse_mode="HTML")

        @r.message(Command("pending"))
        @authorized
        async def pending(m: Message, role: str):
            async with self.db.session() as s:
                ids = [a.id for a in (await s.scalars(select(Approval).where(Approval.status == "pending"))).all()]
            if not ids:
                await m.answer("Không có yêu cầu nào chờ duyệt.")
            await self._send_approvals(m.chat.id, ids)

        @r.message(Command("case"))
        @authorized
        async def case(m: Message, role: str):
            arg = (m.text or "").partition(" ")[2].strip()
            if not arg:
                await m.answer("Dùng: /case HS-2026-0001")
                return
            await self._ask(m, role, f"Cho anh tổng quan hồ sơ {arg}")

        @r.message(F.document)
        @authorized
        async def upload(m: Message, role: str):
            await self._upload(m, role)

        @r.message(F.text)
        @authorized
        async def text(m: Message, role: str):
            await self._ask(m, role, m.text)

        @r.callback_query(F.data.startswith("ap:"))
        async def approval_cb(cb: CallbackQuery):
            role = self.role_of(cb.from_user.id)
            if role is None:
                await cb.answer("Không có quyền", show_alert=True)
                return
            _, sid, choice = cb.data.split(":")
            ctx = self.ctx(cb.message.chat.id, cb.from_user.id, role)
            status, msg = await decide(ctx, int(sid), choice == "y")
            await cb.answer(msg[:190], show_alert=status == "denied")
            if status != "denied":
                await cb.message.edit_reply_markup(reply_markup=None)
                await cb.message.answer(html.escape(msg), parse_mode="HTML")

    async def _ask(self, m: Message, role: str, text: str) -> None:
        lock = self._locks.setdefault(m.chat.id, asyncio.Lock())  # tuần tự hoá theo chat
        async with lock, ChatActionSender.typing(bot=self.bot, chat_id=m.chat.id):
            ctx = self.ctx(m.chat.id, m.from_user.id, role)
            try:
                reply = await self.orch.handle(ctx, text)
            except Exception:
                ref = uuid.uuid4().hex[:8]
                log.exception("Lỗi xử lý [%s]", ref)
                reply = f"Em gặp lỗi khi xử lý (mã {ref}). Anh thử lại giúp em, hoặc báo mã này cho kỹ thuật."
        await self._send(m.chat.id, reply)
        await self._send_approvals(m.chat.id, ctx.pending_approval_ids)

    async def _upload(self, m: Message, role: str) -> None:
        doc = m.document
        name = doc.file_name or "tai-lieu"
        if not name.lower().endswith((".pdf", ".txt", ".md")):
            await m.answer("Hiện em đọc được PDF, TXT, MD. Anh gửi đúng định dạng giúp em.")
            return
        if doc.file_size and doc.file_size > 20 * 1024 * 1024:
            await m.answer("Tệp quá lớn (giới hạn 20MB).")
            return
        dest = self.s.data_dir / "uploads" / f"{uuid.uuid4().hex[:8]}-{name.replace('/', '_')}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        await self.bot.download(doc, destination=dest)
        text = await asyncio.to_thread(_extract_text, dest)
        if not text.strip():
            await m.answer("Em không trích được chữ từ tệp này (có thể là bản scan).")
            return
        async with self.db.session() as s, s.begin():
            d = Document(direction="in", title=name, file_path=str(dest), content=text, status="approved")
            s.add(d)
            await s.flush()
            n = await knowledge.index_text(s, name, text, "v1", d.id)
            await add_evidence(s, "VP-04", "document_uploaded", f"doc:{d.id}:v1", f"{name} ({n} đoạn)")
        await m.answer(f"Đã lưu \"{name}\" (văn bản #{d.id}, {n} đoạn) và lập chỉ mục cho VP-05.")
        if m.caption:
            await self._ask(m, role, f"{m.caption}\n[Tệp vừa nạp: văn bản #{d.id} \"{name}\"]")

    # ---------- nhắc việc ----------
    async def reminder_loop(self) -> None:
        while True:
            try:
                await self._remind_once()
            except Exception:
                log.exception("Lỗi vòng nhắc việc")
            await asyncio.sleep(self.s.reminder_interval_seconds)

    async def _remind_once(self) -> None:
        now = dt.datetime.now(dt.timezone.utc)
        horizon = now + dt.timedelta(hours=self.s.reminder_lead_hours)
        async with self.db.session() as s, s.begin():
            due = (await s.scalars(select(Task).where(
                Task.status != "done", Task.due_at.is_not(None), Task.due_at <= horizon,
                Task.remind_chat_id.is_not(None)))).all()
            for t in due:
                last = t.last_reminded_at
                if last and last.tzinfo is None:
                    last = last.replace(tzinfo=dt.timezone.utc)
                if last and now - last < dt.timedelta(hours=6):
                    continue
                due_at = t.due_at if t.due_at.tzinfo else t.due_at.replace(tzinfo=dt.timezone.utc)
                tag = "⚠️ QUÁ HẠN" if due_at < now else "⏰ Sắp đến hạn"
                await self.bot.send_message(
                    t.remind_chat_id, f"{tag}: #{t.id} {t.title}\nPhụ trách: {t.assignee or '—'} · "
                    f"Hạn {due_at.astimezone().strftime('%d/%m %H:%M')} · Tiến độ {t.progress}%")
                t.last_reminded_at = now

    async def run(self) -> None:
        await self.db.create_all()
        reminder = asyncio.create_task(self.reminder_loop())
        try:
            await self.dp.start_polling(self.bot)
        finally:
            reminder.cancel()
            await self.bot.session.close()


def _extract_text(path) -> str:
    if str(path).lower().endswith(".pdf"):
        from pypdf import PdfReader
        out = []
        for i, page in enumerate(PdfReader(str(path)).pages, 1):
            out.append(f"Trang {i}\n{page.extract_text() or ''}")
        return "\n".join(out)
    return path.read_text("utf-8", errors="replace")
