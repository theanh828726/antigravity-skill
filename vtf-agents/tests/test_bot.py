"""Kiểm tra nối dây Telegram bằng session giả (không gọi mạng)."""
import datetime as dt

from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.methods import SendMessage, TelegramMethod
from aiogram.types import CallbackQuery, Chat, Message, Update, User

from conftest import ScriptedLLM, call, reply, text
from vtf.bot.app import VtfBot
from vtf.core.orchestrator import Orchestrator


class FakeSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.sent: list[tuple[str, dict]] = []

    async def make_request(self, bot, method: TelegramMethod, timeout=None):
        data = method.model_dump(exclude_none=True)
        self.sent.append((type(method).__name__, data))
        if isinstance(method, SendMessage):
            return Message(message_id=len(self.sent), date=dt.datetime.now(), chat=Chat(id=data["chat_id"], type="private"),
                           text=data["text"])
        return True

    async def close(self): ...
    async def stream_content(self, *a, **k): yield b""


def make_bot(settings, db, integ, llm):
    b = VtfBot.__new__(VtfBot)
    # dựng thủ công để tránh Bot() thật
    from aiogram import Dispatcher, Router
    import asyncio
    b.s, b.db, b.integ, b.orch = settings, db, integ, Orchestrator(llm)
    b.sess = FakeSession()
    b.bot = Bot("123:ABC", session=b.sess)
    from vtf.core.mail_pipeline import MailPipeline
    b.pipeline = MailPipeline(llm, settings, db.session, integ, b.notify)
    b.dp, b._locks = Dispatcher(), {}
    r = Router(); b._register(r); b.dp.include_router(r)
    return b


def msg_update(uid, txt, uid_chat=None, n=1):
    u = User(id=uid, is_bot=False, first_name="T")
    return Update(update_id=n, message=Message(message_id=n, date=dt.datetime.now(), chat=Chat(id=uid_chat or uid, type="private"),
                                               from_user=u, text=txt))


async def test_unauthorized_rejected(settings, db, integ):
    b = make_bot(settings, db, integ, ScriptedLLM())
    await b.dp.feed_update(b.bot, msg_update(999, "xin chào"))
    assert "chưa được cấp quyền" in b.sess.sent[-1][1]["text"]


async def test_command_and_approval_buttons_end_to_end(settings, db, integ):
    llm = ScriptedLLM(
        reply(call("delegate", agent="VP-02", instruction="gửi thư")),
        reply(call("send_email_draft", draft_id="draft-1", to="a@vtf.vn", subject="Mời")),
        reply(text("đã tạo yêu cầu")),
        reply(text("Em đã trình anh duyệt.")),
    )
    await integ.mail.create_draft("a@vtf.vn", "Mời", "nội dung")  # draft-1
    b = make_bot(settings, db, integ, llm)

    await b.dp.feed_update(b.bot, msg_update(1, "/agents", n=1))
    assert "VP-05" in b.sess.sent[-1][1]["text"]

    await b.dp.feed_update(b.bot, msg_update(1, "Gửi thư mời cho a@vtf.vn", n=2))
    kb = [d for n, d in b.sess.sent if "reply_markup" in d][-1]["reply_markup"]
    assert integ.mail.sent == []
    data = kb["inline_keyboard"][0][0]["callback_data"]
    assert data.startswith("ap:") and data.endswith(":y")

    cb_msg = Message(message_id=50, date=dt.datetime.now(), chat=Chat(id=1, type="private"), text="x")
    owner = User(id=1, is_bot=False, first_name="T")
    await b.dp.feed_update(b.bot, Update(update_id=3, callback_query=CallbackQuery(
        id="c1", from_user=owner, chat_instance="ci", message=cb_msg, data=data)))
    assert len(integ.mail.sent) == 1

    # nhân viên (staff) bấm Duyệt trên yêu cầu khác phải bị từ chối
    from vtf.core.approvals import request_approval
    import vtf.agents.vp02_email  # noqa
    from conftest import Ctx
    ctx = Ctx(settings, db.session, integ, chat_id=1, user_id=1)
    aid = await request_approval(ctx, "VP-02", "send_email", "x", {"draft_id": "none", "to": "t"})
    staff = User(id=2, is_bot=False, first_name="S")
    await b.dp.feed_update(b.bot, Update(update_id=4, callback_query=CallbackQuery(
        id="c2", from_user=staff, chat_instance="ci", message=cb_msg, data=f"ap:{aid}:y")))
    assert len(integ.mail.sent) == 1


async def test_auto_mail_buttons_and_redo_via_reply(settings, db, integ):
    from test_auto_mail import draft_script, incoming
    llm = ScriptedLLM(*draft_script("Bản 1"),
                      reply(call("propose_reply", to="vp@bo.gov.vn", subject="Re: BC", body="Bản 2 ngắn",
                                 request_summary="x", source_message_id="m1")), reply(text("xong")))
    integ.mail.inbox.append(incoming())
    b = make_bot(settings, db, integ, llm)
    await b.pipeline.poll_once()

    drafts = [d for n, d in b.sess.sent if "Dự thảo trả lời" in d.get("text", "")]
    assert "Bản 1" in drafts[0]["text"] and "Cần bổ sung" in drafts[0]["text"]
    btns = [x["callback_data"] for x in drafts[0]["reply_markup"]["inline_keyboard"][0]]
    assert [c.split(":")[2] for c in btns] == ["y", "r", "n"]
    aid = btns[0].split(":")[1]

    owner = User(id=1, is_bot=False, first_name="T")
    cb_msg = Message(message_id=50, date=dt.datetime.now(), chat=Chat(id=1, type="private"), text="x")
    await b.dp.feed_update(b.bot, Update(update_id=10, callback_query=CallbackQuery(
        id="c", from_user=owner, chat_instance="ci", message=cb_msg, data=f"ap:{aid}:r")))
    prompt = b.sess.sent[-1][1]
    assert f"Làm lại bản dự thảo #{aid}" in prompt["text"] and prompt["reply_markup"]["force_reply"]

    # anh trả lời đúng tin nhắn nhắc → hệ thống làm lại
    prompt_msg = Message(message_id=60, date=dt.datetime.now(), chat=Chat(id=1, type="private"), text=prompt["text"])
    upd = Update(update_id=11, message=Message(message_id=61, date=dt.datetime.now(), chat=Chat(id=1, type="private"),
                  from_user=owner, text="Ngắn hơn", reply_to_message=prompt_msg))
    await b.dp.feed_update(b.bot, upd)
    newest = [d for n, d in b.sess.sent if "Dự thảo trả lời" in d.get("text", "")][-1]
    assert "Bản 2 ngắn" in newest["text"] and "v2" in newest["text"]
    assert integ.mail.sent == []
