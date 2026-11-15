"""In hồ sơ kế toán hàng loạt: xuất PDF các sổ và chứng từ của kỳ vào một thư mục kèm mục lục."""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from pathlib import Path

from ketoan.domain.constants import VOUCHER_TYPES
from ketoan.domain.money import fmt_decimal
from ketoan.reports import export
from ketoan.services.context import Session
from ketoan.services.ledger_service import LedgerService
from ketoan.services.voucher_service import VoucherService

ITEMS = [("cdps", "Bảng cân đối số phát sinh"), ("nkc", "Sổ nhật ký chung"), ("socai", "Sổ cái (mọi tài khoản có phát sinh)"),
         ("soquy", "Sổ quỹ tiền mặt"), ("sotgnh", "Sổ tiền gửi ngân hàng"), ("chungtu", "Chứng từ đã ghi sổ (mỗi chứng từ một trang)")]


def vn(d: str) -> str:
    return f"{d[8:10]}/{d[5:7]}/{d[:4]}"


def _slug(text: str) -> str:
    s = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D"))
    return re.sub(r"[^A-Za-z0-9]+", "_", "".join(ch for ch in s if unicodedata.category(ch) != "Mn")).strip("_")[:50]


def _page_break(html_parts: list[str]) -> str:
    return '<div style="page-break-after:always"></div>'.join(html_parts)


def _table(headers, rows, money, total_rows=()):
    return export.to_html("", "", "", headers, rows, set(money), set(total_rows))


def build(session: Session, selected: list[str], d_from: str, d_to: str, folder: str | Path) -> list[Path]:
    session.require("export", "in hồ sơ")
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    c = session.company
    company = f"{c['name']} – MST: {c['tax_code'] or ''}"
    sub = f"Từ ngày {vn(d_from)} đến ngày {vn(d_to)}"
    ls = LedgerService(session)
    signers = ["Người lập biểu", "Kế toán trưởng", "Giám đốc"]
    files: list[Path] = []

    def write(name: str, title: str, headers, rows, money, totals=()):
        path = folder / f"{len(files) + 1:02d}_{_slug(name)}.pdf"
        export.export_pdf(str(path), export.to_html(title, sub, company, headers, rows, set(money), set(totals), signers), True)
        files.append(path)

    if "cdps" in selected:
        tb = ls.trial_balance(d_from, d_to)
        rows = [[r.code, r.name, r.ob_d, r.ob_c, r.ps_d, r.ps_c, r.cb_d, r.cb_c] for r in tb.rows]
        t = tb.total
        rows.append(["", "TỔNG CỘNG", t.ob_d, t.ob_c, t.ps_d, t.ps_c, t.cb_d, t.cb_c])
        write("Bang can doi so phat sinh", "Bảng cân đối số phát sinh",
              ["Số hiệu TK", "Tên tài khoản", "Dư Nợ đầu kỳ", "Dư Có đầu kỳ", "Phát sinh Nợ", "Phát sinh Có", "Dư Nợ cuối kỳ", "Dư Có cuối kỳ"],
              rows, range(2, 8), {len(rows) - 1})
    if "nkc" in selected:
        rows = [[vn(r["posting_date"]), r["number"], r["description"] or "", r["account_code"], r["contra_account"] or "", r["debit"], r["credit"]]
                for r in ls.general_journal(d_from, d_to)]
        rows.append(["", "", "Cộng phát sinh", "", "", sum(r[5] for r in rows), sum(r[6] for r in rows)])
        write("So nhat ky chung", "Sổ nhật ký chung", ["Ngày ghi sổ", "Số CT", "Diễn giải", "TK", "TK đối ứng", "Phát sinh Nợ", "Phát sinh Có"],
              rows, (5, 6), {len(rows) - 1})
    if "socai" in selected:
        sections = []
        for a in ls.accounts():
            if not a["is_detail"]:
                continue
            d = ls.account_detail(a["code"], d_from, d_to)
            if not d["rows"] and not d["opening"]:
                continue
            rows = [["", "", "Số dư đầu kỳ", "", max(d["opening"], 0), max(-d["opening"], 0)]]
            rows += [[vn(r["posting_date"]), r["number"], r["description"] or "", r["contra_account"] or "", r["debit"], r["credit"]]
                     for r in d["rows"]]
            rows.append(["", "", "Cộng phát sinh", "", d["total_d"], d["total_c"]])
            rows.append(["", "", "Số dư cuối kỳ", "", max(d["closing"], 0), max(-d["closing"], 0)])
            body = export.to_html(f"Sổ cái TK {a['code']} – {a['name']}", sub, company,
                                  ["Ngày", "Số CT", "Diễn giải", "TK đối ứng", "Nợ", "Có"], rows, {4, 5}, {0, len(rows) - 2, len(rows) - 1})
            sections.append(re.sub(r"</?(html|head|body)[^>]*>|<style>.*?</style>", "", body, flags=re.S))
        if sections:
            path = folder / f"{len(files) + 1:02d}_So_cai.pdf"
            export.export_pdf(str(path), "<html><body>" + _page_break(sections) + "</body></html>", True)
            files.append(path)
    for key, acc, title in (("soquy", "111", "Sổ quỹ tiền mặt"), ("sotgnh", "112", "Sổ tiền gửi ngân hàng")):
        if key in selected:
            d = ls.account_detail(acc, d_from, d_to)
            rows = [["", "", "Số dư đầu kỳ", "", "", "", d["opening"]]]
            rows += [[vn(r["posting_date"]), r["number"], r["description"] or "", r["contra_account"] or "", r["debit"], r["credit"], r["balance"]]
                     for r in d["rows"]]
            rows.append(["", "", "Cộng phát sinh / số dư cuối kỳ", "", d["total_d"], d["total_c"], d["closing"]])
            write(title, title, ["Ngày", "Số CT", "Diễn giải", "TK đối ứng", "Thu / Gửi vào", "Chi / Rút ra", "Tồn"], rows, (4, 5, 6), {0, len(rows) - 1})
    if "chungtu" in selected:
        vs = VoucherService(session)
        sections = []
        for v in vs.list(None, d_from, d_to, "POSTED"):
            full = vs.get(v["id"])
            vt = VOUCHER_TYPES[full["vtype"]]
            rows = [[l["line_no"], l["description"] or "", l["debit_account"] or "", l["credit_account"] or "", l["item"] or "",
                     fmt_decimal(l["quantity"]) if l["quantity"] not in ("0", None) else "", l["amount"], l["tax_amount"]] for l in full["lines"]]
            rows.append(["", "Tổng", "", "", "", "", full["total_amount"], full["total_tax"]])
            head = (f"Số: {full['number']} · Ngày CT: {vn(full['voucher_date'])} · Ngày HT: {vn(full['posting_date'])} · Đối tượng: "
                    f"{full['partner_code'] or ''} {full['partner_name'] or ''} · {full['description'] or ''}")
            if full["invoice_no"]:
                head += f" · HĐ {full['invoice_series'] or ''} số {full['invoice_no']}"
            body = export.to_html(vt.name, head, company, ["STT", "Diễn giải", "TK Nợ", "TK Có", "Mã hàng", "Số lượng", "Thành tiền", "Tiền thuế"],
                                  rows, {6, 7}, {len(rows) - 1}, ["Người lập", "Kế toán trưởng", "Giám đốc"])
            sections.append(re.sub(r"</?(html|head|body)[^>]*>|<style>.*?</style>", "", body, flags=re.S))
        if sections:
            path = folder / f"{len(files) + 1:02d}_Chung_tu_da_ghi_so.pdf"
            export.export_pdf(str(path), "<html><body>" + _page_break(sections) + "</body></html>", False)
            files.append(path)
    index = folder / "00_MUC_LUC.txt"
    index.write_text("\n".join([f"{company}", f"Hồ sơ kế toán {sub}", f"Lập lúc {datetime.now():%d/%m/%Y %H:%M} bởi {session.user.username}", ""] +
                               [f"{i}. {p.name}" for i, p in enumerate(files, 1)]) + "\n", encoding="utf-8")
    files.insert(0, index)
    session.db.execute("INSERT INTO audit_log(ts, username, company_id, action, entity, entity_id, detail) VALUES(?,?,?,?,?,?,?)",
                       (datetime.now().isoformat(timespec="seconds"), session.user.username, session.company_id, "In hồ sơ", "folder",
                        str(folder), f"{len(files) - 1} file, {d_from}..{d_to}"))
    return files

