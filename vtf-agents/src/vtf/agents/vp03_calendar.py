"""VP-03 | Quản lý lịch: tra lịch, kiểm tra trùng, đề xuất lịch, chuẩn bị họp, nhắc mốc đã xác nhận."""
from __future__ import annotations

import datetime as dt

from ..core.approvals import executor
from ..core.context import Ctx
from ..core.tools import AgentDef, Tool

SYSTEM = """Bạn là VP-03 | Quản lý lịch của hệ thống AI Agent VTF.
Nhiệm vụ: tra lịch, kiểm tra trùng lịch, đề xuất khung giờ, chuẩn bị họp (chương trình, tài liệu cần mang), nhắc mốc.
Quy tắc cứng:
- Luôn gọi check_conflicts trước khi đề xuất hoặc tạo lịch. Nếu trùng, nêu rõ sự kiện trùng.
- create_calendar_event chỉ tạo yêu cầu phê duyệt; lịch chỉ được tạo sau khi anh Thanh Huy bấm Duyệt.
- Giờ theo múi giờ Việt Nam (UTC+7) nếu không nói khác. Dùng ISO 8601 có ngày đầy đủ; thiếu ngày/giờ thì hỏi lại.
- Chỉ nhắc "mốc đã xác nhận" - không coi lịch dự kiến là cam kết."""

WORK_START, WORK_END = 8, 17.5


def _row(e):
    return {"id": e.id, "title": e.title, "start": e.start.isoformat(), "end": e.end.isoformat(),
            "location": e.location}


async def list_schedule(ctx: Ctx, start: str, end: str):
    return [_row(e) for e in await ctx.integrations.calendar.list_events(ctx.parse_dt(start), ctx.parse_dt(end))]


async def check_conflicts(ctx: Ctx, start: str, end: str):
    ev = await ctx.integrations.calendar.list_events(ctx.parse_dt(start), ctx.parse_dt(end))
    return {"trung_lich": bool(ev), "su_kien_trung": [_row(e) for e in ev]}


async def propose_slots(ctx: Ctx, date_from: str, date_to: str, duration_minutes: int = 60, max_slots: int = 5):
    """Tìm khung trống trong giờ hành chính (T2-T6, 08:00-17:30), bước 30 phút."""
    d0, d1 = ctx.parse_dt(date_from), ctx.parse_dt(date_to)
    busy = await ctx.integrations.calendar.list_events(d0, d1 + dt.timedelta(days=1))
    dur, slots = dt.timedelta(minutes=duration_minutes), []
    day = d0.replace(hour=0, minute=0, second=0, microsecond=0)
    while day.date() <= d1.date() and len(slots) < max_slots:
        if day.weekday() < 5:
            t = day.replace(hour=int(WORK_START))
            close = day.replace(hour=int(WORK_END), minute=int((WORK_END % 1) * 60))
            while t + dur <= close and len(slots) < max_slots:
                if t >= ctx.now() and not any(e.start < t + dur and e.end > t for e in busy):
                    slots.append({"start": t.isoformat(), "end": (t + dur).isoformat()})
                t += dt.timedelta(minutes=30)
        day += dt.timedelta(days=1)
    return slots


def build() -> AgentDef:
    return AgentDef("VP-03", "Quản lý lịch", SYSTEM, [
        Tool("list_schedule", "Liệt kê sự kiện trong khoảng thời gian (ISO 8601).",
             {"start": {"type": "string"}, "end": {"type": "string"}}, ["start", "end"], list_schedule),
        Tool("check_conflicts", "Kiểm tra khoảng thời gian có trùng sự kiện nào không.",
             {"start": {"type": "string"}, "end": {"type": "string"}}, ["start", "end"], check_conflicts),
        Tool("propose_slots", "Đề xuất khung giờ trống trong giờ hành chính.",
             {"date_from": {"type": "string"}, "date_to": {"type": "string"},
              "duration_minutes": {"type": "integer"}, "max_slots": {"type": "integer"}},
             ["date_from", "date_to"], propose_slots),
        Tool("create_calendar_event", "Yêu cầu TẠO lịch. Chỉ tạo yêu cầu phê duyệt, chưa tạo.",
             {"title": {"type": "string"}, "start": {"type": "string"}, "end": {"type": "string"},
              "location": {"type": "string"}, "attendees": {"type": "array", "items": {"type": "string"}},
              "case_id": {"type": "integer"}}, ["title", "start", "end"],
             approval_action="create_event",
             summarize=lambda a: f"Tạo lịch \"{a.get('title')}\" {a.get('start')} → {a.get('end')}"),
    ])


@executor("create_event")
async def _create(ctx: Ctx, p: dict):
    e = await ctx.integrations.calendar.create_event(
        p["title"], ctx.parse_dt(p["start"]), ctx.parse_dt(p["end"]), p.get("location", ""), p.get("attendees"))
    return f"Đã tạo lịch \"{e.title}\" (mã {e.id}).", "event_created", e.id
