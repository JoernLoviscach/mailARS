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
import thumbnail
import locale


class AddresseesDialog(widgets.QDialog):
    def __init__(self, parent: thumbnail.Thumbnail, \
        all_current_addresses: typing.List[typing.Tuple[str, str]], \
        addresses_in_thumbnail: typing.List[typing.Tuple[str, str]], \
        address_from_preferences: str, \
        send_to_all: bool, \
        send_to_explicit_receiver: bool) -> None:
        super().__init__(parent)
        self._send_to_all = send_to_all
        self._send_to_explicit_receiver = send_to_explicit_receiver
        self._addresses: typing.List[typing.Tuple[str, str]] = addresses_in_thumbnail

        self.setWindowTitle(self.tr("An wen schicken?"))

        layout = widgets.QHBoxLayout(self)
        self.setLayout(layout)

        scroll_area = widgets.QScrollArea(self)
        layout.addWidget(scroll_area)
        scroll_area.setHorizontalScrollBarPolicy(core.Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(core.Qt.ScrollBarAsNeeded)
        scroll_area.setWidgetResizable(True)

        content = widgets.QWidget(self)
        scroll_area.setWidget(content)

        content_layout = widgets.QVBoxLayout()
        content.setLayout(content_layout)

        self._check_from_prefs: typing.Optional[widgets.QCheckBox] = None
        if address_from_preferences != "":
            self._check_from_prefs = widgets.QCheckBox(address_from_preferences)
            self._check_from_prefs.setChecked(send_to_explicit_receiver \
                or (address_from_preferences, address_from_preferences) in addresses_in_thumbnail)
            content_layout.addWidget(self._check_from_prefs)
            content_layout.addWidget(widgets.QLabel())

        self._check_all = widgets.QCheckBox(self.tr("An alle empfangenen Adressen"))
        self._check_all.setChecked(send_to_all)
        self._check_all.stateChanged.connect(self._check_all_state_changed)
        content_layout.addWidget(self._check_all)
        content_layout.addWidget(widgets.QLabel())

        self._checkboxes: typing.List[typing.Tuple[widgets.QCheckBox, str, str]] = []
        for address, name in sorted(all_current_addresses, key=lambda x: locale.strxfrm(x[1])):
            check_address = widgets.QCheckBox(name)
            self._checkboxes.append((check_address, address, name))
            if (address, name) in addresses_in_thumbnail:
                check_address.setChecked(True)
            check_address.setEnabled(not send_to_all)
            content_layout.addWidget(check_address)

        button_box = widgets.QDialogButtonBox(typing.cast(widgets.QDialogButtonBox.StandardButtons, widgets.QDialogButtonBox.Ok | widgets.QDialogButtonBox.Cancel))
        button_box.setOrientation(core.Qt.Vertical)
        layout.addWidget(button_box)   
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

    def _check_all_state_changed(self, state: int) -> None:
        for c, _, _ in self._checkboxes:
            c.setEnabled(state != core.Qt.Checked)

    def accept(self) -> None:
        self._send_to_all = self._check_all.isChecked()
        if self._check_from_prefs is not None:
            self._send_to_explicit_receiver = self._check_from_prefs.isChecked()
        self._addresses = [(address, name) for (checkbox, address, name) in self._checkboxes if checkbox.isChecked()]
        super().accept()

    def reject(self) -> None:
        super().reject()

    def send_to_all(self) -> bool:
        return self._send_to_all

    def send_to_explicit_receiver(self) -> bool:
        return self._send_to_explicit_receiver

    # addresses may not be unique
    def addresses(self) -> typing.List[typing.Tuple[str, str]]:
        return self._addresses
        