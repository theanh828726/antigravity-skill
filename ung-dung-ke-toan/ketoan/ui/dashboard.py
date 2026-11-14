"""Màn hình tổng quan dạng ô chức năng + trang nhóm chức năng của từng mục menu."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QAbstractButton, QFrame, QHBoxLayout, QLabel, QLayout, QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from ketoan.domain.constants import SEV_BLOCK, SEV_REVIEW
from ketoan.domain.money import fmt_money
from ketoan.ui import icons, theme
from ketoan.ui.registry import DASHBOARD_GROUPS, FUNCS
from ketoan.ui.widgets import SectionHeader, vn_date

TILE_W, TILE_H = 155, 46


class FlowLayout(QLayout):
    def __init__(self, parent=None, spacing=6):
        super().__init__(parent)
        self._items: list = []
        self._sp = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientations(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        return self._layout(QRect(0, 0, w, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        return QSize(TILE_W, TILE_H)

    def _layout(self, rect, test):
        x, y, line_h = rect.x(), rect.y(), 0
        for it in self._items:
            hint = it.widget().minimumSize() if it.widget() is not None else it.sizeHint()
            if x + hint.width() > rect.right() + 1 and line_h > 0:
                x, y = rect.x(), y + line_h + self._sp
                line_h = 0
            if not test:
                it.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + self._sp
            line_h = max(line_h, hint.height())
        return y + line_h - rect.y()


class Tile(QAbstractButton):
    """Ô chức năng: nền màu theo nhóm nghiệp vụ, biểu tượng nét trắng, tên tiếng Việt đầy đủ."""

    def __init__(self, func, parent=None):
        super().__init__(parent)
        self.func = func
        self.setFixedSize(TILE_W, TILE_H)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        tip = func.title
        if func.pending:
            tip += f"\nCHƯA TRIỂN KHAI – Giai đoạn {func.phase}. Bấm để xem phạm vi dự kiến."
        self.setToolTip(tip)
        self.setAccessibleName(func.title)
        self._hover = False

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        base = QColor(theme.TILE_COLORS[self.func.color])
        pending = self.func.pending
        if pending:
            base = QColor.fromHsv(base.hsvHue(), int(base.hsvSaturation() * 0.45), min(255, base.value() + 40))
        if self._hover or self.hasFocus():
            base = base.darker(112)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(r, 5, 5)
        p.fillPath(path, base)
        if self.hasFocus():
            p.setPen(QPen(QColor("#FFD54A"), 2))
            p.drawPath(path)
        p.drawPixmap(8, (TILE_H - 24) // 2, icons.pixmap(self.func.icon, "#FFFFFF", 24))
        p.setPen(QColor("#FFFFFF"))
        text_rect = QRect(38, 2, TILE_W - 42 - (20 if self.func.pending else 0), TILE_H - 4)
        f = QFont(self.font())
        f.setBold(True)
        for size in (8.2, 7.6, 7.0, 6.6):      # tự co chữ để tên dài vẫn hiển thị đầy đủ
            f.setPointSizeF(size)
            p.setFont(f)
            br = p.boundingRect(text_rect, Qt.AlignVCenter | Qt.AlignLeft | Qt.TextWordWrap, self.func.title)
            if br.height() <= text_rect.height() and br.width() <= text_rect.width():
                break
        p.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft | Qt.TextWordWrap, self.func.title)
        if pending:
            f2 = QFont(self.font())
            f2.setPointSizeF(6.8)
            f2.setBold(True)
            p.setFont(f2)
            badge = QRectF(TILE_W - 28, 3, 25, 12)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 220))
            p.drawRoundedRect(badge, 6, 6)
            p.setPen(QColor("#6B4E00"))
            p.drawText(badge, Qt.AlignCenter, f"GĐ{self.func.phase}")
        p.end()


class TileGroup(QWidget):
    def __init__(self, title: str, keys: list[str], on_open, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 4)
        lay.setSpacing(4)
        lay.addWidget(SectionHeader(title))
        holder = QWidget()
        flow = FlowLayout(holder, 5)
        for k in keys:
            t = Tile(FUNCS[k])
            t.clicked.connect(lambda _=False, key=k: on_open(key))
            flow.addWidget(t)
        holder.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        lay.addWidget(holder)


class _Kpi(QFrame):
    clicked = Signal()

    def __init__(self, label, color):
        super().__init__()
        self.setObjectName("TotalBox")
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(f"#TotalBox {{ border-left: 4px solid {color}; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 3, 8, 3)
        lay.setSpacing(0)
        self.l = QLabel(label)
        self.l.setObjectName("TotalLabel")
        self.v = QLabel("")
        self.v.setObjectName("TotalValue")
        lay.addWidget(self.l)
        lay.addWidget(self.v)

    def mouseReleaseEvent(self, e):
        self.clicked.emit()


class Dashboard(QWidget):
    """Tổng quan: dải chỉ số nhanh + các nhóm ô chức năng (theo bố cục ảnh tham chiếu)."""

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.setObjectName("Page")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        body.setObjectName("Page")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(14, 8, 14, 10)
        lay.setSpacing(2)

        head = QHBoxLayout()
        self.title = QLabel()
        self.title.setObjectName("PageTitle")
        self.sub = QLabel()
        self.sub.setObjectName("Hint")
        head.addWidget(self.title)
        head.addSpacing(10)
        head.addWidget(self.sub, 1)
        lay.addLayout(head)

        kpis = QHBoxLayout()
        kpis.setSpacing(6)
        self.k = {}
        for key, label, color, target in (
                ("cash", "Tiền mặt", theme.TILE_COLORS["tien"], ("r_soquy", {})),
                ("bank", "Tiền gửi ngân hàng", theme.TILE_COLORS["tien"], ("r_sotgnh", {})),
                ("receivable", "Phải thu khách hàng", theme.TILE_COLORS["mua_ban"], ("r_sct", {"account": "131"})),
                ("payable", "Phải trả người bán", theme.TILE_COLORS["mua_ban"], ("r_sct", {"account": "331"})),
                ("revenue", "Doanh thu trong kỳ", theme.TILE_COLORS["bao_cao"], ("r_sct", {"account": "511"})),
                ("pending", "Chứng từ chưa ghi sổ", theme.TILE_COLORS["kho"], ("v_ALL", {"status": "DRAFT"})),
                ("alerts", "Cảnh báo", theme.TILE_COLORS["thue"], ("s_alerts", {}))):
            w = _Kpi(label, color)
            w.clicked.connect(lambda t=target: self.ctx.open(t[0], **t[1]))
            kpis.addWidget(w, 1)
            self.k[key] = w
        lay.addLayout(kpis)

        g = DASHBOARD_GROUPS
        lay.addWidget(TileGroup(g[0][0], g[0][1], self.ctx.open))
        lay.addWidget(TileGroup(g[1][0], g[1][1], self.ctx.open))
        two = QHBoxLayout()
        two.setSpacing(16)
        two.addWidget(TileGroup(g[2][0], g[2][1], self.ctx.open), 5)
        two.addWidget(TileGroup(g[3][0], g[3][1], self.ctx.open), 4)
        lay.addLayout(two)
        legend = QLabel("Ô màu nhạt có nhãn <b>GĐ4</b>: chức năng chưa triển khai, bấm để xem phạm vi dự kiến. "
                        "Phím tắt: F5 cập nhật · Ctrl+W đóng tab · Ctrl+Tab chuyển tab · F1 trợ giúp.")
        legend.setObjectName("Hint")
        lay.addWidget(legend)
        lay.addStretch(1)
        scroll.setWidget(body)
        outer.addWidget(scroll)
        self.refresh()

    def refresh(self):
        s = self.ctx.session
        c = s.company
        reg = s.regime_for()
        self.title.setText("TỔNG QUAN")
        self.sub.setText(f"{c['name']}  ·  Kỳ: {s.period_label} ({vn_date(s.date_from.isoformat())} – "
                         f"{vn_date(s.date_to.isoformat())})  ·  Chế độ kế toán: "
                         f"{reg['legal_ref'] + (' (chưa kiểm chứng)' if not reg['verified'] else '') if reg else 'chưa cấu hình'}")
        from ketoan.services.alert_service import AlertService
        from ketoan.services.ledger_service import LedgerService
        sm = LedgerService(s).summary(s.date_from, s.date_to)
        for key in ("cash", "bank", "receivable", "payable", "revenue"):
            self.k[key].v.setText(fmt_money(sm[key], blank_zero=False))
        pending = sum(n for st, n in sm["counts"].items() if st != "POSTED")
        self.k["pending"].v.setText(f"{pending} chứng từ")
        al = AlertService(s).collect(s.date_from.isoformat(), s.date_to.isoformat())
        nb = sum(1 for a in al if a.severity == SEV_BLOCK)
        nr = sum(1 for a in al if a.severity == SEV_REVIEW)
        self.k["alerts"].v.setText(f"{nb} lỗi · {nr} cần KT")
        self.k["alerts"].v.setStyleSheet("color:#B42318" if nb else "")


class SectionPage(QWidget):
    """Trang của một mục menu: các nhóm ô chức năng."""

    def __init__(self, ctx, title: str, groups: list, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 8, 14, 10)
        t = QLabel(title.upper())
        t.setObjectName("PageTitle")
        lay.addWidget(t)
        for gtitle, keys in groups:
            lay.addWidget(TileGroup(gtitle, keys, ctx.open))
        lay.addStretch(1)

    def refresh(self):
        pass
