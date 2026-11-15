-- Lược đồ CSDL Ứng dụng Kế toán (SQLite). Tiền lưu INTEGER (đồng); số lượng/đơn giá lưu TEXT Decimal.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- ===================================================== Chế độ kế toán (quản lý phiên bản)
CREATE TABLE IF NOT EXISTS accounting_regime (
    code           TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    legal_ref      TEXT NOT NULL,
    effective_from TEXT,
    effective_to   TEXT,
    verified       INTEGER NOT NULL DEFAULT 0,  -- 1: đã kiểm chứng văn bản gốc
    verified_note  TEXT,
    note           TEXT
);

CREATE TABLE IF NOT EXISTS company (
    id         INTEGER PRIMARY KEY,
    code       TEXT NOT NULL UNIQUE,
    name       TEXT NOT NULL,
    tax_code   TEXT,
    address    TEXT,
    business   TEXT,                 -- thương mại, dịch vụ, sản xuất, xây dựng, vận tải
    director   TEXT,
    chief_accountant TEXT,
    currency   TEXT NOT NULL DEFAULT 'VND',
    is_demo    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS company_regime (
    id             INTEGER PRIMARY KEY,
    company_id     INTEGER NOT NULL REFERENCES company(id) ON DELETE CASCADE,
    regime_code    TEXT NOT NULL REFERENCES accounting_regime(code),
    effective_from TEXT NOT NULL,
    UNIQUE(company_id, effective_from)
);

CREATE TABLE IF NOT EXISTS fiscal_year (
    id         INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES company(id) ON DELETE CASCADE,
    year       INTEGER NOT NULL,
    start_date TEXT NOT NULL,
    end_date   TEXT NOT NULL,
    UNIQUE(company_id, year)
);

CREATE TABLE IF NOT EXISTS period_lock (
    company_id INTEGER NOT NULL REFERENCES company(id) ON DELETE CASCADE,
    year       INTEGER NOT NULL,
    month      INTEGER NOT NULL,
    locked_by  TEXT,
    locked_at  TEXT,
    PRIMARY KEY (company_id, year, month)
);

-- Thuế suất GTGT: cấu hình theo hiệu lực; dữ liệu mẫu cần kiểm chứng trước khi dùng thật
CREATE TABLE IF NOT EXISTS tax_rate (
    id             INTEGER PRIMARY KEY,
    code           TEXT NOT NULL,
    name           TEXT NOT NULL,
    rate           TEXT NOT NULL,
    effective_from TEXT,
    effective_to   TEXT,
    legal_ref      TEXT,
    verified       INTEGER NOT NULL DEFAULT 0,
    UNIQUE(code, effective_from)
);

-- ===================================================== Danh mục
CREATE TABLE IF NOT EXISTS account (
    id             INTEGER PRIMARY KEY,
    company_id     INTEGER NOT NULL REFERENCES company(id) ON DELETE CASCADE,
    code           TEXT NOT NULL,
    name           TEXT NOT NULL,
    parent_code    TEXT,
    level          INTEGER NOT NULL DEFAULT 1,
    nature         TEXT NOT NULL DEFAULT 'L',   -- N: dư Nợ, C: dư Có, L: lưỡng tính
    is_detail      INTEGER NOT NULL DEFAULT 1,  -- chỉ TK chi tiết mới được hạch toán
    require_partner INTEGER NOT NULL DEFAULT 0, -- bắt buộc đối tượng
    active         INTEGER NOT NULL DEFAULT 1,
    UNIQUE(company_id, code)
);

CREATE TABLE IF NOT EXISTS partner (
    id         INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES company(id) ON DELETE CASCADE,
    code       TEXT NOT NULL,
    name       TEXT NOT NULL,
    kind       TEXT NOT NULL DEFAULT 'KH',   -- KH khách hàng | NCC nhà cung cấp | NV nhân viên | KHAC
    tax_code   TEXT,
    address    TEXT,
    phone      TEXT,
    email      TEXT,
    payment_terms INTEGER DEFAULT 0,         -- số ngày hạn thanh toán
    active     INTEGER NOT NULL DEFAULT 1,
    UNIQUE(company_id, code)
);

CREATE TABLE IF NOT EXISTS item (
    id         INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES company(id) ON DELETE CASCADE,
    code       TEXT NOT NULL,
    name       TEXT NOT NULL,
    unit       TEXT,
    kind       TEXT NOT NULL DEFAULT 'HH',   -- HH hàng hóa | VT vật tư | TP thành phẩm | CCDC | DV dịch vụ
    stock_account TEXT,
    tax_rate   TEXT,
    active     INTEGER NOT NULL DEFAULT 1,
    UNIQUE(company_id, code)
);

CREATE TABLE IF NOT EXISTS warehouse (
    id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES company(id) ON DELETE CASCADE,
    code TEXT NOT NULL, name TEXT NOT NULL, address TEXT, active INTEGER NOT NULL DEFAULT 1,
    UNIQUE(company_id, code));

CREATE TABLE IF NOT EXISTS project (
    id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES company(id) ON DELETE CASCADE,
    code TEXT NOT NULL, name TEXT NOT NULL, customer TEXT, start_date TEXT, end_date TEXT,
    active INTEGER NOT NULL DEFAULT 1, UNIQUE(company_id, code));

CREATE TABLE IF NOT EXISTS department (
    id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES company(id) ON DELETE CASCADE,
    code TEXT NOT NULL, name TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
    UNIQUE(company_id, code));

CREATE TABLE IF NOT EXISTS expense_item (
    id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES company(id) ON DELETE CASCADE,
    code TEXT NOT NULL, name TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
    UNIQUE(company_id, code));

CREATE TABLE IF NOT EXISTS fixed_asset (
    id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES company(id) ON DELETE CASCADE,
    code TEXT NOT NULL, name TEXT NOT NULL, asset_account TEXT, depreciation_account TEXT,
    expense_account TEXT, original_cost INTEGER NOT NULL DEFAULT 0, start_date TEXT,
    useful_months INTEGER, department TEXT, active INTEGER NOT NULL DEFAULT 1,
    UNIQUE(company_id, code));

-- ===================================================== Số dư đầu kỳ (đầu năm tài chính)
CREATE TABLE IF NOT EXISTS opening_balance (
    id           INTEGER PRIMARY KEY,
    company_id   INTEGER NOT NULL REFERENCES company(id) ON DELETE CASCADE,
    year         INTEGER NOT NULL,
    account_code TEXT NOT NULL,
    partner_id   INTEGER REFERENCES partner(id),
    debit        INTEGER NOT NULL DEFAULT 0,
    credit       INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_ob ON opening_balance(company_id, year, account_code);

-- ===================================================== Chứng từ
CREATE TABLE IF NOT EXISTS voucher (
    id            INTEGER PRIMARY KEY,
    company_id    INTEGER NOT NULL REFERENCES company(id) ON DELETE CASCADE,
    vtype         TEXT NOT NULL,
    number        TEXT NOT NULL,
    voucher_date  TEXT NOT NULL,
    posting_date  TEXT NOT NULL,
    partner_id    INTEGER REFERENCES partner(id),
    partner_name  TEXT,
    tax_code      TEXT,
    description   TEXT,
    invoice_no    TEXT,
    invoice_series TEXT,
    invoice_date  TEXT,
    status        TEXT NOT NULL DEFAULT 'DRAFT',
    total_amount  INTEGER NOT NULL DEFAULT 0,
    total_tax     INTEGER NOT NULL DEFAULT 0,
    total_payment INTEGER NOT NULL DEFAULT 0,
    created_by    TEXT, created_at TEXT,
    updated_by    TEXT, updated_at TEXT,
    checked_by    TEXT, checked_at TEXT,
    posted_by     TEXT, posted_at TEXT,
    UNIQUE(company_id, vtype, number)
);
CREATE INDEX IF NOT EXISTS ix_voucher_date ON voucher(company_id, posting_date);

CREATE TABLE IF NOT EXISTS voucher_line (
    id             INTEGER PRIMARY KEY,
    voucher_id     INTEGER NOT NULL REFERENCES voucher(id) ON DELETE CASCADE,
    line_no        INTEGER NOT NULL,
    description    TEXT,
    debit_account  TEXT,
    credit_account TEXT,
    debit_partner_id  INTEGER REFERENCES partner(id),
    credit_partner_id INTEGER REFERENCES partner(id),
    item_id        INTEGER REFERENCES item(id),
    warehouse_id   INTEGER REFERENCES warehouse(id),
    unit           TEXT,
    quantity       TEXT NOT NULL DEFAULT '0',
    unit_price     TEXT NOT NULL DEFAULT '0',
    amount         INTEGER NOT NULL DEFAULT 0,
    tax_rate       TEXT,
    tax_amount     INTEGER NOT NULL DEFAULT 0,
    project_id     INTEGER REFERENCES project(id),
    department_id  INTEGER REFERENCES department(id),
    expense_item_id INTEGER REFERENCES expense_item(id)
);
CREATE INDEX IF NOT EXISTS ix_line_voucher ON voucher_line(voucher_id);

-- Sổ cái chung: chỉ sinh ra khi Ghi sổ, xóa khi Bỏ ghi sổ. Mỗi dòng truy ngược về voucher/line.
CREATE TABLE IF NOT EXISTS ledger_entry (
    id             INTEGER PRIMARY KEY,
    company_id     INTEGER NOT NULL,
    voucher_id     INTEGER NOT NULL REFERENCES voucher(id),
    line_id        INTEGER REFERENCES voucher_line(id),
    posting_date   TEXT NOT NULL,
    account_code   TEXT NOT NULL,
    contra_account TEXT,
    partner_id     INTEGER,
    item_id        INTEGER,
    warehouse_id   INTEGER,
    quantity       TEXT,
    project_id     INTEGER,
    department_id  INTEGER,
    expense_item_id INTEGER,
    debit          INTEGER NOT NULL DEFAULT 0,
    credit         INTEGER NOT NULL DEFAULT 0,
    description    TEXT,
    is_tax         INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_le_acc ON ledger_entry(company_id, account_code, posting_date);
CREATE INDEX IF NOT EXISTS ix_le_voucher ON ledger_entry(voucher_id);

-- ===================================================== Hệ thống
CREATE TABLE IF NOT EXISTS role (
    code        TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    permissions TEXT NOT NULL      -- danh sách mã quyền, phân tách dấu phẩy
);

CREATE TABLE IF NOT EXISTS app_user (
    id        INTEGER PRIMARY KEY,
    username  TEXT NOT NULL UNIQUE,
    full_name TEXT,
    role_code TEXT NOT NULL REFERENCES role(code),
    pwd_salt  TEXT NOT NULL,
    pwd_hash  TEXT NOT NULL,
    active    INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY,
    ts         TEXT NOT NULL,
    username   TEXT,
    company_id INTEGER,
    action     TEXT NOT NULL,
    entity     TEXT,
    entity_id  TEXT,
    detail     TEXT
);
CREATE INDEX IF NOT EXISTS ix_audit_ts ON audit_log(ts);
