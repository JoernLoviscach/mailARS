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

 
class UndoRedo(core.QObject):
    undo_status_changed: core.pyqtSignal = core.pyqtSignal(bool, name="undoStatusChanged")
    redo_status_changed: core.pyqtSignal = core.pyqtSignal(bool, name="redoStatusChanged")

    def __init__(self, parent: core.QObject) -> None:
        super().__init__(parent)
        self._undo_stack: typing.List[Command] = []
        self._redo_stack: typing.List[Command] = []
    
    def undo(self) -> None:
        if len(self._undo_stack) > 0:
            command = self._undo_stack.pop()
            command.undo_function()
            self._redo_stack.append(command)
        self._emit_status()

    def redo(self) -> None:
        if len(self._redo_stack) > 0:
            command = self._redo_stack.pop()
            command.redo_function()
            self._undo_stack.append(command)
        self._emit_status()

    def add_undo(self, command: Command) -> None:
        self._undo_stack.append(command)
        self._redo_stack.clear()
        self._emit_status()

    def _emit_status(self) -> None:
        self.undo_status_changed.emit(len(self._undo_stack) > 0)
        self.redo_status_changed.emit(len(self._redo_stack) > 0)

class Command():
    def __init__(self, \
        undo_redo_stacks: UndoRedo, \
        undo_function: typing.Callable[[], None], \
        redo_function: typing.Callable[[], None],
        call_redo_function_now: bool) -> None:
        self.undo_function = undo_function
        self.redo_function = redo_function
        if call_redo_function_now:
            redo_function()
        undo_redo_stacks.add_undo(self)
 