from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from .approvals import request_approval
from .context import Ctx
from .llm import LLM

log = logging.getLogger(__name__)

Handler = Callable[..., Awaitable[Any]]


@dataclass
class Tool:
    name: str
    description: str
    properties: dict[str, Any]
    required: list[str] = field(default_factory=list)
    handler: Handler | None = None
    # Hành động tác động ra ngoài: không chạy ngay mà tạo yêu cầu phê duyệt.
    approval_action: str | None = None
    summarize: Callable[[dict], str] | None = None

    def spec(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {"type": "object", "properties": self.properties,
                             "required": self.required, "additionalProperties": False},
        }


@dataclass
class AgentDef:
    code: str  # VP-01...
    name: str
    system: str
    tools: list[Tool]


def _text(content: list) -> str:
    return "\n".join(b.text for b in content if getattr(b, "type", "") == "text").strip()


async def run_agent(agent: AgentDef, llm: LLM, ctx: Ctx, history: list[dict], max_iter: int = 12) -> str:
    """Vòng lặp tool-use thủ công: chạy tới khi model kết thúc, chặn hành động cần duyệt."""
    tools = {t.name: t for t in agent.tools}
    specs = [t.spec() for t in agent.tools]
    messages = list(history)

    for _ in range(max_iter):
        resp = await llm.create(system=agent.system, messages=messages, tools=specs)
        if resp.stop_reason == "refusal":
            return "Yêu cầu này em không thể xử lý (bị từ chối bởi bộ lọc an toàn)."
        if resp.stop_reason == "max_tokens":
            return _text(resp.content) or "Phản hồi bị cắt do quá dài, anh chia nhỏ yêu cầu giúp em."
        if resp.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": resp.content})
            continue
        calls = [b for b in resp.content if getattr(b, "type", "") == "tool_use"]
        if resp.stop_reason != "tool_use" or not calls:
            return _text(resp.content)

        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for c in calls:
            results.append(await _exec(tools.get(c.name), c, agent, ctx))
        messages.append({"role": "user", "content": results})

    return "Em đã đạt giới hạn số bước xử lý; kết quả một phần đã được ghi vào hồ sơ."


async def _exec(tool: Tool | None, call: Any, agent: AgentDef, ctx: Ctx) -> dict:
    def res(content: Any, err: bool = False) -> dict:
        body = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False, default=str)
        return {"type": "tool_result", "tool_use_id": call.id, "content": body, **({"is_error": True} if err else {})}

    if tool is None:
        return res(f"Không có công cụ {call.name}", True)
    args = dict(call.input or {})
    try:
        if tool.approval_action:
            summary = tool.summarize(args) if tool.summarize else json.dumps(args, ensure_ascii=False)
            appr_id = await request_approval(ctx, agent.code, tool.approval_action, summary, args,
                                             case_id=args.get("case_id"))
            return res(f"Đã tạo yêu cầu phê duyệt #{appr_id}. CHƯA thực thi. Thông báo cho anh Thanh Huy "
                       f"bấm Duyệt trên Telegram; không nói là đã gửi/đã tạo.")
        assert tool.handler is not None
        return res(await tool.handler(ctx, **args))
    except Exception as e:  # lỗi công cụ trả về cho model tự xử lý, không làm sập lượt chat
        log.exception("Tool %s lỗi", tool.name)
        return res(f"Lỗi {type(e).__name__}: {e}", True)
