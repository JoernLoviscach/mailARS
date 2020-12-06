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
import uuid
import locale
import os
import json
import graphics
import drawing_window
import mailbox_widget
import mailboxes_window
import preferences
import addressees_window
import mailing


class Thumbnail(widgets.QWidget):
    def __init__(self, mailbox_wid: mailbox_widget.MailboxWidget, \
        mailboxes_win: mailboxes_window.MailboxesWindow, \
        elements: typing.List[graphics.GraphicsObject], \
        addresses: typing.List[typing.Tuple[str, str]], \
        when: datetime.datetime, \
        message_id: typing.Optional[str]) -> None:
        super().__init__(mailbox_wid)
        
        self._mailbox_widget: mailbox_widget.MailboxWidget = mailbox_wid
        self._mailboxes_window: mailboxes_window.MailboxesWindow = mailboxes_win
        self._elements: typing.List[graphics.GraphicsObject] = elements
        self._editor: typing.Optional[drawing_window.DrawingWindow] = None
        self._size: core.QSize = core.QSize(100, 100)
        self._addresses: typing.List[typing.Tuple[str, str]] = addresses
        self._when: datetime.datetime = when

        if message_id is not None:
            self._message_id = message_id            
        else:
            self._message_id = str(uuid.uuid4().int)

        self._checkbox = widgets.QCheckBox(self)
        self._checkbox.stateChanged.connect(self._checkbox_state_changed)

        # Constructor called: a fresh Thumbnail, hence it's no reply
        # (unless we correct for that in the clone method).
        # If it's no reply send it to the teacher or to everybody.
        self._send_to_all: bool = (preferences.get("smtp_receiver") == "")
        self._send_to_explicit_receiver: bool = not self._send_to_all
        self.set_tooltip()

    def clone(self, mailbox_wid: mailbox_widget.MailboxWidget, \
        mailboxes_win: mailboxes_window.MailboxesWindow, \
        addresses: typing.Optional[typing.List[typing.Tuple[str, str]]], \
        when: datetime.datetime) -> Thumbnail:
        clone = Thumbnail(mailbox_wid, mailboxes_win, \
            graphics.clone_list(self._elements), \
            addresses if addresses is not None else self._addresses, \
            when, None)
        clone._editor = None
        clone._size = core.QSize(self._size)

        # after all, it _is_ a reply
        clone._send_to_all = False
        clone._send_to_explicit_receiver = False
        clone.set_tooltip()
        return clone

    def get_message_id(self) -> str:
        return self._message_id

    def get_when(self) -> datetime.datetime:
        return self._when

    def get_checkbox_state(self) -> bool:
        return self._checkbox.isChecked()

    def set_checkbox_state(self, state: bool) -> None:
        self._checkbox.setChecked(state)

    def _checkbox_state_changed(self, state: int) -> None:
        self._mailbox_widget.checkbox_state_changed(self, state)

    def set_tooltip(self) -> None:
        self.setToolTip(", ".join(sorted( \
            [n for (_, n) in self._addresses], key=lambda x: locale.strxfrm(x))) \
            + self._when.astimezone(datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo).strftime("\n%x %X"))

#    def contains_address(self, address: str, name: str) -> bool:
#        return (address, name) in self._addresses

    def get_first_address(self) -> typing.Optional[typing.Tuple[str, str]]:
        if len(self._addresses) > 0:
            return self._addresses[0]
        else:
            return None

    def collect_addresses_in(self, addresses: typing.List[typing.Tuple[str, str]]) -> None:
        addresses.extend(self._addresses)

    def exec_addressees_dialog(self, window: drawing_window.DrawingWindow):
        aw = addressees_window.AddresseesDialog(window, \
            self._mailboxes_window.get_addresses(), \
            self._addresses, \
            preferences.get("smtp_receiver"), \
            self._send_to_all, \
            self._send_to_explicit_receiver)
        aw.exec_()
        self._send_to_all = aw.send_to_all()
        self._send_to_explicit_receiver = aw.send_to_explicit_receiver()
        self._addresses = aw.addresses()

    def get_definitive_addresses(self) -> typing.List[typing.Tuple[str, str]]:
        addresses: typing.List[typing.Tuple[str, str]] = []
        if self._send_to_all:
            addresses.extend(self._mailboxes_window.get_addresses())
        rec = preferences.get("smtp_receiver")
        if rec != "" and self._send_to_explicit_receiver:
            addresses.append((rec, rec))
        if not self._send_to_all:
            addresses.extend(self._addresses)
        # make unique
        addresses = list(set(addresses))
        return addresses

    def send(self, drawing_wid: drawing_window.DrawingWindow, \
        addresses: typing.List[typing.Tuple[str, str]], \
        when: datetime.datetime) -> None:
        mailing.send(self._mailboxes_window, \
            drawing_wid, \
            [a for (a, _) in addresses], \
            self._elements, \
            when, \
            self._message_id, \
            preferences.get("name"), \
            preferences.get("smtp_sender"), \
            preferences.get("smtp_server"), \
            preferences.get_password())

    def paintEvent(self, event: gui.QPaintEvent) -> None:
        rect = graphics.get_bounding_box_of_list(self._elements)
        w: float
        h: float
        s: float
        if rect.width() * self._size.height() > rect.height() * self._size.width():
            w = self._size.width()
            s = w / (rect.width() + 0.1)
            h = s * rect.height()
        else:
            h = self._size.height()
            s = h / (rect.height() + 0.1)
            w = s * rect.width()

        x = 0.5 * (self._size.width() - w)
        y = 0.5 * (self._size.height() - h)

        qp = gui.QPainter()
        qp.begin(self)

        if self._editor is not None:
            qp.drawText(core.QRect(0, 0, self._size.width(), self._size.height()), core.Qt.AlignCenter, "(im Editor)")
        else:
            qp.setRenderHints(typing.cast(gui.QPainter.RenderHint, gui.QPainter.Antialiasing | gui.QPainter.SmoothPixmapTransform))
            transform = gui.QTransform()
            transform.translate(x, y)
            transform.scale(s, s)
            transform.translate(-rect.left(), -rect.top())
            qp.setTransform(transform)
            for element in self._elements:
                element.draw(qp, False)
        
        qp.end()

    def resizeEvent(self, event: gui.QResizeEvent) -> None:
        self._size = event.size()

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        rect = graphics.get_bounding_box_of_list(self._elements)
        aspect = min(3.0, max(0.333, rect.height() / (rect.width() + 0.1)))
        return int(width * aspect)

    def mouseReleaseEvent(self, event: gui.QMouseEvent) -> None:
        if event.button() == core.Qt.LeftButton:
            now = datetime.datetime.now(datetime.timezone.utc).astimezone()
            new_thumb = self._mailboxes_window.copy_to_drafts_if_needed(self, now)
            if new_thumb is None:
                self.open_in_editor(True)
            else:
                new_thumb.open_in_editor(False)

    def editor_is_closed(self, is_dirty: bool):
        self._editor = None
        self.update()
        if not is_dirty:
            self._mailboxes_window.remove_draft_thumbnail(self)
        else:
            self.save()

    def open_in_editor(self, is_already_dirty: bool):
        if self._editor is None:
            self._editor = drawing_window.DrawingWindow(self, self._elements, is_already_dirty)
            self.update()
        else:
            self._editor.activateWindow()

    def save(self) -> None:
        folder = os.path.join(self._mailbox_widget.get_folder_name(), self._message_id)
        try:
            if not os.path.exists(folder):
                os.mkdir(folder)

            metadata = { "addresses": self._addresses, "when": self._when.isoformat() }
            with open(os.path.join(folder, "metadata.txt"), "w", encoding="utf8") as file:
                json.dump(metadata, file, ensure_ascii=False)

            document_text, files = graphics.serialize(self._elements)
            with open(os.path.join(folder, "graphics.svg"), "w", encoding="utf8") as file:
                file.write(document_text)

            for name in files:
                    f = core.QSaveFile(os.path.join(folder, name))
                    f.open(core.QIODevice.WriteOnly)
                    f.write(files[name])
                    f.commit()

        except Exception as ex:
            widgets.QMessageBox.critical(self, "Schreibfehler", "Fehler beim Schreiben der Nachricht " + self._message_id + ":\n" + str(ex))

    @staticmethod
    def load(mailbox_wid: mailbox_widget.MailboxWidget, \
        mailboxes_win: mailboxes_window.MailboxesWindow, \
        mailbox_folder: str, \
        single_mail_folder: str) -> Thumbnail:

        files: typing.Dict[str, core.QByteArray] = {}
        message_id = single_mail_folder 
        folder = os.path.join(mailbox_folder, single_mail_folder)

        with open(os.path.join(folder, "metadata.txt"), "r", encoding="utf8") as file:
            metadata = json.load(file)
        # JSON turns tuples into lists, hence:
        addresses = [(x, y) for x, y in metadata["addresses"]]

        folder_files = os.listdir(folder)
        files = {}
        for file in folder_files:
            if file.endswith(".jpg"):
                f = core.QFile(os.path.join(folder, file))
                f.open(core.QIODevice.ReadOnly)
                files[file] = f.readAll()
                f.close()

        with open(os.path.join(folder, "graphics.svg"), "r", encoding="utf8") as file:
            document_text = file.read()
            elements = graphics.deserialize(document_text, files)

        return Thumbnail(mailbox_wid, mailboxes_win, elements, addresses, datetime.datetime.fromisoformat(metadata["when"]), message_id)

    def remove(self) -> None:
        folder = os.path.join(self._mailbox_widget.get_folder_name(), self._message_id)
        try:
            files = os.listdir(folder)
            for f in files:
                os.remove(os.path.join(folder, f))
            os.rmdir(folder)
        except Exception as ex:
            widgets.QMessageBox.critical(self, "Löschfehler", "Fehler beim Löschen des Verzeichnisses " + folder + ":\n" + str(ex))
