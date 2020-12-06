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
import sys
import PyQt5.QtCore as core
import PyQt5.QtWidgets as widgets
import PyQt5.QtGui as gui
import os
import preferences
import mailboxes_window
import locale
import types
import traceback

os.chdir(os.path.dirname(os.path.abspath(sys.argv[0])))
locale.setlocale(locale.LC_ALL, "")
app = widgets.QApplication(sys.argv)
app.setApplicationName("mailARS")

def print_error(exception_type: typing.Type[BaseException], \
    value: BaseException, \
    tb: types.TracebackType) -> None:
    widgets.QMessageBox.critical(None, "Interner Fehler", \
        "Bitte machen Sie hiervon einen Screenshot!\n"
        + "".join(traceback.format_exception(exception_type, value, tb)))
sys.excepthook = print_error

preferences.load()
preferences.set_password(None)
window = mailboxes_window.MailboxesWindow()
app.exec_()
preferences.save()
