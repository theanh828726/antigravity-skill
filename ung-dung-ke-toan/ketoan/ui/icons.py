"""Bộ biểu tượng nét (line icon) vẽ bằng QPainter – không phụ thuộc file ảnh ngoài.

Hệ tọa độ 24×24, nét bo tròn. ``icon(name, color, size)`` trả về QIcon; ``pixmap`` trả về QPixmap.
"""
from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap


def _doc(p, fold=True):
    path = QPainterPath()
    path.moveTo(6, 3); path.lineTo(14, 3); path.lineTo(18, 7); path.lineTo(18, 21); path.lineTo(6, 21); path.closeSubpath()
    p.drawPath(path)
    if fold:
        p.drawPolyline([QPointF(14, 3), QPointF(14, 7), QPointF(18, 7)])


def _lines(p, ys, x1=9, x2=15):
    for y in ys:
        p.drawLine(QPointF(x1, y), QPointF(x2, y))


def _arrow(p, x1, y1, x2, y2, head=2.6):
    p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
    if x1 == x2:
        s = 1 if y2 > y1 else -1
        p.drawPolyline([QPointF(x2 - head, y2 - s * head), QPointF(x2, y2), QPointF(x2 + head, y2 - s * head)])
    else:
        s = 1 if x2 > x1 else -1
        p.drawPolyline([QPointF(x2 - s * head, y2 - head), QPointF(x2, y2), QPointF(x2 - s * head, y2 + head)])


def _box(p):
    path = QPainterPath()
    path.moveTo(4, 8); path.lineTo(12, 4); path.lineTo(20, 8); path.lineTo(20, 17); path.lineTo(12, 21); path.lineTo(4, 17)
    path.closeSubpath()
    p.drawPath(path)
    p.drawPolyline([QPointF(4, 8), QPointF(12, 12), QPointF(20, 8)])
    p.drawLine(QPointF(12, 12), QPointF(12, 21))


def _coin(p, cx=12, cy=12, r=7):
    p.drawEllipse(QPointF(cx, cy), r, r)


def _text(p, txt, rect, size=7.5, bold=True):
    f = QFont(); f.setPointSizeF(size); f.setBold(bold)
    p.setFont(f)
    p.drawText(QRectF(*rect), Qt.AlignCenter, txt)


def _book(p):
    p.drawRoundedRect(QRectF(5, 3, 14, 18), 1.5, 1.5)
    p.drawLine(QPointF(8, 3), QPointF(8, 21))


def _bank(p):
    p.drawPolyline([QPointF(3, 9), QPointF(12, 4), QPointF(21, 9), QPointF(3, 9)])
    for x in (6, 10, 14, 18):
        p.drawLine(QPointF(x, 11), QPointF(x, 17))
    p.drawLine(QPointF(3, 19.5), QPointF(21, 19.5))


def _users(p):
    p.drawEllipse(QPointF(9, 8.5), 3.2, 3.2)
    p.drawArc(QRectF(3, 13, 12, 10), 0, 180 * 16)
    p.drawEllipse(QPointF(16.5, 9), 2.6, 2.6)
    p.drawArc(QRectF(13, 14, 9, 8), 0, 180 * 16)


def _building(p):
    p.drawRect(QRectF(5, 4, 9, 17))
    p.drawRect(QRectF(14, 10, 5, 11))
    for y in (7, 11, 15):
        p.drawLine(QPointF(8, y), QPointF(11, y))


def _chart(p):
    p.drawPolyline([QPointF(4, 4), QPointF(4, 20), QPointF(20, 20)])
    p.drawLine(QPointF(8, 17), QPointF(8, 12))
    p.drawLine(QPointF(12, 17), QPointF(12, 8))
    p.drawLine(QPointF(16, 17), QPointF(16, 10))


def _scale(p):
    p.drawLine(QPointF(12, 4), QPointF(12, 20)); p.drawLine(QPointF(8, 20), QPointF(16, 20))
    p.drawLine(QPointF(5, 7), QPointF(19, 7))
    p.drawPolyline([QPointF(5, 7), QPointF(2.5, 13), QPointF(7.5, 13), QPointF(5, 7)])
    p.drawPolyline([QPointF(19, 7), QPointF(16.5, 13), QPointF(21.5, 13), QPointF(19, 7)])


def _gear(p):
    p.drawEllipse(QPointF(12, 12), 3, 3)
    import math
    for i in range(8):
        a = math.pi / 4 * i
        p.drawLine(QPointF(12 + 5.5 * math.cos(a), 12 + 5.5 * math.sin(a)), QPointF(12 + 8 * math.cos(a), 12 + 8 * math.sin(a)))
    p.drawEllipse(QPointF(12, 12), 5.5, 5.5)


def _draw(p: QPainter, name: str):
    if name == "receipt_in":
        _doc(p); _arrow(p, 12, 9, 12, 17)
    elif name == "receipt_out":
        _doc(p); _arrow(p, 12, 17, 12, 9)
    elif name == "cart":
        p.drawPolyline([QPointF(3, 4), QPointF(6, 4), QPointF(8, 15), QPointF(19, 15), QPointF(21, 7), QPointF(7, 7)])
        p.drawEllipse(QPointF(9, 19), 1.5, 1.5); p.drawEllipse(QPointF(17, 19), 1.5, 1.5)
    elif name == "sale":
        path = QPainterPath(); path.moveTo(3, 12); path.lineTo(11, 4); path.lineTo(20, 4); path.lineTo(20, 13)
        path.lineTo(12, 21); path.closeSubpath(); p.drawPath(path); p.drawEllipse(QPointF(16, 8), 1.4, 1.4)
    elif name == "doc_swap":
        _doc(p); _arrow(p, 9, 11, 15, 11, 2); _arrow(p, 15, 16, 9, 16, 2)
    elif name == "box_in":
        _box(p); _arrow(p, 12, 0.5, 12, 9, 2.2)
    elif name == "box_out":
        _box(p); _arrow(p, 16, 14.5, 23, 14.5, 2.2)
    elif name == "boxes":
        p.drawRect(QRectF(3, 12, 8, 8)); p.drawRect(QRectF(13, 12, 8, 8)); p.drawRect(QRectF(8, 4, 8, 8))
    elif name == "journal":
        _book(p); _lines(p, (8, 11.5, 15), 11, 16)
    elif name == "bank":
        _bank(p)
    elif name == "docs":
        p.drawRect(QRectF(8, 3, 11, 14)); p.drawPolyline([QPointF(5, 7), QPointF(5, 21), QPointF(16, 21)])
        _lines(p, (7, 10.5, 13.5), 11, 16)
    elif name == "book":
        _book(p)
    elif name == "ledger":
        _book(p); _text(p, "Σ", (8, 4, 11, 16), 10, True)
    elif name == "columns":
        p.drawRect(QRectF(3, 4, 18, 16)); p.drawLine(QPointF(3, 8.5), QPointF(21, 8.5))
        p.drawLine(QPointF(9, 4), QPointF(9, 20)); p.drawLine(QPointF(15, 4), QPointF(15, 20))
    elif name == "scale":
        _scale(p)
    elif name == "cash":
        p.drawRoundedRect(QRectF(2.5, 6, 19, 12), 1.5, 1.5); _coin(p, 12, 12, 3); p.drawLine(QPointF(5.5, 9), QPointF(5.5, 15))
        p.drawLine(QPointF(18.5, 9), QPointF(18.5, 15))
    elif name == "bank_book":
        _bank(p)
    elif name == "debt":
        _users(p)
    elif name == "warehouse":
        p.drawPolyline([QPointF(3, 20), QPointF(3, 9), QPointF(12, 4), QPointF(21, 9), QPointF(21, 20)])
        p.drawRect(QRectF(7, 13, 10, 7)); p.drawLine(QPointF(7, 16.5), QPointF(17, 16.5))
    elif name == "compare":
        _arrow(p, 4, 8, 20, 8); _arrow(p, 20, 16, 4, 16)
    elif name == "asset":
        _building(p)
    elif name == "tools":
        p.drawLine(QPointF(5, 19), QPointF(14, 10)); p.drawEllipse(QPointF(16.5, 7.5), 3.5, 3.5)
        p.drawRect(QRectF(4, 4, 5, 5))
    elif name == "crane":
        p.drawLine(QPointF(6, 21), QPointF(6, 4)); p.drawLine(QPointF(3, 6), QPointF(21, 6))
        p.drawLine(QPointF(17, 6), QPointF(17, 12)); p.drawRect(QRectF(15, 12, 4, 3)); p.drawLine(QPointF(3, 21), QPointF(10, 21))
        p.drawLine(QPointF(6, 9), QPointF(10, 6))
    elif name == "factory":
        p.drawPolyline([QPointF(3, 20), QPointF(3, 11), QPointF(8, 14), QPointF(8, 11), QPointF(13, 14), QPointF(13, 11),
                        QPointF(18, 14), QPointF(18, 4), QPointF(21, 4), QPointF(21, 20), QPointF(3, 20)])
    elif name == "truck":
        p.drawRect(QRectF(2.5, 7, 11, 9)); p.drawPolyline([QPointF(13.5, 10), QPointF(18, 10), QPointF(21, 13.5),
                                                          QPointF(21, 16), QPointF(13.5, 16)])
        p.drawEllipse(QPointF(7, 18), 1.8, 1.8); p.drawEllipse(QPointF(17, 18), 1.8, 1.8)
    elif name == "service":
        p.drawEllipse(QPointF(12, 8), 4, 4); p.drawArc(QRectF(4, 13, 16, 12), 0, 180 * 16)
    elif name == "calc":
        p.drawRoundedRect(QRectF(5, 3, 14, 18), 1.5, 1.5); p.drawRect(QRectF(8, 6, 8, 3.5))
        for x in (9, 12, 15):
            for y in (13, 17):
                p.drawPoint(QPointF(x, y))
    elif name == "chart":
        _chart(p)
    elif name == "report":
        _doc(p); p.drawLine(QPointF(9, 18), QPointF(9, 14)); p.drawLine(QPointF(12, 18), QPointF(12, 11))
        p.drawLine(QPointF(15, 18), QPointF(15, 13))
    elif name == "cashflow":
        _coin(p, 12, 12, 7.5); _arrow(p, 9, 15, 15, 9, 2.2)
    elif name == "notes":
        _doc(p); _lines(p, (10, 13, 16), 9, 15)
    elif name == "tax":
        p.drawLine(QPointF(6, 18), QPointF(18, 6)); p.drawEllipse(QPointF(7.5, 7.5), 2.2, 2.2)
        p.drawEllipse(QPointF(16.5, 16.5), 2.2, 2.2)
    elif name == "printer":
        p.drawRect(QRectF(7, 3, 10, 5)); p.drawRoundedRect(QRectF(3, 8, 18, 8), 1.5, 1.5); p.drawRect(QRectF(7, 13, 10, 8))
    elif name == "home":
        p.drawPolyline([QPointF(3, 11), QPointF(12, 3.5), QPointF(21, 11)])
        p.drawPolyline([QPointF(5.5, 9.5), QPointF(5.5, 20), QPointF(18.5, 20), QPointF(18.5, 9.5)])
        p.drawRect(QRectF(10, 14, 4, 6))
    elif name == "list":
        for y in (6, 12, 18):
            p.drawPoint(QPointF(5, y)); p.drawLine(QPointF(9, y), QPointF(20, y))
    elif name == "shield":
        path = QPainterPath(); path.moveTo(12, 3); path.lineTo(19.5, 6); path.lineTo(19, 13); path.quadTo(18, 18, 12, 21)
        path.quadTo(6, 18, 5, 13); path.lineTo(4.5, 6); path.closeSubpath(); p.drawPath(path)
        p.drawPolyline([QPointF(8.5, 12), QPointF(11, 14.5), QPointF(15.5, 9.5)])
    elif name == "calendar":
        p.drawRoundedRect(QRectF(3.5, 5, 17, 15), 1.5, 1.5); p.drawLine(QPointF(3.5, 9.5), QPointF(20.5, 9.5))
        p.drawLine(QPointF(8, 3), QPointF(8, 7)); p.drawLine(QPointF(16, 3), QPointF(16, 7))
    elif name == "refresh":
        p.drawArc(QRectF(4.5, 4.5, 15, 15), 40 * 16, 280 * 16); p.drawPolyline([QPointF(18, 3.5), QPointF(18, 8), QPointF(13.5, 8)])
    elif name == "help":
        _coin(p, 12, 12, 8.5); _text(p, "?", (4, 3.5, 16, 16), 10, True)
    elif name == "lock":
        p.drawRoundedRect(QRectF(5, 10.5, 14, 10), 1.5, 1.5); p.drawArc(QRectF(8, 4, 8, 11), 0, 180 * 16)
        p.drawLine(QPointF(8, 9.5), QPointF(8, 10.5)); p.drawLine(QPointF(16, 9.5), QPointF(16, 10.5))
    elif name == "alert":
        path = QPainterPath(); path.moveTo(12, 3.5); path.lineTo(21, 19.5); path.lineTo(3, 19.5); path.closeSubpath()
        p.drawPath(path); p.drawLine(QPointF(12, 9), QPointF(12, 14)); p.drawPoint(QPointF(12, 17))
    elif name == "backup":
        p.drawEllipse(QRectF(5, 3, 14, 5)); p.drawLine(QPointF(5, 5.5), QPointF(5, 18.5)); p.drawLine(QPointF(19, 5.5), QPointF(19, 18.5))
        p.drawArc(QRectF(5, 16, 14, 5), 180 * 16, 180 * 16); p.drawArc(QRectF(5, 10, 14, 5), 180 * 16, 180 * 16)
    elif name == "excel":
        p.drawRoundedRect(QRectF(4, 3, 16, 18), 1.5, 1.5)
        p.drawLine(QPointF(8.5, 8), QPointF(15.5, 16)); p.drawLine(QPointF(15.5, 8), QPointF(8.5, 16))
    elif name == "pdf":
        _doc(p, True); _text(p, "PDF", (5, 9, 14, 10), 5.5, True)
    elif name == "users":
        _users(p)
    elif name == "user":
        p.drawEllipse(QPointF(12, 8), 4, 4); p.drawArc(QRectF(4.5, 13.5, 15, 13), 0, 180 * 16)
    elif name == "org":
        p.drawRect(QRectF(9, 3, 6, 5)); p.drawRect(QRectF(3, 16, 6, 5)); p.drawRect(QRectF(15, 16, 6, 5))
        p.drawPolyline([QPointF(12, 8), QPointF(12, 12), QPointF(6, 12), QPointF(6, 16)])
        p.drawPolyline([QPointF(12, 12), QPointF(18, 12), QPointF(18, 16)])
    elif name == "tag":
        path = QPainterPath(); path.moveTo(3, 4); path.lineTo(12, 4); path.lineTo(20.5, 12.5); path.lineTo(12.5, 20.5)
        path.lineTo(3, 12); path.closeSubpath(); p.drawPath(path); p.drawEllipse(QPointF(7.5, 8.5), 1.4, 1.4)
    elif name == "settings":
        _gear(p)
    elif name == "folder":
        p.drawPolyline([QPointF(3, 19), QPointF(3, 5), QPointF(9, 5), QPointF(11, 7.5), QPointF(21, 7.5),
                        QPointF(21, 19), QPointF(3, 19)])
    elif name == "box":
        _box(p)
    elif name == "truck_cost":
        p.drawRect(QRectF(2.5, 7, 11, 9)); p.drawPolyline([QPointF(13.5, 10), QPointF(18, 10), QPointF(21, 13.5),
                                                          QPointF(21, 16), QPointF(13.5, 16)])
        p.drawEllipse(QPointF(7, 18), 1.8, 1.8); p.drawEllipse(QPointF(17, 18), 1.8, 1.8)
    elif name == "add":
        p.drawLine(QPointF(12, 5), QPointF(12, 19)); p.drawLine(QPointF(5, 12), QPointF(19, 12))
    elif name == "edit":
        p.drawPolyline([QPointF(5, 19), QPointF(5.5, 15), QPointF(15.5, 5), QPointF(19, 8.5), QPointF(9, 18.5), QPointF(5, 19)])
    elif name == "save":
        p.drawPolyline([QPointF(4, 4), QPointF(17, 4), QPointF(20, 7), QPointF(20, 20), QPointF(4, 20), QPointF(4, 4)])
        p.drawRect(QRectF(8, 4, 7, 5)); p.drawRect(QRectF(7, 13, 10, 7))
    elif name == "cancel":
        p.drawLine(QPointF(6, 6), QPointF(18, 18)); p.drawLine(QPointF(18, 6), QPointF(6, 18))
    elif name == "check":
        p.drawPolyline([QPointF(4.5, 12.5), QPointF(9.5, 17.5), QPointF(19.5, 6.5)])
    elif name == "post":
        _book(p); p.drawPolyline([QPointF(10.5, 12.5), QPointF(13, 15), QPointF(17, 9.5)])
    elif name == "unpost":
        _book(p); p.drawLine(QPointF(11, 9), QPointF(17, 15)); p.drawLine(QPointF(17, 9), QPointF(11, 15))
    elif name == "delete":
        p.drawLine(QPointF(4, 6.5), QPointF(20, 6.5)); p.drawRect(QRectF(6.5, 6.5, 11, 14))
        p.drawLine(QPointF(9.5, 4), QPointF(14.5, 4)); p.drawLine(QPointF(10, 10), QPointF(10, 17)); p.drawLine(QPointF(14, 10), QPointF(14, 17))
    elif name == "search":
        p.drawEllipse(QPointF(10.5, 10.5), 6, 6); p.drawLine(QPointF(15, 15), QPointF(20.5, 20.5))
    elif name == "copy":
        p.drawRect(QRectF(8, 8, 12, 12)); p.drawPolyline([QPointF(16, 8), QPointF(16, 4), QPointF(4, 4), QPointF(4, 16), QPointF(8, 16)])
    elif name == "menu":
        for y in (7, 12, 17):
            p.drawLine(QPointF(4, y), QPointF(20, y))
    elif name == "open":
        p.drawRect(QRectF(4, 6, 12, 14)); _arrow(p, 11, 13, 20, 4, 2.5)
    elif name == "import":
        p.drawPolyline([QPointF(4, 14), QPointF(4, 20), QPointF(20, 20), QPointF(20, 14)]); _arrow(p, 12, 3, 12, 15)
    elif name == "close_period":
        _scale(p)
    else:
        _doc(p); _lines(p, (11, 14, 17))


@lru_cache(maxsize=512)
def pixmap(name: str, color: str = "#FFFFFF", size: int = 24, width: float = 1.7) -> QPixmap:
    ratio = 2
    pm = QPixmap(size * ratio, size * ratio)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(size * ratio / 24.0, size * ratio / 24.0)
    pen = QPen(QColor(color), width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    _draw(p, name)
    p.end()
    pm.setDevicePixelRatio(ratio)
    return pm


def icon(name: str, color: str = "#FFFFFF", size: int = 24) -> QIcon:
    return QIcon(pixmap(name, color, size))


def logo_pixmap(size: int = 34) -> QPixmap:
    """Logo Hocviendaotaoai: khối vuông bo góc, chữ 'AI' và vòng quỹ đạo."""
    ratio = 2
    pm = QPixmap(size * ratio, size * ratio)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(size * ratio / 34.0, size * ratio / 34.0)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#F5B323"))
    p.drawRoundedRect(QRectF(1, 1, 32, 32), 8, 8)
    p.setBrush(QColor("#123B6D"))
    p.drawRoundedRect(QRectF(4, 4, 26, 26), 6, 6)
    pen = QPen(QColor("#F5B323"), 1.6)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QRectF(6, 11, 22, 12))
    p.setPen(QColor("white"))
    f = QFont(); f.setBold(True); f.setPointSizeF(10.5)
    p.setFont(f)
    p.drawText(QRectF(4, 4, 26, 26), Qt.AlignCenter, "AI")
    p.end()
    pm.setDevicePixelRatio(ratio)
    return pm
