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
from PyQt5.QtCore import QObject
import PyQt5.QtWidgets as widgets 
import PyQt5.QtGui as gui
import random
import json
import preferences
import mailing


_preferences: typing.Dict[str, typing.Any] = {
    # better only use immutable types
    # make sure to use the right types for initialization here as they will be used for conversion on loading
    "name": "",
    "smtp_sender": "",
    "smtp_server": "",
    "smtp_receiver": "",
    "imap_user": "",
    "imap_server": "",
    "smooth_drawing": True,
    "group_by_sender": False,
    "number_of_columns": 3,
    "mailboxes_screen": (50, 50, 300, 500),
    "drawing_screen": (100, 100, 600, 500),
    "color": (0, 0, 0),
    "stroke_thickness": 3.0,
    "font_size": 14.0
}

_password: str = ""

def set_password(parent: widgets.QWidget) -> None:
    global _password
    _new_password, success = widgets.QInputDialog.getText(parent, "Passwort", "Mail-Passwort:", widgets.QLineEdit.Password, "")
    if success:
        _password = _new_password.strip()

def get_password() -> str:
    return _password

def get(which: str) -> typing.Any:
    return _preferences[which]

def set(which: str, value: typing.Any) -> None:
    if which in _preferences:
        _preferences[which] = value
    else:
        raise KeyError("No preference is called " + which)

def load() -> None:
    try:
        preferencesRead = {}
        with open("preferences.txt", "r", encoding="utf8") as file:
            preferencesRead = json.load(file)
            for key in _preferences:
                if key in preferencesRead:
                    r = preferencesRead[key]
                    if isinstance(_preferences[key], tuple):
                        r = tuple(r)
                    _preferences[key] = r
        if typing.cast(str, _preferences["name"]).strip() == "":
            _preferences["name"] = str(random.randrange(10000, 100000))
    except:
        pass  # TODO: notify user

def save() -> None:
    try:
        with open("preferences.txt", "w", encoding="utf8") as file:
            json.dump(_preferences, file, ensure_ascii=False)
    except:
        pass  # TODO: notify user

_update_receiver_connection_data_listeners = []
def attach_update_receiver_connection_data_listener(listener: typing.Any):
    if listener not in _update_receiver_connection_data_listeners:
        _update_receiver_connection_data_listeners.append(listener)

def detach_update_receiver_connection_data_listener(listener: typing.Any):
    _update_receiver_connection_data_listeners.remove(listener)

def _emit_update_receiver_connection_data(user: str, server: str, password: str) -> None:
    for listener in _update_receiver_connection_data_listeners:
        listener.update_receiver_connection_data(user, server, password)

class PreferencesDialog(widgets.QDialog):
    def __init__(self, parent: widgets.QWidget):
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")
        layout = widgets.QVBoxLayout()
        self.setLayout(layout)

        mail_group = widgets.QGroupBox("Mail-Konfiguration")
        layout.addWidget(mail_group)
        mail_group_layout = widgets.QFormLayout()
        mail_group.setLayout(mail_group_layout)

        # TODO: set buddies
        self._name: widgets.QLineEdit = widgets.QLineEdit()
        self._name.setText(get("name"))
        mail_group_layout.addRow(widgets.QLabel("Name zum Anzeigen"), self._name)
        self._smtp_sender: widgets.QLineEdit = widgets.QLineEdit()
        self._smtp_sender.setText(get("smtp_sender"))
        mail_group_layout.addRow(widgets.QLabel("SMTP-Absender"), self._smtp_sender)
        self._imap_user: widgets.QLineEdit = widgets.QLineEdit()
        self._imap_user.setText(get("imap_user"))
        mail_group_layout.addRow(widgets.QLabel("IMAP-User"), self._imap_user)

        self._smtp_receiver: widgets.QLineEdit = widgets.QLineEdit()
        self._smtp_receiver.setText(get("smtp_receiver"))
        mail_group_layout.addRow(widgets.QLabel("SMTP-Empfänger"), self._smtp_receiver)
        mail_group_layout.addRow(widgets.QLabel("    (SMTP-Empfänger leer = auf eingehende Mails reagieren)"))

        self._smtp_server: widgets.QLineEdit = widgets.QLineEdit()
        self._smtp_server.setText(get("smtp_server"))
        mail_group_layout.addRow(widgets.QLabel("SMTP-Server"), self._smtp_server)
        self._imap_server: widgets.QLineEdit = widgets.QLineEdit()
        self._imap_server.setText(get("imap_server"))
        mail_group_layout.addRow(widgets.QLabel("IMAP-Server"), self._imap_server)

        misc_group = widgets.QGroupBox("Sonstiges")
        layout.addWidget(misc_group)
        misc_group_layout = widgets.QFormLayout()
        misc_group.setLayout(misc_group_layout)

        self._smooth_drawing: widgets.QCheckBox = widgets.QCheckBox()
        self._smooth_drawing.setText("Kurven nach der Eingabe glätten")
        self._smooth_drawing.setChecked(get("smooth_drawing"))
        misc_group_layout.addRow(widgets.QLabel(""), self._smooth_drawing)

        button_password = widgets.QPushButton()
        layout.addWidget(button_password)
        button_password.setText("Mail-Passwort ändern...")
        button_password.clicked.connect(self.set_password)

        button_box = widgets.QDialogButtonBox(typing.cast(widgets.QDialogButtonBox.StandardButtons, widgets.QDialogButtonBox.Ok | widgets.QDialogButtonBox.Cancel))
        layout.addWidget(button_box)   
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

    def set_password(self):
        preferences.set_password(self.parent())
        _emit_update_receiver_connection_data(get("imap_user"), get("imap_server"), get_password())

    def accept(self):
        set("name", self._name.text().strip())
        set("smtp_sender", self._smtp_sender.text().strip())
        set("smtp_server", self._smtp_server.text().strip())
        set("smtp_receiver", self._smtp_receiver.text().strip())
        set("imap_user", self._imap_user.text().strip())
        set("imap_server", self._imap_server.text().strip())
        set("smooth_drawing", self._smooth_drawing.isChecked())
        save()
        _emit_update_receiver_connection_data(get("imap_user"), get("imap_server"), get_password())
        super().accept()

    def reject(self):
        super().reject()