"""Người dùng, vai trò, phân quyền, mật khẩu (PBKDF2-SHA256)."""
from __future__ import annotations

import hashlib
import hmac
import secrets

from ketoan.data.db import Database
from ketoan.domain.constants import PERMISSION_CODES
from ketoan.services.context import BusinessError, CurrentUser, Session

PBKDF2_ROUNDS = 120_000


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ROUNDS).hex()
    return salt, digest


def authenticate(db: Database, username: str, password: str) -> CurrentUser:
    row = db.one("""SELECT u.*, r.name AS role_name, r.permissions FROM app_user u JOIN role r ON r.code=u.role_code
                    WHERE u.username=?""", (username.strip(),))
    if not row or not row["active"]:
        raise BusinessError("Tên đăng nhập không tồn tại hoặc đã bị khóa.")
    _, digest = hash_password(password, row["pwd_salt"])
    if not hmac.compare_digest(digest, row["pwd_hash"]):
        raise BusinessError("Mật khẩu không đúng.")
    perms = {p for p in (row["permissions"] or "").split(",") if p}
    return CurrentUser(row["username"], row["full_name"] or row["username"], row["role_code"], row["role_name"], perms)


def ensure_default_roles(db: Database):
    roles = [
        ("ADMIN", "Quản trị hệ thống", ",".join(PERMISSION_CODES)),
        ("KTT", "Kế toán trưởng", "view,add,edit,delete,post,lock,export"),
        ("KTV", "Kế toán viên", "view,add,edit,delete,export"),
        ("XEM", "Chỉ xem", "view"),
    ]
    for code, name, perms in roles:
        db.execute("INSERT OR IGNORE INTO role(code, name, permissions) VALUES(?,?,?)", (code, name, perms))


def create_user(db: Database, username: str, full_name: str, role_code: str, password: str):
    if not username.strip():
        raise BusinessError("Tên đăng nhập không được trống.")
    if len(password) < 6:
        raise BusinessError("Mật khẩu tối thiểu 6 ký tự.")
    salt, digest = hash_password(password)
    db.execute("INSERT INTO app_user(username, full_name, role_code, pwd_salt, pwd_hash) VALUES(?,?,?,?,?)",
               (username.strip(), full_name, role_code, salt, digest))


class UserService:
    def __init__(self, session: Session):
        self.s = session
        self.db = session.db

    def users(self):
        return self.db.query("""SELECT u.id, u.username, u.full_name, u.role_code, r.name AS role_name, u.active
                                FROM app_user u JOIN role r ON r.code=u.role_code ORDER BY u.username""")

    def roles(self):
        return self.db.query("SELECT * FROM role ORDER BY code")

    def save_user(self, user_id, username, full_name, role_code, active, password=""):
        self.s.require("admin", "quản lý người dùng")
        with self.db.transaction():
            if user_id:
                if password:
                    if len(password) < 6:
                        raise BusinessError("Mật khẩu tối thiểu 6 ký tự.")
                    salt, digest = hash_password(password)
                    self.db.execute("UPDATE app_user SET pwd_salt=?, pwd_hash=? WHERE id=?", (salt, digest, user_id))
                if username == self.s.user.username and not active:
                    raise BusinessError("Không thể tự khóa tài khoản đang đăng nhập.")
                self.db.execute("UPDATE app_user SET full_name=?, role_code=?, active=? WHERE id=?",
                                (full_name, role_code, 1 if active else 0, user_id))
                self.s.audit("Sửa người dùng", "app_user", username, {"role": role_code, "active": active})
            else:
                if self.db.scalar("SELECT 1 FROM app_user WHERE username=?", (username,)):
                    raise BusinessError(f"Tên đăng nhập '{username}' đã tồn tại.")
                create_user(self.db, username, full_name, role_code, password)
                self.s.audit("Thêm người dùng", "app_user", username, {"role": role_code})

    def save_role_permissions(self, role_code: str, perms: set):
        self.s.require("admin", "phân quyền")
        if role_code == "ADMIN" and "admin" not in perms:
            raise BusinessError("Vai trò Quản trị hệ thống phải giữ quyền quản trị.")
        with self.db.transaction():
            self.db.execute("UPDATE role SET permissions=? WHERE code=?",
                            (",".join(p for p in PERMISSION_CODES if p in perms), role_code))
            self.s.audit("Phân quyền", "role", role_code, sorted(perms))
