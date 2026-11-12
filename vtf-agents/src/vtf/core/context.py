from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..config import Settings
from ..integrations.base import Integrations


@dataclass
class Ctx:
    """Ngữ cảnh một lượt xử lý: ai gọi, ở chat nào, dùng dịch vụ nào."""

    settings: Settings
    sessionmaker: async_sessionmaker[AsyncSession]
    integrations: Integrations
    chat_id: int = 0
    user_id: int = 0
    role: str = "owner"  # owner | staff
    pending_approval_ids: list[int] = field(default_factory=list)  # bot sẽ hiện nút Duyệt

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.settings.timezone)

    def now(self) -> dt.datetime:
        return dt.datetime.now(self.tz)

    def parse_dt(self, value: str) -> dt.datetime:
        """Nhận ISO 8601; nếu thiếu múi giờ thì dùng múi giờ cấu hình."""
        d = dt.datetime.fromisoformat(value)
        return d if d.tzinfo else d.replace(tzinfo=self.tz)
