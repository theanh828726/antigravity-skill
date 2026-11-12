"""Lập chỉ mục và tìm kiếm tài liệu cho VP-05. Chấm điểm theo từ khóa, chạy trên cả SQLite và Postgres.
Có thể thay bằng pgvector/FTS mà không đổi giao diện search()."""
from __future__ import annotations

import re
import unicodedata

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import KnowledgeChunk

_DIEU = re.compile(r"^\s*(Điều|Chương|Mục)\s+\d+[a-zA-Z]?\b.*", re.IGNORECASE)


def _norm(t: str) -> str:
    return unicodedata.normalize("NFC", t).lower()


def _tokens(t: str) -> list[str]:
    return [w for w in re.findall(r"\w+", _norm(t)) if len(w) > 1]


def chunk_text(text: str, max_chars: int = 900) -> list[tuple[str, str]]:
    """Tách theo Điều/Chương nếu có, còn lại theo đoạn. Trả về [(ref, text)]."""
    chunks: list[tuple[str, str]] = []
    ref, buf, n = "đoạn 1", [], 1

    def flush():
        nonlocal buf, n
        body = "\n".join(buf).strip()
        if body:
            chunks.append((ref, body))
            n += 1
        buf = []

    for line in text.splitlines():
        if _DIEU.match(line):
            flush()
            ref = line.strip()[:80]
        elif sum(len(b) for b in buf) + len(line) > max_chars:
            flush()
            if not _DIEU.match(ref):
                ref = f"đoạn {n}"
        buf.append(line)
    flush()
    return chunks


async def index_text(s: AsyncSession, source: str, text: str, version: str | None = None,
                     document_id: int | None = None, replace: bool = True) -> int:
    if replace:
        await s.execute(delete(KnowledgeChunk).where(KnowledgeChunk.source == source,
                                                     KnowledgeChunk.version == version))
    parts = chunk_text(text)
    for ref, body in parts:
        s.add(KnowledgeChunk(source=source, version=version, ref=ref, text=body, document_id=document_id))
    return len(parts)


async def search(s: AsyncSession, query: str, limit: int = 5) -> list[dict]:
    q = set(_tokens(query))
    if not q:
        return []
    scored = []
    for c in (await s.scalars(select(KnowledgeChunk))).all():
        toks = _tokens(c.text + " " + c.source)
        if not toks:
            continue
        hit = q & set(toks)
        if not hit:
            continue
        score = len(hit) / len(q) + 0.1 * sum(toks.count(w) for w in hit) / len(toks) ** 0.5
        scored.append((score, c))
    scored.sort(key=lambda x: -x[0])
    return [{"source": c.source, "version": c.version, "ref": c.ref, "score": round(sc, 3), "text": c.text}
            for sc, c in scored[:limit]]
