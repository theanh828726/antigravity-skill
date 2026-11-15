"""Người dùng, vai trò, phân quyền, mật khẩu (PBKDF2-SHA256)."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta

from ketoan.data.db import Database
from ketoan.domain.constants import PERMISSION_CODES
from ketoan.services.context import BusinessError, CurrentUser, Session

PBKDF2_ROUNDS = int(os.environ.get("KETOAN_PBKDF2_ROUNDS", "600000"))     # khuyến nghị hiện hành cho PBKDF2-SHA256
MAX_FAILED = 5                      # số lần nhập sai liên tiếp trước khi khóa tạm
LOCK_MINUTES = 5
# Mật khẩu mặc định của dữ liệu minh họa / dữ liệu mới: đăng nhập bằng các mật khẩu này buộc phải đổi
DEFAULT_PASSWORDS = {"admin@123", "ktt@123", "ktv@123", "xem@123"}
GENERIC_FAIL = "Tên đăng nhập hoặc mật khẩu không đúng."


def hash_password(password: str, salt: str | None = None, rounds: int | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), rounds or PBKDF2_ROUNDS).hex()
    return salt, digest


def validate_password(password: str, username: str = ""):
    """Chính sách mật khẩu: tối thiểu 8 ký tự, có chữ và số, không trùng tên đăng nhập hoặc mật khẩu mặc định."""
    if len(password) < 8:
        raise BusinessError("Mật khẩu tối thiểu 8 ký tự.")
    if not (any(c.isalpha() for c in password) and any(c.isdigit() for c in password)):
        raise BusinessError("Mật khẩu phải có cả chữ và số.")
    if username and password.lower() == username.strip().lower():
        raise BusinessError("Mật khẩu không được trùng tên đăng nhập.")
    if password in DEFAULT_PASSWORDS:
        raise BusinessError("Không dùng mật khẩu mặc định của hệ thống.")


def _audit(db, username: str, action: str, detail: str = ""):
    db.execute("INSERT INTO audit_log(ts, username, company_id, action, entity, entity_id, detail) VALUES(?,?,?,?,?,?,?)",
               (datetime.now().isoformat(timespec="seconds"), username, None, action, "app_user", username, detail or None))


def authenticate(db: Database, username: str, password: str) -> CurrentUser:
    """Xác thực. Thông báo lỗi chung (không lộ tên đăng nhập có tồn tại hay không); sai quá MAX_FAILED lần thì khóa tạm."""
    username = username.strip()
    row = db.one("""SELECT u.*, r.name AS role_name, r.permissions FROM app_user u JOIN role r ON r.code=u.role_code
                    WHERE u.username=?""", (username,))
    now = datetime.now()
    if row and row["locked_until"] and row["locked_until"] > now.isoformat(timespec="seconds"):
        _audit(db, username, "Đăng nhập bị từ chối (đang khóa tạm)")
        raise BusinessError(f"Tài khoản tạm khóa đến {row['locked_until'][11:16]} do nhập sai mật khẩu nhiều lần. Vui lòng thử lại sau.")
    # luôn băm một lần để thời gian phản hồi không lộ tài khoản có tồn tại hay không
    _, digest = hash_password(password, row["pwd_salt"] if row else "00" * 16, row["pwd_rounds"] if row else None)
    if not row or not row["active"] or not hmac.compare_digest(digest, row["pwd_hash"]):
        if row and row["active"]:
            failed = row["failed_attempts"] + 1
            lock = (now + timedelta(minutes=LOCK_MINUTES)).isoformat(timespec="seconds") if failed >= MAX_FAILED else None
            db.execute("UPDATE app_user SET failed_attempts=?, locked_until=? WHERE id=?", (0 if lock else failed, lock, row["id"]))
        _audit(db, username, "Đăng nhập thất bại")
        raise BusinessError(GENERIC_FAIL)
    must_change = password in DEFAULT_PASSWORDS
    if row["failed_attempts"] or row["locked_until"] or row["pwd_rounds"] < PBKDF2_ROUNDS:
        sets, params = ["failed_attempts=0", "locked_until=NULL"], []
        if row["pwd_rounds"] < PBKDF2_ROUNDS:          # nâng cấp độ mạnh băm khi người dùng đăng nhập thành công
            salt, new_digest = hash_password(password)
            sets += ["pwd_salt=?", "pwd_hash=?", "pwd_rounds=?"]
            params += [salt, new_digest, PBKDF2_ROUNDS]
        db.execute(f"UPDATE app_user SET {', '.join(sets)} WHERE id=?", params + [row["id"]])
    _audit(db, username, "Đăng nhập")
    perms = {p for p in (row["permissions"] or "").split(",") if p}
    return CurrentUser(row["username"], row["full_name"] or row["username"], row["role_code"], row["role_name"], perms, must_change)


def change_password(db: Database, username: str, old: str, new: str):
    """Người dùng tự đổi mật khẩu (xác thực lại mật khẩu cũ)."""
    authenticate(db, username, old)
    validate_password(new, username)
    salt, digest = hash_password(new)
    db.execute("UPDATE app_user SET pwd_salt=?, pwd_hash=?, pwd_rounds=?, failed_attempts=0, locked_until=NULL WHERE username=?",
               (salt, digest, PBKDF2_ROUNDS, username))
    _audit(db, username, "Đổi mật khẩu")


def ensure_default_roles(db: Database):
    roles = [
        ("ADMIN", "Quản trị hệ thống", ",".join(PERMISSION_CODES)),
        ("KTT", "Kế toán trưởng", "view,add,edit,delete,post,lock,export"),
        ("KTV", "Kế toán viên", "view,add,edit,delete,export"),
        ("XEM", "Chỉ xem", "view"),
    ]
    for code, name, perms in roles:
        db.execute("INSERT INTO role(code, name, permissions) VALUES(?,?,?) ON CONFLICT DO NOTHING", (code, name, perms))


def create_user(db: Database, username: str, full_name: str, role_code: str, password: str, enforce_policy: bool = True):
    if not username.strip():
        raise BusinessError("Tên đăng nhập không được trống.")
    if enforce_policy:
        validate_password(password, username)
    salt, digest = hash_password(password)
    db.execute("INSERT INTO app_user(username, full_name, role_code, pwd_salt, pwd_hash, pwd_rounds) VALUES(?,?,?,?,?,?)",
               (username.strip(), full_name, role_code, salt, digest, PBKDF2_ROUNDS))


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
                    validate_password(password, username)
                    salt, digest = hash_password(password)
                    self.db.execute("UPDATE app_user SET pwd_salt=?, pwd_hash=?, pwd_rounds=?, failed_attempts=0, locked_until=NULL WHERE id=?",
                                    (salt, digest, PBKDF2_ROUNDS, user_id))
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
