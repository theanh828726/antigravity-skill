import itertools
from types import SimpleNamespace as NS

import pytest

from vtf.config import Settings
from vtf.core.context import Ctx
from vtf.core.orchestrator import Orchestrator
from vtf.db.session import Database
from vtf.integrations.base import Integrations
from vtf.integrations.mock import MockCalendar, MockDrive, MockMail

_ids = itertools.count(1)


def text(t):
    return NS(type="text", text=t)


def call(name, **inp):
    return NS(type="tool_use", id=f"tu_{next(_ids)}", name=name, input=inp)


def reply(*blocks, stop=None):
    stop = stop or ("tool_use" if any(b.type == "tool_use" for b in blocks) else "end_turn")
    return NS(content=list(blocks), stop_reason=stop)


class ScriptedLLM:
    """Trả lần lượt các phản hồi đã soạn; ghi lại các lần gọi để kiểm tra."""

    def __init__(self, *responses):
        self.queue, self.calls = list(responses), []

    async def create(self, *, system, messages, tools):
        self.calls.append({"system": system, "messages": list(messages), "tools": [t["name"] for t in tools]})
        assert self.queue, "LLM bị gọi nhiều hơn kịch bản"
        return self.queue.pop(0)


@pytest.fixture
async def db():
    d = Database("sqlite+aiosqlite:///:memory:")
    await d.create_all()
    yield d
    await d.dispose()


@pytest.fixture
def integ():
    return Integrations(MockMail(), MockCalendar(), MockDrive(), mode="mock")


@pytest.fixture
def settings():
    return Settings(owner_telegram_ids="1", staff_telegram_ids="2", timezone="Asia/Ho_Chi_Minh")


@pytest.fixture
def make_ctx(db, integ, settings):
    def f(role="owner", user_id=1, chat_id=100):
        return Ctx(settings, db.session, integ, chat_id=chat_id, user_id=user_id, role=role)
    return f


@pytest.fixture
def orch():
    def f(llm):
        return Orchestrator(llm)
    return f
