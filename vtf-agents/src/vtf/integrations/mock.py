"""Adapter giả lập dùng khi chưa nối Google và khi chạy test. Có trạng thái trong bộ nhớ."""
from __future__ import annotations

import datetime as dt
import itertools

from .base import CalendarEvent, DriveFile, MailDraft, MailMessage



class MockMail:
    def __init__(self) -> None:
        self._ids = itertools.count(1)
        self.inbox: list[MailMessage] = []
        self.drafts: dict[str, MailDraft] = {}
        self.sent: list[tuple[str, MailDraft]] = []

    async def list_unread(self, limit: int = 10) -> list[MailMessage]:
        return [m for m in self.inbox if m.unread][:limit]

    async def get_message(self, message_id: str) -> MailMessage:
        for m in self.inbox:
            if m.id == message_id:
                return m
        raise KeyError(f"Không có thư {message_id}")

    async def create_draft(self, to, subject, body, reply_to_message_id=None) -> MailDraft:
        d = MailDraft(f"draft-{next(self._ids)}", to, subject, body, reply_to_message_id)
        self.drafts[d.id] = d
        return d

    async def send_draft(self, draft_id: str) -> str:
        d = self.drafts.pop(draft_id)
        sent_id = f"sent-{next(self._ids)}"
        self.sent.append((sent_id, d))
        return sent_id


class MockCalendar:
    def __init__(self) -> None:
        self._ids = itertools.count(1)
        self.events: list[CalendarEvent] = []

    async def list_events(self, start, end) -> list[CalendarEvent]:
        return sorted((e for e in self.events if e.start < end and e.end > start), key=lambda e: e.start)

    async def create_event(self, title, start, end, location="", attendees=None) -> CalendarEvent:
        e = CalendarEvent(f"evt-{next(self._ids)}", title, start, end, location, attendees or [])
        self.events.append(e)
        return e


class MockDrive:
    def __init__(self) -> None:
        self._ids = itertools.count(1)
        self.files: dict[str, tuple[DriveFile, str]] = {}

    def add(self, name: str, text: str, mime: str = "text/plain") -> DriveFile:
        f = DriveFile(f"file-{next(self._ids)}", name, mime, f"https://drive.example/{name}")
        self.files[f.id] = (f, text)
        return f

    async def search(self, query, limit=10) -> list[DriveFile]:
        q = query.lower()
        return [f for f, t in self.files.values() if q in f.name.lower() or q in t.lower()][:limit]

    async def read_text(self, file_id: str) -> str:
        return self.files[file_id][1]
