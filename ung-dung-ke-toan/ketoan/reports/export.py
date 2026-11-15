"""Xuất báo cáo: Excel (openpyxl), PDF và in / xem trước khi in (Qt PrintSupport).

Dữ liệu vào là bảng chuẩn: headers + rows, với mỗi ô là str | int | Decimal; cột tiền giữ dạng số khi xuất Excel.
"""
from __future__ import annotations

import html
from datetime import datetime
from decimal import Decimal

from ketoan.domain.money import fmt_decimal, fmt_money


def _is_num(v) -> bool:
    return isinstance(v, (int, Decimal)) and not isinstance(v, bool)


def export_excel(path: str, title: str, subtitle: str, company: str, headers: list[str], rows: list[list],
                 money_cols: set[int] | None = None, total_rows: set[int] | None = None):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    money_cols = money_cols or set()
    total_rows = total_rows or set()
    wb = Workbook()
    ws = wb.active
    ws.title = (title[:28] or "Bao cao").replace("/", "-")
    ncol = len(headers)
    ws.cell(1, 1, company).font = Font(bold=True)
    ws.cell(2, 1, title.upper()).font = Font(bold=True, size=14, color="123B6D")
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=max(ncol, 1))
    ws.cell(2, 1).alignment = Alignment(horizontal="center")
    ws.cell(3, 1, subtitle).alignment = Alignment(horizontal="center")
    ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=max(ncol, 1))
    thin = Side(style="thin", color="B7C3D3")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    head_fill = PatternFill("solid", fgColor="EAF0F7")
    r0 = 5
    for j, h in enumerate(headers, 1):
        c = ws.cell(r0, j, h)
        c.font = Font(bold=True)
        c.fill = head_fill
        c.border = border
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    widths = [len(h) + 2 for h in headers]
    for i, row in enumerate(rows):
        for j, v in enumerate(row, 1):
            val = int(v) if (j - 1) in money_cols and _is_num(v) else (float(v) if isinstance(v, Decimal) else v)
            if (j - 1) in money_cols and val in (0, None):
                val = None
            c = ws.cell(r0 + 1 + i, j, val)
            if isinstance(val, str) and val[:1] in ("=", "+", "-", "@"):
                c.data_type = "s"            # dữ liệu nhập từ bên ngoài không được thực thi như công thức Excel
            c.border = border
            if (j - 1) in money_cols:
                c.number_format = '#,##0;(#,##0)'
            if i in total_rows:
                c.font = Font(bold=True)
            widths[j - 1] = min(max(widths[j - 1], len(str(v if v is not None else "")) + 2), 60)
    for j, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.freeze_panes = ws.cell(r0 + 1, 1)
    last = r0 + len(rows) + 2
    ws.cell(last, 1, f"Lập lúc {datetime.now():%d/%m/%Y %H:%M} – Ứng dụng Kế toán Hocviendaotaoai").font = Font(italic=True,
                                                                                                              color="777777")
    wb.save(path)


def to_html(title: str, subtitle: str, company: str, headers: list[str], rows: list[list],
            money_cols: set[int] | None = None, total_rows: set[int] | None = None, signers: list[str] | None = None) -> str:
    money_cols = money_cols or set()
    total_rows = total_rows or set()

    def cell(v, j):
        if j in money_cols and _is_num(v):
            return f'<td align="right">{fmt_money(v)}</td>'
        if isinstance(v, Decimal):
            return f'<td align="right">{fmt_decimal(v)}</td>'
        return f"<td>{html.escape(str(v if v is not None else ''))}</td>"

    body = []
    for i, r in enumerate(rows):
        style = ' style="font-weight:bold;background:#F1F4F8"' if i in total_rows else ""
        body.append(f"<tr{style}>" + "".join(cell(v, j) for j, v in enumerate(r)) + "</tr>")
    sign = ""
    if signers:
        tds = "".join(f'<td align="center" width="{100 // len(signers)}%"><b>{html.escape(s)}</b><br/><i>(Ký, họ tên)</i>'
                      f"<br/><br/><br/><br/></td>" for s in signers)
        sign = f'<table width="100%" style="margin-top:14px"><tr>{tds}</tr></table>'
    return f"""<html><head><meta charset="utf-8"><style>
        body {{ font-family: 'Segoe UI', 'Noto Sans', Arial, sans-serif; font-size: 8.5pt; }}
        table.grid {{ border-collapse: collapse; width: 100%; }}
        table.grid th {{ background: #EAF0F7; border: 1px solid #9FB0C6; padding: 3px; font-size: 8pt; }}
        table.grid td {{ border: 1px solid #C3CEDC; padding: 2px 3px; font-size: 8pt; }}
        </style></head><body>
        <div><b>{html.escape(company)}</b></div>
        <h2 align="center" style="color:#123B6D;margin:6px 0 2px 0">{html.escape(title.upper())}</h2>
        <div align="center">{html.escape(subtitle)}</div><br/>
        <table class="grid" cellspacing="0" cellpadding="2"><thead><tr>
        {''.join(f'<th>{html.escape(h)}</th>' for h in headers)}</tr></thead><tbody>{''.join(body)}</tbody></table>
        {sign}
        <div style="color:#777;margin-top:8px"><i>Lập lúc {datetime.now():%d/%m/%Y %H:%M}</i></div>
        </body></html>"""


def _document(html_text: str):
    from PySide6.QtGui import QTextDocument
    doc = QTextDocument()
    doc.setHtml(html_text)
    return doc


def _printer(landscape: bool, pdf_path: str | None = None):
    from PySide6.QtGui import QPageLayout, QPageSize
    from PySide6.QtCore import QMarginsF
    from PySide6.QtPrintSupport import QPrinter
    printer = QPrinter(QPrinter.HighResolution)
    printer.setPageSize(QPageSize(QPageSize.A4))
    printer.setPageOrientation(QPageLayout.Landscape if landscape else QPageLayout.Portrait)
    printer.setPageMargins(QMarginsF(12, 12, 12, 12), QPageLayout.Millimeter)
    if pdf_path:
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(pdf_path)
    return printer


def export_pdf(path: str, html_text: str, landscape: bool = True):
    printer = _printer(landscape, path)
    _document(html_text).print_(printer)


def print_preview(parent, html_text: str, landscape: bool = True):
    from PySide6.QtPrintSupport import QPrintPreviewDialog
    printer = _printer(landscape)
    dlg = QPrintPreviewDialog(printer, parent)
    dlg.setWindowTitle("Xem trước khi in")
    doc = _document(html_text)
    dlg.paintRequested.connect(lambda p: doc.print_(p))
    dlg.resize(1100, 720)
    dlg.exec()
