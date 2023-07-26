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
import random
import json
import preferences


_preferences: typing.Dict[str, typing.Any] = {
    # Better only use immutable types.
    # Use the right types for initialization here
    # as they will be used for converting
    # the data found in the preferences file.
    "language": "en",
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

def set_password(parent: typing.Union[widgets.QWidget, widgets.QApplication]) -> None:
    global _password
    par = parent
    app = widgets.QApplication.instance()
    if isinstance(parent, widgets.QApplication):
        par = None
    _new_password, success = widgets.QInputDialog.getText(par, app.translate("Password", "Password"), app.translate("Password", "Mail password"), widgets.QLineEdit.Password, "")
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
        self.setWindowTitle(self.tr("Settings"))
        layout = widgets.QVBoxLayout()
        self.setLayout(layout)

        language_group = widgets.QGroupBox(self.tr("Language"))
        layout.addWidget(language_group)
        language_group_outer_layout = widgets.QVBoxLayout()
        language_group.setLayout(language_group_outer_layout)

        language_group_radios = widgets.QWidget()
        language_group_outer_layout.addWidget(language_group_radios)
        language_group_radios_layout = widgets.QHBoxLayout()
        language_group_radios.setLayout(language_group_radios_layout)

        #TODO: Generate these options from the names of the translation files
        self._radio_english = widgets.QRadioButton()
        self._radio_english.setText("en")
        self._radio_english.setChecked(get("language") == "en")
        language_group_radios_layout.addWidget(self._radio_english, core.Qt.AlignLeft)
        self._radio_german = widgets.QRadioButton()
        self._radio_german.setText("de")
        self._radio_german.setChecked(get("language") == "de")
        language_group_radios_layout.addWidget(self._radio_german, core.Qt.AlignLeft)
        self._radio_ukrainian = widgets.QRadioButton()
        self._radio_ukrainian.setText("uk")
        self._radio_ukrainian.setChecked(get("language") == "uk")
        language_group_radios_layout.addWidget(self._radio_ukrainian, core.Qt.AlignLeft)
        self._radio_russian = widgets.QRadioButton()
        self._radio_russian.setText("ru")
        self._radio_russian.setChecked(get("language") == "ru")
        language_group_radios_layout.addWidget(self._radio_russian, core.Qt.AlignLeft)

        language_group_outer_layout.addWidget(widgets.QLabel(self.tr("Changes are applied on next start")))

        mail_group = widgets.QGroupBox(self.tr("Mail Settings"))
        layout.addWidget(mail_group)
        mail_group_layout = widgets.QFormLayout()
        mail_group.setLayout(mail_group_layout)

        # TODO: set buddies
        self._name: widgets.QLineEdit = widgets.QLineEdit()
        self._name.setText(get("name"))
        mail_group_layout.addRow(widgets.QLabel(self.tr("Name to be displayed")), self._name)
        self._smtp_sender: widgets.QLineEdit = widgets.QLineEdit()
        self._smtp_sender.setText(get("smtp_sender"))
        mail_group_layout.addRow(widgets.QLabel(self.tr("SMTP sender")), self._smtp_sender)
        self._imap_user: widgets.QLineEdit = widgets.QLineEdit()
        self._imap_user.setText(get("imap_user"))
        mail_group_layout.addRow(widgets.QLabel(self.tr("IMAP user")), self._imap_user)

        self._smtp_receiver: widgets.QLineEdit = widgets.QLineEdit()
        self._smtp_receiver.setText(get("smtp_receiver"))
        mail_group_layout.addRow(widgets.QLabel(self.tr("SMTP receiver")), self._smtp_receiver)
        mail_group_layout.addRow(widgets.QLabel(self.tr("Leave empty to only react to incoming mails")))

        self._smtp_server: widgets.QLineEdit = widgets.QLineEdit()
        self._smtp_server.setText(get("smtp_server"))
        mail_group_layout.addRow(widgets.QLabel(self.tr("SMTP server")), self._smtp_server)
        self._imap_server: widgets.QLineEdit = widgets.QLineEdit()
        self._imap_server.setText(get("imap_server"))
        mail_group_layout.addRow(widgets.QLabel(self.tr("IMAP server")), self._imap_server)

        misc_group = widgets.QGroupBox(self.tr("Miscellaneous"))
        layout.addWidget(misc_group)
        misc_group_layout = widgets.QFormLayout()
        misc_group.setLayout(misc_group_layout)

        self._smooth_drawing: widgets.QCheckBox = widgets.QCheckBox()
        self._smooth_drawing.setText(self.tr("Smooth curves after drawing"))
        self._smooth_drawing.setChecked(get("smooth_drawing"))
        misc_group_layout.addRow(widgets.QLabel(""), self._smooth_drawing)

        layout.addStretch()

        button_password = widgets.QPushButton()
        layout.addWidget(button_password)
        button_password.setText(self.tr("Change mail password..."))
        button_password.clicked.connect(self.set_password)

        button_box = widgets.QDialogButtonBox(typing.cast(widgets.QDialogButtonBox.StandardButtons, widgets.QDialogButtonBox.Ok | widgets.QDialogButtonBox.Cancel))
        layout.addWidget(button_box)   
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

    def set_password(self):
        preferences.set_password(self.parent())
        _emit_update_receiver_connection_data(get("imap_user"), get("imap_server"), get_password())

    def accept(self):
        lang = "en"
        if self._radio_german.isChecked():
            lang = "de"
        elif self._radio_ukrainian.isChecked():
            lang = "uk"
        elif self._radio_russian.isChecked():
            lang = "ru"
        set("language", lang)
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
