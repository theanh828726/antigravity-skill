"""Adapter Google thật (Gmail / Calendar / Drive) qua OAuth refresh token.

Thư viện google-api-python-client là đồng bộ, nên mọi lời gọi được bọc bằng asyncio.to_thread.
Phạm vi quyền cần cấp khi tạo refresh token:
  gmail.readonly, gmail.compose, calendar, drive.readonly
"""
from __future__ import annotations

import asyncio
import base64
import datetime as dt
from email.message import EmailMessage

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from ..config import Settings
from .base import CalendarEvent, DriveFile, Integrations, MailDraft, MailMessage

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/drive.readonly",
]


def _creds(s: Settings) -> Credentials:
    return Credentials(
        token=None,
        refresh_token=s.google_refresh_token,
        client_id=s.google_client_id,
        client_secret=s.google_client_secret,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )


def _header(msg: dict, name: str) -> str:
    for h in msg.get("payload", {}).get("headers", []):
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def _body_text(payload: dict) -> str:
    if payload.get("mimeType", "").startswith("text/plain") and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", "replace")
    for part in payload.get("parts", []) or []:
        text = _body_text(part)
        if text:
            return text
    return ""


class GoogleMail:
    def __init__(self, s: Settings):
        self._svc = build("gmail", "v1", credentials=_creds(s), cache_discovery=False)

    def _to_msg(self, m: dict, full: bool) -> MailMessage:
        return MailMessage(
            id=m["id"], thread_id=m["threadId"], sender=_header(m, "From"), subject=_header(m, "Subject"),
            snippet=m.get("snippet", ""), body=_body_text(m["payload"]) if full else "",
            received_at=_header(m, "Date"), unread="UNREAD" in m.get("labelIds", []),
        )

    async def list_unread(self, limit: int = 10) -> list[MailMessage]:
        def run():
            r = self._svc.users().messages().list(userId="me", q="is:unread in:inbox", maxResults=limit).execute()
            return [
                self._svc.users().messages().get(userId="me", id=x["id"], format="metadata",
                                                 metadataHeaders=["From", "Subject", "Date"]).execute()
                for x in r.get("messages", [])
            ]
        return [self._to_msg(m, False) for m in await asyncio.to_thread(run)]

    async def get_message(self, message_id: str) -> MailMessage:
        m = await asyncio.to_thread(
            lambda: self._svc.users().messages().get(userId="me", id=message_id, format="full").execute())
        return self._to_msg(m, True)

    async def create_draft(self, to, subject, body, reply_to_message_id=None) -> MailDraft:
        em = EmailMessage()
        em["To"], em["Subject"] = to, subject
        em.set_content(body)
        msg: dict = {"raw": base64.urlsafe_b64encode(em.as_bytes()).decode()}
        if reply_to_message_id:
            orig = await asyncio.to_thread(
                lambda: self._svc.users().messages().get(userId="me", id=reply_to_message_id, format="minimal").execute())
            msg["threadId"] = orig["threadId"]
        d = await asyncio.to_thread(
            lambda: self._svc.users().drafts().create(userId="me", body={"message": msg}).execute())
        return MailDraft(d["id"], to, subject, body, reply_to_message_id)

    async def send_draft(self, draft_id: str) -> str:
        r = await asyncio.to_thread(
            lambda: self._svc.users().drafts().send(userId="me", body={"id": draft_id}).execute())
        return r["id"]


class GoogleCalendar:
    def __init__(self, s: Settings):
        self._svc = build("calendar", "v3", credentials=_creds(s), cache_discovery=False)
        self._cal = s.google_calendar_id

    @staticmethod
    def _parse(v: dict) -> dt.datetime:
        raw = v.get("dateTime") or v["date"] + "T00:00:00+00:00"
        return dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))

    async def list_events(self, start, end) -> list[CalendarEvent]:
        r = await asyncio.to_thread(lambda: self._svc.events().list(
            calendarId=self._cal, timeMin=start.isoformat(), timeMax=end.isoformat(),
            singleEvents=True, orderBy="startTime").execute())
        return [CalendarEvent(e["id"], e.get("summary", "(không tiêu đề)"), self._parse(e["start"]),
                              self._parse(e["end"]), e.get("location", ""),
                              [a["email"] for a in e.get("attendees", [])]) for e in r.get("items", [])]

    async def create_event(self, title, start, end, location="", attendees=None) -> CalendarEvent:
        body = {"summary": title, "location": location,
                "start": {"dateTime": start.isoformat()}, "end": {"dateTime": end.isoformat()},
                "attendees": [{"email": a} for a in attendees or []]}
        e = await asyncio.to_thread(lambda: self._svc.events().insert(calendarId=self._cal, body=body).execute())
        return CalendarEvent(e["id"], title, start, end, location, attendees or [])


class GoogleDrive:
    def __init__(self, s: Settings):
        self._svc = build("drive", "v3", credentials=_creds(s), cache_discovery=False)
        self._folder = s.google_drive_folder_id

    async def search(self, query, limit=10) -> list[DriveFile]:
        q = query.replace("'", "\\'")
        expr = f"(name contains '{q}' or fullText contains '{q}') and trashed=false"
        if self._folder:
            expr += f" and '{self._folder}' in parents"
        r = await asyncio.to_thread(lambda: self._svc.files().list(
            q=expr, pageSize=limit, fields="files(id,name,mimeType,webViewLink,modifiedTime)").execute())
        return [DriveFile(f["id"], f["name"], f["mimeType"], f.get("webViewLink", ""), f.get("modifiedTime", ""))
                for f in r.get("files", [])]

    async def read_text(self, file_id: str) -> str:
        meta = await asyncio.to_thread(lambda: self._svc.files().get(fileId=file_id, fields="mimeType").execute())
        if meta["mimeType"].startswith("application/vnd.google-apps"):
            data = await asyncio.to_thread(
                lambda: self._svc.files().export(fileId=file_id, mimeType="text/plain").execute())
        else:
            data = await asyncio.to_thread(lambda: self._svc.files().get_media(fileId=file_id).execute())
        return data.decode("utf-8", "replace") if isinstance(data, bytes) else str(data)


def build_integrations(s: Settings) -> Integrations:
    if s.google_configured:
        return Integrations(GoogleMail(s), GoogleCalendar(s), GoogleDrive(s), mode="google")
    from .mock import MockCalendar, MockDrive, MockMail
    return Integrations(MockMail(), MockCalendar(), MockDrive(), mode="mock")
