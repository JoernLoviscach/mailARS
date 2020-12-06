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
import typing
import PyQt5.QtCore as core
import PyQt5.QtWidgets as widgets 
import PyQt5.QtGui as gui


class DragButton(widgets.QToolButton):
    def __init__(self, parent: widgets.QWidget, \
        mouse_function: typing.Callable[[typing.Optional[core.QPoint], typing.Optional[core.QPoint]], None]) -> None:
        super().__init__(parent)
        self._mouse_function = mouse_function
        self._old_position: typing.Optional[core.QPoint] = None

    def mousePressEvent(self, event: gui.QMouseEvent) -> None:
        # mapToGlobal: Widget changes its position during dragging!
        self._old_position = self.parent().mapToGlobal(event.pos())
        self._mouse_function(self._old_position, None)
        self.grabMouse()
        event.accept()

    def mouseMoveEvent(self, event: gui.QMouseEvent) -> None:
        new_position = self.parent().mapToGlobal(event.pos())
        self._mouse_function(new_position, self._old_position)
        self._old_position = new_position
        event.accept()

    def mouseReleaseEvent(self, event: gui.QMouseEvent) -> None:
        self.releaseMouse()
        self._mouse_function(None, self._old_position)
        self._old_position = None
        event.accept()

    def mouseDoubleClickEvent(self, event: gui.QMouseEvent) -> None:
        event.accept()

    def tabletEvent(self, event):
        event.accept()