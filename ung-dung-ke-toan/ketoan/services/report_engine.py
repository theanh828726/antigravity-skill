"""Bộ máy báo cáo tài chính theo MẪU QUẢN LÝ PHIÊN BẢN.

Ứng dụng KHÔNG tự đặt chỉ tiêu hay công thức của báo cáo theo quy định. Mẫu (danh sách chỉ tiêu + công thức) do người dùng
nhập từ văn bản đã kiểm chứng; mẫu mới nhập vào ở trạng thái CHƯA KIỂM CHỨNG cho tới khi người có quyền quản trị xác nhận kèm
căn cứ văn bản. Mọi báo cáo/bản in/xuất file từ mẫu chưa kiểm chứng đều mang cảnh báo.

CÔNG THỨC (ví dụ):   DN(111,112)+DN(131)-[130]
  Số hạng : số, [mã chỉ tiêu khác], hàm, ngoặc đơn, dấu âm; phép + - * /
  Hàm lấy số dư (tại cuối kỳ) hoặc phát sinh (trong kỳ) từ SỔ ĐÃ GHI SỔ; đối số là các số hiệu TK, gồm cả TK con:
    DN(..) dư Nợ cuối kỳ        CN(..) dư Có cuối kỳ
    DNDK(..) dư Nợ đầu năm      CNDK(..) dư Có đầu năm        (cột «Đầu năm» của báo cáo dạng BS)
    PSN(..) phát sinh Nợ        PSC(..) phát sinh Có          (trong kỳ)
    PSNDU(TK;TKĐƯ) / PSCDU(TK;TKĐƯ)  phát sinh Nợ / Có của TK đối ứng với TKĐƯ, ví dụ PSNDU(511;911)
Loại mẫu: BS (tình hình tài chính / cân đối – có cột Đầu năm), IS (kết quả kinh doanh), CF (lưu chuyển tiền tệ).
"""
from __future__ import annotations

import re
from datetime import datetime

from ketoan.services.context import BusinessError, Session
from ketoan.services.ledger_service import LedgerService

FUNCS = {"DN", "CN", "DNDK", "CNDK", "PSN", "PSC", "PSNDU", "PSCDU"}
KINDS = {"BS": "Báo cáo tình hình tài chính / Bảng cân đối kế toán", "IS": "Báo cáo kết quả hoạt động kinh doanh",
         "CF": "Báo cáo lưu chuyển tiền tệ"}
_TOKEN = re.compile(r"\s*(?:(\d+(?:\.\d+)?)|(\[[^\]\s]+\])|([A-Z]+)\(([^)]*)\)|(.))")


class FormulaError(BusinessError):
    pass


def tokenize(f: str) -> list[tuple]:
    out, pos = [], 0
    f = f or ""
    while pos < len(f):
        m = _TOKEN.match(f, pos)
        if not m or m.end() == pos:
            break
        num, ref, fn, args, ch = m.groups()
        if num is not None:
            out.append(("num", num))
        elif ref:
            out.append(("ref", ref[1:-1]))
        elif fn:
            if fn not in FUNCS:
                raise FormulaError(f"Hàm '{fn}' không được hỗ trợ (dùng: {', '.join(sorted(FUNCS))}).")
            out.append(("fn", fn, args))
        elif ch and not ch.isspace():
            if ch not in "+-*/()":
                raise FormulaError(f"Ký tự '{ch}' không hợp lệ trong công thức.")
            out.append(("op", ch))
        pos = m.end()
    return out


class _Parser:
    """Bộ phân tích đệ quy → cây biểu thức; dùng chung cho kiểm tra cú pháp và tính giá trị."""

    def __init__(self, tokens):
        self.t, self.i = tokens, 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else None

    def take(self):
        tok = self.peek()
        self.i += 1
        return tok

    def parse(self):
        node = self.expr()
        if self.peek() is not None:
            raise FormulaError("Công thức thừa ký tự ở cuối.")
        return node

    def expr(self):
        node = self.term()
        while self.peek() and self.peek()[0] == "op" and self.peek()[1] in "+-":
            op = self.take()[1]
            node = ("bin", op, node, self.term())
        return node

    def term(self):
        node = self.factor()
        while self.peek() and self.peek()[0] == "op" and self.peek()[1] in "*/":
            op = self.take()[1]
            node = ("bin", op, node, self.factor())
        return node

    def factor(self):
        tok = self.take()
        if tok is None:
            raise FormulaError("Công thức chưa hoàn chỉnh.")
        if tok[0] == "num":
            return ("num", float(tok[1]))
        if tok[0] in ("ref", "fn"):
            return tok
        if tok == ("op", "-"):
            return ("neg", self.factor())
        if tok == ("op", "("):
            node = self.expr()
            if self.take() != ("op", ")"):
                raise FormulaError("Thiếu dấu đóng ngoặc.")
            return node
        raise FormulaError(f"Không hiểu '{tok[1]}' trong công thức.")


def parse(formula: str):
    return _Parser(tokenize(formula)).parse()


def references(node, acc: set | None = None) -> set:
    """Tập mã chỉ tiêu được tham chiếu."""
    acc = set() if acc is None else acc
    if node[0] == "ref":
        acc.add(node[1])
    elif node[0] == "bin":
        references(node[2], acc); references(node[3], acc)
    elif node[0] == "neg":
        references(node[1], acc)
    return acc


def accounts_of(node, acc: list | None = None) -> list:
    """Danh sách số hiệu TK được dùng trong công thức (để truy ngược sổ)."""
    acc = [] if acc is None else acc
    if node[0] == "fn":
        first = node[2].split(";")[0]
        for a in first.split(","):
            a = a.strip()
            if a and a not in acc:
                acc.append(a)
    elif node[0] == "bin":
        accounts_of(node[2], acc); accounts_of(node[3], acc)
    elif node[0] == "neg":
        accounts_of(node[1], acc)
    return acc


class ReportEngine:
    def __init__(self, session: Session):
        self.s = session
        self.db = session.db

    # ------------------------------------------------------------ quản lý mẫu
    def templates(self, kind: str | None = None):
        cond, params = "", [self.s.company_id]
        if kind:
            cond, params = " AND kind=?", params + [kind]
        return self.db.query(f"SELECT * FROM report_template WHERE company_id=?{cond} ORDER BY code, version DESC", params)

    def lines(self, template_id: int):
        return self.db.query("SELECT * FROM report_line WHERE template_id=? ORDER BY seq", (template_id,))

    @staticmethod
    def validate_lines(lines: list[dict]) -> list[str]:
        """Kiểm tra: mã duy nhất, công thức đúng cú pháp, tham chiếu tồn tại, không vòng lặp."""
        errors, codes, graph = [], set(), {}
        for i, l in enumerate(lines, 1):
            code = (l.get("code") or "").strip()
            if not code:
                errors.append(f"Dòng {i}: thiếu mã chỉ tiêu"); continue
            if code in codes:
                errors.append(f"Dòng {i}: mã '{code}' bị lặp")
            codes.add(code)
            if not (l.get("label") or "").strip():
                errors.append(f"Dòng {i} ({code}): thiếu tên chỉ tiêu")
            f = (l.get("formula") or "").strip()
            if f:
                try:
                    graph[code] = references(parse(f))
                except FormulaError as e:
                    errors.append(f"Dòng {i} ({code}): {e}")
        for code, refs in graph.items():
            for r in refs:
                if r not in codes:
                    errors.append(f"{code}: tham chiếu đến chỉ tiêu [{r}] không tồn tại")
        seen: set = set()

        def has_cycle(n, stack):
            if n in stack:
                return True
            if n in seen:
                return False
            seen.add(n)
            return any(has_cycle(m, stack | {n}) for m in graph.get(n, ()) if m in graph)
        for c in graph:
            if has_cycle(c, frozenset()):
                errors.append(f"Công thức vòng tròn liên quan chỉ tiêu {c}")
                break
        return errors

    def import_template(self, code: str, name: str, kind: str, regime_code: str, effective_from: str, source_ref: str,
                        lines: list[dict]) -> int:
        self.s.require("admin", "nhập mẫu báo cáo")
        if kind not in KINDS:
            raise BusinessError("Loại mẫu không hợp lệ (BS / IS / CF).")
        if not code.strip() or not name.strip():
            raise BusinessError("Mã và tên mẫu không được trống.")
        errors = self.validate_lines(lines)
        if not lines:
            errors.append("Mẫu không có chỉ tiêu nào")
        if errors:
            raise BusinessError("Mẫu có lỗi, chưa nhập:\n" + "\n".join(errors[:30]))
        with self.db.transaction():
            version = (self.db.scalar("SELECT MAX(version) FROM report_template WHERE company_id=? AND code=?",
                                      (self.s.company_id, code), 0) or 0) + 1
            tid = self.db.execute("""INSERT INTO report_template(company_id, code, name, kind, regime_code, version, effective_from,
                source_ref, verified, created_by, created_at) VALUES(?,?,?,?,?,?,?,?,0,?,?)""",
                                  (self.s.company_id, code.strip(), name.strip(), kind, regime_code or None, version,
                                   effective_from or None, source_ref or None, self.s.user.username,
                                   datetime.now().isoformat(timespec="seconds"))).lastrowid
            self.db.executemany("INSERT INTO report_line(template_id, seq, code, label, formula, indent, bold) VALUES(?,?,?,?,?,?,?)",
                                [(tid, i, l["code"].strip(), l["label"].strip(), (l.get("formula") or "").strip(),
                                  int(l.get("indent") or 0), 1 if l.get("bold") else 0) for i, l in enumerate(lines, 1)])
            self.s.audit("Nhập mẫu báo cáo", "report_template", f"{code} v{version}", {"so_chi_tieu": len(lines)})
        return tid

    def verify_template(self, template_id: int, note: str):
        self.s.require("admin", "xác nhận kiểm chứng mẫu báo cáo")
        if len((note or "").strip()) < 10:
            raise BusinessError("Cần ghi căn cứ kiểm chứng (số hiệu, điều/phụ lục văn bản, ngày hiệu lực, nguồn chính thức).")
        with self.db.transaction():
            self.db.execute("UPDATE report_template SET verified=1, verified_by=?, verified_at=?, verified_note=? WHERE id=? AND company_id=?",
                            (self.s.user.username, datetime.now().isoformat(timespec="seconds"), note.strip(), template_id,
                             self.s.company_id))
            self.s.audit("Xác nhận kiểm chứng mẫu báo cáo", "report_template", template_id, {"can_cu": note.strip()})

    # ------------------------------------------------------------ tính báo cáo
    def evaluate(self, template_id: int, d_from: str, d_to: str) -> list[dict]:
        t = self.db.one("SELECT * FROM report_template WHERE id=? AND company_id=?", (template_id, self.s.company_id))
        if not t:
            raise BusinessError("Không tìm thấy mẫu báo cáo.")
        lines = [dict(l) for l in self.lines(template_id)]
        trees = {l["code"]: (parse(l["formula"]) if l["formula"] else None) for l in lines}
        ls = LedgerService(self.s)
        tb = {r.code: r for r in ls.trial_balance(d_from, d_to, False).rows}
        year_start = f"{d_to[:4]}-01-01"
        tb_open = None
        if t["kind"] == "BS":     # cột «Đầu năm»: số dư đầu năm tài chính của kỳ đang xem
            tb_open = {r.code: r for r in ls.trial_balance(year_start, year_start, False).rows}
        du_cache: dict = {}

        def du(side, a_group, c_group):
            key = (side, tuple(a_group), tuple(c_group))
            if key not in du_cache:
                total = 0
                for a in a_group:
                    for c in c_group:
                        total += self.db.scalar(f"""SELECT COALESCE(SUM({side}),0) FROM ledger_entry WHERE company_id=?
                            AND account_code LIKE ? AND contra_account LIKE ? AND posting_date BETWEEN ? AND ?""",
                                                (self.s.company_id, a + "%", c + "%", d_from, d_to), 0)
                du_cache[key] = total
            return du_cache[key]

        def fn_value(name, args, opening: bool):
            groups = [[x.strip() for x in g.split(",") if x.strip()] for g in args.split(";")]
            accs = groups[0]
            if name in ("PSNDU", "PSCDU"):
                if len(groups) != 2 or not groups[1]:
                    raise FormulaError(f"{name} cần hai nhóm TK: {name}(TK;TKĐƯ)")
                return du("debit" if name == "PSNDU" else "credit", accs, groups[1])
            total = 0
            for a in accs:
                if name in ("DN", "CN"):
                    if opening:                                  # cột «Đầu năm»: số dư đầu năm tài chính
                        r = (tb_open or {}).get(a)
                        total += (r.ob_d if name == "DN" else r.ob_c) if r else 0
                    else:
                        r = tb.get(a)
                        total += (r.cb_d if name == "DN" else r.cb_c) if r else 0
                elif name in ("DNDK", "CNDK"):
                    r = (tb_open or tb).get(a) if opening else tb.get(a)
                    total += (r.ob_d if name == "DNDK" else r.ob_c) if r else 0
                else:
                    r = tb.get(a)
                    total += (r.ps_d if name == "PSN" else r.ps_c) if r else 0
            return total

        def ev(node, opening, memo):
            k = node[0]
            if k == "num":
                return node[1]
            if k == "neg":
                return -ev(node[1], opening, memo)
            if k == "ref":
                return value_of(node[1], opening, memo)
            if k == "fn":
                return fn_value(node[1], node[2], opening)
            a, b = ev(node[2], opening, memo), ev(node[3], opening, memo)
            return a + b if node[1] == "+" else a - b if node[1] == "-" else a * b if node[1] == "*" else (a / b if b else 0)

        def value_of(code, opening, memo):
            if code not in memo:
                tree = trees.get(code)
                memo[code] = None if tree is None else ev(tree, opening, memo)
            return memo[code]

        out = []
        memo_cur, memo_open = {}, {}
        for l in lines:
            cur = value_of(l["code"], False, memo_cur)
            opn = value_of(l["code"], True, memo_open) if t["kind"] == "BS" else None
            tree = trees.get(l["code"])
            out.append({**l, "value": None if cur is None else round(cur), "open_value": None if opn is None else round(opn),
                        "accounts": accounts_of(tree) if tree else []})
        return out

    # mẫu thử nghiệm kỹ thuật được nạp khi tạo dữ liệu minh họa
    def seed_demo_templates(self):
        bs = [("A", "TÀI SẢN", "", 0, 1), ("A1", "Tiền (TK 111, 112)", "DN(111,112)", 1, 0),
              ("A2", "Phải thu của khách hàng (dư Nợ TK 131)", "DN(131)", 1, 0),
              ("A3", "Trả trước cho người bán (dư Nợ TK 331)", "DN(331)", 1, 0),
              ("A4", "Hàng tồn kho (TK 151–157)", "DN(151,152,153,154,155,156,157)", 1, 0),
              ("A5", "Thuế GTGT được khấu trừ, tạm ứng, chi phí trả trước", "DN(133,141,242)", 1, 0),
              ("A6", "Tài sản cố định – nguyên giá", "DN(211)", 1, 0),
              ("A7", "Hao mòn tài sản cố định", "-CN(214)", 1, 0),
              ("A9", "TỔNG TÀI SẢN", "[A1]+[A2]+[A3]+[A4]+[A5]+[A6]+[A7]", 0, 1),
              ("B", "NGUỒN VỐN", "", 0, 1),
              ("B1", "Phải trả người bán (dư Có TK 331)", "CN(331)", 1, 0),
              ("B2", "Người mua trả tiền trước (dư Có TK 131)", "CN(131)", 1, 0),
              ("B3", "Thuế và các khoản phải nộp (TK 333)", "CN(333)", 1, 0),
              ("B4", "Phải trả người lao động, chi phí phải trả, phải trả khác", "CN(334,335,338)", 1, 0),
              ("B5", "Vốn đầu tư của chủ sở hữu", "CN(411)", 1, 0),
              ("B6", "Lợi nhuận sau thuế chưa phân phối", "CN(421)-DN(421)", 1, 0),
              ("B7", "Kết quả chưa kết chuyển trong năm (doanh thu, thu nhập − chi phí)",
               "CN(511,515,711)-DN(511,515,711)-DN(632,635,642,811,821)+CN(632,635,642,811,821)", 1, 0),
              ("B9", "TỔNG NGUỒN VỐN", "[B1]+[B2]+[B3]+[B4]+[B5]+[B6]+[B7]", 0, 1),
              ("K", "Kiểm tra: Tổng tài sản − Tổng nguồn vốn (phải bằng 0)", "[A9]-[B9]", 0, 0)]
        is_ = [("1", "Doanh thu thuần bán hàng và cung cấp dịch vụ", "PSC(511)-PSN(511)+PSNDU(511;911)", 0, 0),
               ("2", "Giá vốn hàng bán", "PSN(632)-PSC(632)+PSCDU(632;911)", 0, 0),
               ("3", "Lợi nhuận gộp", "[1]-[2]", 0, 1),
               ("4", "Doanh thu hoạt động tài chính", "PSC(515)-PSN(515)+PSNDU(515;911)", 0, 0),
               ("5", "Chi phí tài chính", "PSN(635)-PSC(635)+PSCDU(635;911)", 0, 0),
               ("6", "Chi phí quản lý kinh doanh", "PSN(642)-PSC(642)+PSCDU(642;911)", 0, 0),
               ("7", "Lợi nhuận thuần từ hoạt động kinh doanh", "[3]+[4]-[5]-[6]", 0, 1),
               ("8", "Thu nhập khác", "PSC(711)-PSN(711)+PSNDU(711;911)", 0, 0),
               ("9", "Chi phí khác", "PSN(811)-PSC(811)+PSCDU(811;911)", 0, 0),
               ("10", "Lợi nhuận kế toán trước thuế", "[7]+[8]-[9]", 0, 1),
               ("11", "Chi phí thuế thu nhập doanh nghiệp", "PSN(821)-PSC(821)+PSCDU(821;911)", 0, 0),
               ("12", "Lợi nhuận sau thuế", "[10]-[11]", 0, 1)]
        note = ("MẪU THỬ NGHIỆM KỸ THUẬT – không phải mẫu báo cáo theo văn bản; chỉ tiêu và công thức chưa được đối chiếu "
                "với văn bản chính thức.")
        for code, name, kind, rows in (("DEMO_BS", "Bảng cân đối – mẫu thử nghiệm kỹ thuật", "BS", bs),
                                       ("DEMO_IS", "Kết quả kinh doanh – mẫu thử nghiệm kỹ thuật", "IS", is_)):
            self.import_template(code, name, kind, "", "", note,
                                 [{"code": c, "label": lb, "formula": f, "indent": ind, "bold": b} for c, lb, f, ind, b in rows])
