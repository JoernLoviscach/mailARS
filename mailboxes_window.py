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
import datetime
import preferences
import mailbox_widget
import mailing
import thumbnail
import graphics


class MailboxesWindow(widgets.QMainWindow):

    def __init__(self):
        super().__init__()
        self._other_main_windows: typing.List[widgets.QMainWindow] = []

        self._tabs = widgets.QTabWidget(self)
        self.setCentralWidget(self._tabs)

        self._inbox: mailbox_widget.MailboxWidget = mailbox_widget.MailboxWidget(self, "inbox")
        self._tabs.addTab(self._inbox, self.tr("Inbox"))

        self._drafts: mailbox_widget.MailboxWidget = mailbox_widget.MailboxWidget(self, "drafts")
        self._tabs.addTab(self._drafts, self.tr("Drafts"))

        self._outbox: mailbox_widget.MailboxWidget = mailbox_widget.MailboxWidget(self, "outbox")
        self._tabs.addTab(self._outbox, self.tr("Outbox"))

        toolbar = widgets.QToolBar(self)
        self.addToolBar(toolbar)

        self._button_fetch_mail = widgets.QToolButton(self)
        self._button_fetch_mail.setToolTip(self.tr("Fetch mail"))
        self._button_fetch_mail.setIcon(gui.QIcon("fetch.png"))
        self._button_fetch_mail.setIconSize(core.QSize(32, 32))
        self._button_fetch_mail.clicked.connect(self._fetch_mails)
        toolbar.addWidget(self._button_fetch_mail)

        self._button_group_by_sender = widgets.QToolButton(self)
        self._button_group_by_sender.setToolTip(self.tr("Only show latest mail of every sender"))
        self._button_group_by_sender.setIcon(gui.QIcon("group_by_sender.png"))
        self._button_group_by_sender.setIconSize(core.QSize(32, 32))
        self._button_group_by_sender.clicked.connect(self._group_by_sender)
        self._button_group_by_sender.setCheckable(True)
        grouped = preferences.get("group_by_sender")
        self._button_group_by_sender.setChecked(grouped)
        self._inbox.group_by_person(grouped)
        toolbar.addWidget(self._button_group_by_sender)

        button_new_draft = widgets.QToolButton(self)
        button_new_draft.setToolTip(self.tr("New draft"))
        button_new_draft.setIcon(gui.QIcon("new.png"))
        button_new_draft.setIconSize(core.QSize(32, 32))
        button_new_draft.clicked.connect(self._new_draft)
        toolbar.addWidget(button_new_draft)

        label_separator = widgets.QLabel()
        label_separator.setText("      ")
        toolbar.addWidget(label_separator)

        self._button_pdf_export = widgets.QToolButton(self)
        self._button_pdf_export.setToolTip(self.tr("Export as PDF"))
        self._button_pdf_export.setIcon(gui.QIcon("export_to_pdf.png"))
        self._button_pdf_export.setIconSize(core.QSize(32, 32))
        self._button_pdf_export.clicked.connect(self._export_pdf)
        toolbar.addWidget(self._button_pdf_export)
        self._timer_export_pdf = core.QTimer(self)
        self._timer_export_pdf.setSingleShot(True)
        self._timer_export_pdf.timeout.connect(lambda: self._button_pdf_export.setIcon(gui.QIcon("export_to_pdf.png")))

        label_separator = widgets.QLabel()
        label_separator.setText("      ")
        toolbar.addWidget(label_separator)
        
        self._frame_num_columns = widgets.QFrame(toolbar, core.Qt.Popup)
        layout_num_columns = widgets.QHBoxLayout()
        self._frame_num_columns.setLayout(layout_num_columns)
        self._slider_num_columns = widgets.QSlider()
        layout_num_columns.addWidget(self._slider_num_columns)
        self._slider_num_columns.setMinimum(1)
        self._slider_num_columns.setMaximum(17)
        self._slider_num_columns.setTickInterval(4)
        self._slider_num_columns.setOrientation(core.Qt.Horizontal)
        self._slider_num_columns.setTickPosition(widgets.QSlider.TicksLeft)
        self._slider_num_columns.valueChanged.connect(self._num_columns_changed)
        self._button_num_columns = widgets.QToolButton()
        self._button_num_columns.setToolTip(self.tr("Number of columns"))
        self._button_num_columns.setIcon(gui.QIcon("columns.png"))
        self._button_num_columns.setIconSize(core.QSize(32, 32))
        self._button_num_columns.clicked.connect(self._exec_num_columns_slider)
        toolbar.addWidget(self._button_num_columns)

        label_separator = widgets.QLabel()
        label_separator.setText("      ")
        toolbar.addWidget(label_separator)

        button_edit_preferences = widgets.QToolButton(self)
        button_edit_preferences.setToolTip(self.tr("Settings"))
        button_edit_preferences.setIcon(gui.QIcon("settings.png"))
        button_edit_preferences.setIconSize(core.QSize(32, 32))
        button_edit_preferences.clicked.connect(self._edit_preferences)
        toolbar.addWidget(button_edit_preferences)

        screen = preferences.get("mailboxes_screen")
        self.setGeometry(screen[0], screen[1], screen[2], screen[3])

        self.setWindowIcon(gui.QIcon("program.png"))
        self.show()

        mailing.start_receiver(self)

    @core.pyqtSlot(str)
    def display_on_status_bar(self, message: str) -> None:
        if message != "":
            t = datetime.datetime.now().strftime("%H:%M:%S")
            self.statusBar().showMessage(t + "  " + message)
        else:
            self.statusBar().showMessage("")

    @core.pyqtSlot(str, str, list, datetime.datetime, str)
    def add_mail(self, address: str, name: str, \
        elements: typing.List[graphics.GraphicsObject], \
        when: datetime.datetime, \
        message_id: str) -> None:       
        self._inbox.add_item(address, name, elements, when, message_id)
        self._button_fetch_mail.setIcon(gui.QIcon("fetch.png"))

    @core.pyqtSlot()
    def got_mail(self) -> None:
        self._button_fetch_mail.setIcon(gui.QIcon("need_to_fetch.png"))

    @core.pyqtSlot(bool)
    def set_fetch_mail_status(self, status: bool) -> None:
        self._button_fetch_mail.setEnabled(status)

    def _fetch_mails(self) -> None:
        mailing.fetch(self._inbox.get_message_ids())

    def append_other_main_window(self, window: widgets.QMainWindow) -> None:
        self._other_main_windows.append(window)

    def closeEvent(self, event: gui.QCloseEvent) -> None:
        reply = widgets.QMessageBox.question(self, self.tr("Safety prompt"), self.tr("Do you really want to quit?"))
        if reply != widgets.QMessageBox.Yes:
            event.ignore()
            return
        event.accept()
        for dw in self._other_main_windows:
            dw.close()
        screen = self.geometry()
        preferences.set("mailboxes_screen", (screen.x(), screen.y(), screen.width(), screen.height()))
        mailing.stop_receiver()
        super().closeEvent(event)

    def _exec_num_columns_slider(self) -> None:
        self._frame_num_columns.move(self.mapToGlobal(self._button_num_columns.geometry().bottomLeft()))
        self._slider_num_columns.setValue(preferences.get("number_of_columns"))
        self._frame_num_columns.show()

    def _num_columns_changed(self, value: int) -> None:
        preferences.set("number_of_columns", value)
        self._inbox.update_layout()
        self._drafts.update_layout()
        self._outbox.update_layout()

    def _edit_preferences(self) -> None:
        prefs = preferences.PreferencesDialog(self)
        prefs.exec_()

    def _new_draft(self) -> None:
        self._drafts.new_item()

    def _export_pdf(self) -> None:
        widget = typing.cast(typing.Optional[mailbox_widget.MailboxWidget], self._tabs.currentWidget())
        if widget is None:
            return
        if widget.export_pdf():
            self._button_pdf_export.setIcon(gui.QIcon("export_to_pdf_done.png"))
            self._timer_export_pdf.start(500)

    def get_addresses(self) -> typing.List[typing.Tuple[str, str]]:
        return self._inbox.collect_addresses_unique()

    def _group_by_sender(self) -> None:
        grouped = self._button_group_by_sender.isChecked()
        self._button_group_by_sender.setChecked(grouped)
        preferences.set("group_by_sender", grouped)
        self._inbox.group_by_person(grouped)

    def copy_from_drafts_to_outbox(self, \
        thumb: thumbnail.Thumbnail, \
        addresses: typing.List[typing.Tuple[str, str]], \
        when: datetime.datetime) -> thumbnail.Thumbnail:
        new_thumb = thumb.clone(self._outbox, self, addresses, when)
        self._outbox.add_thumbnail(new_thumb)
        return new_thumb

    def copy_to_drafts_if_needed(self, \
        thumb: thumbnail.Thumbnail, \
        when: datetime.datetime) -> typing.Optional[thumbnail.Thumbnail]:
        if self._drafts.contains_thumbnail(thumb):
            return None
        else:
            new_thumb = thumb.clone(self._drafts, self, None, when)
            self._drafts.add_thumbnail(new_thumb)
            return new_thumb

    def remove_draft_thumbnail(self, thumb: thumbnail.Thumbnail) -> None:
        self._drafts.remove_thumbnail(thumb)
        thumb.hide()  #TODO: really get rid of it
