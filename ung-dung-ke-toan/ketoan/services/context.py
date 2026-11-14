"""Ngữ cảnh phiên làm việc: CSDL, người dùng, doanh nghiệp, kỳ đang chọn."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime

from ketoan.data.db import Database
from ketoan.domain.constants import PERMISSION_CODES, PERMISSIONS


class PermissionDenied(Exception):
    pass


class BusinessError(Exception):
    """Lỗi nghiệp vụ hiển thị trực tiếp cho người dùng."""


@dataclass
class CurrentUser:
    username: str
    full_name: str
    role_code: str
    role_name: str
    permissions: set = field(default_factory=set)

    def can(self, perm: str) -> bool:
        return "admin" in self.permissions or perm in self.permissions


@dataclass
class Session:
    db: Database
    user: CurrentUser
    company_id: int = 0
    year: int = date.today().year
    date_from: date = date(date.today().year, 1, 1)
    date_to: date = date(date.today().year, 12, 31)
    period_label: str = "Cả năm"

    # -------------------------------------------------------------- quyền
    def require(self, perm: str, action: str = ""):
        if perm not in PERMISSION_CODES:
            raise ValueError(perm)
        if not self.user.can(perm):
            label = dict(PERMISSIONS)[perm]
            raise PermissionDenied(
                f"Người dùng '{self.user.username}' không có quyền «{label}»" + (f" để {action}." if action else "."))

    # -------------------------------------------------------------- nhật ký
    def audit(self, action: str, entity: str = "", entity_id="", detail=None):
        self.db.execute(
            "INSERT INTO audit_log(ts, username, company_id, action, entity, entity_id, detail) VALUES(?,?,?,?,?,?,?)",
            (datetime.now().isoformat(timespec="seconds"), self.user.username, self.company_id, action, entity,
             str(entity_id), json.dumps(detail, ensure_ascii=False, default=str) if detail is not None else None))

    # -------------------------------------------------------------- doanh nghiệp
    @property
    def company(self):
        return self.db.one("SELECT * FROM company WHERE id=?", (self.company_id,))

    def regime_for(self, on_date: str | None = None):
        on_date = on_date or self.date_to.isoformat()
        return self.db.one(
            """SELECT r.* , cr.effective_from AS applied_from FROM company_regime cr
               JOIN accounting_regime r ON r.code = cr.regime_code
               WHERE cr.company_id=? AND cr.effective_from<=? ORDER BY cr.effective_from DESC LIMIT 1""",
            (self.company_id, on_date))

    def set_period(self, d_from: date, d_to: date, label: str):
        self.date_from, self.date_to, self.period_label = d_from, d_to, label
