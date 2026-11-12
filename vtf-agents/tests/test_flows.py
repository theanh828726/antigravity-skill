import datetime as dt

from sqlalchemy import select

from conftest import ScriptedLLM, call, reply, text
from vtf.core.approvals import decide
from vtf.db.models import Approval, Case, Evidence, Task


async def test_email_requires_approval_then_sends_once(make_ctx, orch, integ, db):
    llm = ScriptedLLM(
        reply(call("delegate", agent="VP-02", instruction="Soạn và gửi thư mời họp tới a@vtf.vn")),
        reply(call("create_email_draft", to="a@vtf.vn", subject="Mời họp", body="Kính mời...")),
        reply(call("send_email_draft", draft_id="draft-1", to="a@vtf.vn", subject="Mời họp")),
        reply(text("Đã tạo yêu cầu phê duyệt #1")),
        reply(text("Em đã trình anh duyệt thư gửi a@vtf.vn.")),
    )
    ctx = make_ctx()
    out = await orch(llm).handle(ctx, "Gửi thư mời họp cho a@vtf.vn")
    assert "trình anh duyệt" in out
    assert integ.mail.sent == []          # CHƯA gửi
    assert len(ctx.pending_approval_ids) == 1

    aid = ctx.pending_approval_ids[0]
    status, msg = await decide(ctx, aid, True)
    assert status == "executed" and len(integ.mail.sent) == 1
    status2, _ = await decide(ctx, aid, True)   # bấm đúp
    assert status2 == "executed" and len(integ.mail.sent) == 1

    async with db.session() as s:
        ev = (await s.scalars(select(Evidence).where(Evidence.kind == "email_sent"))).all()
        assert len(ev) == 1 and ev[0].ref.startswith("sent-")


async def test_staff_cannot_approve_and_reject_does_nothing(make_ctx, integ, db):
    owner = make_ctx()
    from vtf.core.approvals import request_approval
    import vtf.agents.vp02_email  # noqa: đăng ký executor
    aid = await request_approval(owner, "VP-02", "send_email", "x", {"draft_id": "d", "to": "t"})
    st, _ = await decide(make_ctx(role="staff", user_id=2), aid, True)
    assert st == "denied"
    st, _ = await decide(owner, aid, False)
    assert st == "rejected" and integ.mail.sent == []


async def test_vp01_case_task_kpi(make_ctx, orch, db):
    llm = ScriptedLLM(
        reply(call("delegate", agent="VP-01", instruction="Tạo hồ sơ Đại hội và giao việc")),
        reply(call("create_case", title="Đại hội VTF 2026")),
        reply(call("create_task", title="Chuẩn bị báo cáo", case="HS-" + str(dt.datetime.now().year) + "-0001",
                   assignee="Lan", due_at="2020-01-01T09:00:00")),
        reply(call("kpi_summary")),
        reply(text("Đã tạo HS và 1 việc, quá hạn 1.")),
        reply(text("Xong: hồ sơ mới, 1 việc quá hạn.")),
    )
    ctx = make_ctx()
    await orch(llm).handle(ctx, "Lập hồ sơ đại hội, giao Lan báo cáo")
    async with db.session() as s:
        c = (await s.scalars(select(Case))).one()
        t = (await s.scalars(select(Task))).one()
        assert t.case_id == c.id and t.assignee == "Lan"
    kpi = [m for m in llm.calls[-2]["messages"] if m["role"] == "user"][-1]["content"][0]["content"]
    assert '"qua_han": 1' in kpi


async def test_vp03_conflict_and_slots(make_ctx, integ):
    from vtf.agents import vp03_calendar as v
    ctx = make_ctx()
    start = ctx.parse_dt("2099-03-02T09:00:00")  # Thứ Hai
    await integ.calendar.create_event("Họp BCH", start, start + dt.timedelta(hours=2))
    r = await v.check_conflicts(ctx, "2099-03-02T10:00:00", "2099-03-02T11:00:00")
    assert r["trung_lich"] and r["su_kien_trung"][0]["title"] == "Họp BCH"
    slots = await v.propose_slots(ctx, "2099-03-02T00:00:00", "2099-03-02T00:00:00", 60, 3)
    assert slots[0]["start"].startswith("2099-03-02T08:00")
    assert all(not s["start"].startswith("2099-03-02T09:") for s in slots)  # tránh 09:00-11:00
    wk = await v.propose_slots(ctx, "2099-03-07T00:00:00", "2099-03-08T00:00:00")  # T7-CN
    assert wk == []


async def test_vp04_versioning_and_approval(make_ctx, db):
    from vtf.agents import vp04_documents as v
    ctx = make_ctx()
    d1 = await v.draft_document(ctx, "Kế hoạch Giải 2026", "Điều 1. Mục đích\nTổ chức giải.")
    d2 = await v.draft_document(ctx, "", "Điều 1. Mục đích\nTổ chức giải quốc gia.", based_on_document_id=d1["document_id"])
    assert (d1["version"], d2["version"]) == (1, 2) and d2["title"] == "Kế hoạch Giải 2026"
    await v.submit_for_review(ctx, d2["document_id"])
    from vtf.core.approvals import request_approval
    aid = await request_approval(ctx, "VP-04", "approve_document", "x", {"document_id": d2["document_id"]})
    st, _ = await decide(ctx, aid, True)
    assert st == "executed"
    docs = await v.list_documents(ctx, status="approved")
    assert [d["version"] for d in docs] == [2]


async def test_vp05_cited_search(make_ctx):
    from vtf.agents import vp04_documents as v4, vp05_qa as v5
    ctx = make_ctx()
    await v4.register_document(ctx, "Điều lệ VTF", content=(
        "Điều 10. Hội viên\nHội viên đóng phí thường niên trước ngày 31/3.\n"
        "Điều 11. Đại hội\nĐại hội nhiệm kỳ họp 5 năm một lần."))
    hits = await v5.search_knowledge(ctx, "phí thường niên hội viên đóng khi nào")
    assert hits[0]["source"] == "Điều lệ VTF" and hits[0]["ref"].startswith("Điều 10")
    assert await v5.search_knowledge(ctx, "xyz không tồn tại") == {"ket_qua": "Không có đoạn nào khớp trong kho tri thức."}


async def test_inactive_branch_and_tool_error(make_ctx, orch):
    llm = ScriptedLLM(
        reply(call("delegate", agent="SK", instruction="Lập kế hoạch giải đấu")),
        reply(call("update_task_nonexistent")),
        reply(text("Nhánh SK chưa kích hoạt.")),
    )
    out = await orch(llm).handle(make_ctx(), "Lập kế hoạch giải")
    assert "chưa kích hoạt" in out
    # công cụ không tồn tại trả is_error, không làm sập
    last = llm.calls[-1]["messages"][-1]["content"][0]
    assert last["is_error"] is True and "Không có công cụ" in last["content"]


async def test_history_persisted(make_ctx, orch):
    llm = ScriptedLLM(reply(text("Chào anh")), reply(text("Vâng")))
    o, ctx = orch(llm), make_ctx()
    await o.handle(ctx, "xin chào")
    await o.handle(ctx, "tiếp tục")
    roles = [m["role"] for m in llm.calls[1]["messages"]]
    assert roles == ["user", "assistant", "user"]
