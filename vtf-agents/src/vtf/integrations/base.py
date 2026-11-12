from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class MailMessage:
    id: str
    thread_id: str
    sender: str
    subject: str
    snippet: str
    body: str = ""
    received_at: str = ""
    unread: bool = True


@dataclass
class MailDraft:
    id: str
    to: str
    subject: str
    body: str
    reply_to_message_id: str | None = None


@dataclass
class CalendarEvent:
    id: str
    title: str
    start: dt.datetime
    end: dt.datetime
    location: str = ""
    attendees: list[str] = field(default_factory=list)


@dataclass
class DriveFile:
    id: str
    name: str
    mime_type: str
    web_url: str = ""
    modified: str = ""


class MailProvider(Protocol):
    async def list_unread(self, limit: int = 10) -> list[MailMessage]: ...
    async def get_message(self, message_id: str) -> MailMessage: ...
    async def create_draft(self, to: str, subject: str, body: str, reply_to_message_id: str | None = None) -> MailDraft: ...
    async def send_draft(self, draft_id: str) -> str: ...  # trả về mã thư đã gửi


class CalendarProvider(Protocol):
    async def list_events(self, start: dt.datetime, end: dt.datetime) -> list[CalendarEvent]: ...
    async def create_event(self, title: str, start: dt.datetime, end: dt.datetime, location: str = "", attendees: list[str] | None = None) -> CalendarEvent: ...


class DriveProvider(Protocol):
    async def search(self, query: str, limit: int = 10) -> list[DriveFile]: ...
    async def read_text(self, file_id: str) -> str: ...


@dataclass
class Integrations:
    mail: MailProvider
    calendar: CalendarProvider
    drive: DriveProvider
    mode: str = "mock"
