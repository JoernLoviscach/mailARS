#    Copyright (C) 2020 Jörn Loviscach <https://j3L7h.de>
#
#    This file is part of mailARS.
#
#    mailARS is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    mailARS is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with mailARS.  If not, see <https://www.gnu.org/licenses/>.

from __future__ import annotations
from locale import currency
import typing
import PyQt5.QtCore as core
import PyQt5.QtWidgets as widgets 
import PyQt5.QtGui as gui
from enum import IntEnum
import drawing_widget
import graphics
import undo_redo

class _ResizeMode(IntEnum):
    NONE = 0
    N = 1
    NE = 2
    E = 3
    SE = 4
    S = 5
    SW = 6
    W = 7
    NW = 8

class TextEditor(widgets.QFrame):
    def __init__(self, drawing_wid: drawing_widget.DrawingWidget) -> None:
        super().__init__(drawing_wid)
        self._drawing_widget = drawing_wid
        self._text_element = None
        self._initial_position: typing.Optional[core.QPoint] = None
        self._initial_geometry: typing.Optional[core.QRect] = None
        self._resize_mode: _ResizeMode = _ResizeMode.NONE

        self.hide()
        self.setMouseTracking(True)
        self.setFrameShape(widgets.QFrame.Box)
        self.setLineWidth(4)
        layout = widgets.QGridLayout() #   .QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        self._text_edit = widgets.QPlainTextEdit(self)
        layout.addWidget(self._text_edit, 0, 0)
        self._text_edit.setFrameStyle(widgets.QFrame.NoFrame)
        self._text_edit.document().setDocumentMargin(0)
        self._text_edit.setHorizontalScrollBarPolicy(core.Qt.ScrollBarAlwaysOff)
        self._text_edit.setVerticalScrollBarPolicy(core.Qt.ScrollBarAlwaysOff)
        self._text_edit.textChanged.connect(self._update_text)

        self._close_button = widgets.QToolButton(self)
        self._close_button.setText("X")
        self._close_button.setCursor(core.Qt.ArrowCursor)
        layout.addWidget(self._close_button, 0, 0)
        layout.setAlignment(self._close_button, typing.cast(core.Qt.Alignment, core.Qt.AlignRight | core.Qt.AlignBottom))
        self._close_button.clicked.connect(self._drawing_widget.clean_ui)

    def open(self) -> None:
        self.show()
        self.activateWindow()
        self._text_edit.setFocus()

    def set_text_element(self, text_element: typing.Optional[graphics.TextObject]) -> None:
        self._text_element = text_element
        if self._text_element is None:
            return
        bb = self._text_element.get_bounding_box()
        left = int(bb.left())
        top = int(bb.top())
        width = int(bb.width())
        height = int(bb.height())
        f = self.frameWidth()
        self.setGeometry(left - f, top - f, width + 2 * f, height + 2 * f)
        self.update_font_size(self._text_element.get_font_size())
        self._text_edit.setPlainText(self._text_element.get_text())

    def get_text_element(self) -> typing.Optional[graphics.TextObject]:
        return self._text_element

    def _update_text(self) -> None:
        if self._text_element is not None:
            self._text_element.set_text(self._text_edit.toPlainText())

    def update_font_size(self, font_size: float) -> None:
        if self._text_element is not None:
            self._text_element.set_font_size(font_size)
            font = self._text_edit.document().defaultFont()
            font.setPointSizeF(font_size)
            self._text_edit.document().setDefaultFont(font)

    def _set_cursor_and_resize_mode(self, x: int, y: int) -> None:
        w = self.width()
        h = self.height()
        d = 10
        if x <= d:
            if y <= d:
                self._resize_mode = _ResizeMode.NW
            elif y >= h - d:
                self._resize_mode = _ResizeMode.SW
            else:
                self._resize_mode = _ResizeMode.W
        elif x >= w - d:
            if y <= d:
                self._resize_mode = _ResizeMode.NE
            elif y >= h - d:
                self._resize_mode = _ResizeMode.SE
            else:
                self._resize_mode = _ResizeMode.E
        else:
            if y <= d:
                self._resize_mode = _ResizeMode.N
            elif y >= h - d:
                self._resize_mode = _ResizeMode.S
            else:
                self._resize_mode = _ResizeMode.NONE
 
        if self._resize_mode == _ResizeMode.NE or self._resize_mode == _ResizeMode.SW:
            self.setCursor(core.Qt.SizeBDiagCursor)
        elif self._resize_mode == _ResizeMode.NW or self._resize_mode == _ResizeMode.SE:
            self.setCursor(core.Qt.SizeFDiagCursor)
        elif self._resize_mode == _ResizeMode.N or self._resize_mode == _ResizeMode.S:
            self.setCursor(core.Qt.SizeVerCursor)
        elif self._resize_mode == _ResizeMode.E or self._resize_mode == _ResizeMode.W:
            self.setCursor(core.Qt.SizeHorCursor)
        else:  # _ResizeMode.NONE
            self.setCursor(core.Qt.ArrowCursor)

    def mousePressEvent(self, event: gui.QMouseEvent) -> None:
        event.accept()
        if event.button() == core.Qt.LeftButton:
            self.grabMouse()
            self._initial_position = event.pos()
            self._initial_geometry = self.geometry()
            self._set_cursor_and_resize_mode(event.x(), event.y())

    def mouseMoveEvent(self, event: gui.QMouseEvent) -> None:
        event.accept()
        x = event.x()
        y = event.y()
        if not (event.buttons() & core.Qt.LeftButton):
            self._set_cursor_and_resize_mode(x, y)
        else:  # Don't change mode while mouse button is being pressed!
            if self._resize_mode != _ResizeMode.NONE \
                and self._initial_position is not None \
                and self._initial_geometry is not None:

                geo = self._initial_geometry
                left = geo.left()
                right = left + geo.width()  # != geo.right()
                top = geo.top()
                bottom = top + geo.height()  # != geo.bottom()

                current_geo = self.geometry()
                # x, y are relative to widget
                dx = x - self._initial_position.x() + current_geo.left() - left
                dy = y - self._initial_position.y() + current_geo.top() - top
                dws = self._drawing_widget.size()

                m = self.lower_size_limit()
                if self._resize_mode == _ResizeMode.N:
                    top += dy
                    top = max(0, min(top, bottom - m))
                elif self._resize_mode == _ResizeMode.NE:
                    top += dy
                    top = max(0, min(top, bottom - m))
                    right += dx
                    right = min(dws.width(), max(right, left + m))
                elif self._resize_mode == _ResizeMode.E:
                    right += dx
                    right = min(dws.width(), max(right, left + m))
                elif self._resize_mode == _ResizeMode.SE:
                    right += dx
                    right = min(dws.width(), max(right, left + m))
                    bottom += dy
                    bottom = min(dws.height(), max(bottom, top + m))
                elif self._resize_mode == _ResizeMode.S:
                    bottom += dy
                    bottom = min(dws.height(), max(bottom, top + m))
                elif self._resize_mode == _ResizeMode.SW:
                    left += dx
                    left = max(0, min(left, right - m))
                    bottom += dy
                    bottom = min(dws.height(), max(bottom, top + m))
                elif self._resize_mode == _ResizeMode.W:
                    left += dx
                    left = max(0, min(left, right - m))
                elif self._resize_mode == _ResizeMode.NW:
                    left += dx
                    left = max(0, min(left, right - m))
                    top += dy
                    top = max(0, min(top, bottom - m))
                
                self.setGeometry(core.QRect(left, top, right - left, bottom - top))

    def mouseReleaseEvent(self, event: gui.QMouseEvent) -> None:
        event.accept()
        if self._text_element is not None and self._initial_geometry is not None:  # should "never" be otherwise
            text_element = self._text_element  # copy for closure
            f = self.frameWidth()
            box_before = core.QRectF(self._initial_geometry)
            box_before.adjust(f, f, -f, -f)
            box_after = core.QRectF(self.geometry())
            box_after.adjust(f, f, -f, -f)
            def undo_function() -> None:
                text_element.set_bounding_box(box_before)
                self._drawing_widget.update()
            def redo_function() -> None:
                text_element.set_bounding_box(box_after)
                self._drawing_widget.update()
            undo_redo.Command(self._drawing_widget._undo_redo, undo_function, redo_function, True)

        self._initial_position = None
        self._initial_geometry = None
        self._resize_mode = _ResizeMode.NONE
        self.releaseMouse()

    def tabletEvent(self, event: gui.QTabletEvent) -> None:
        event.ignore()

    def lower_size_limit(self) -> int:
        return 5 + self.frameWidth()
