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
import PyQt5.QtPrintSupport as print
import datetime
import preferences
import graphics
import thumbnail
import mailboxes_window
import os


class MailboxWidget(widgets.QScrollArea):
    def __init__(self, \
        mailboxes_window: mailboxes_window.MailboxesWindow, \
        folder_name: str) -> None:
        super().__init__(mailboxes_window)
        self._mailboxes_window = mailboxes_window
        self._items: typing.List[thumbnail.Thumbnail] = []
        self._grouped_by_person = False

        self.setHorizontalScrollBarPolicy(core.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(core.Qt.ScrollBarAsNeeded)
        self.setWidgetResizable(True)
        self._thumbnails_widget = widgets.QWidget(self)
        self.setWidget(self._thumbnails_widget)
        self._thumbnails_layout = widgets.QGridLayout()
        self._thumbnails_widget.setLayout(self._thumbnails_layout)
        
        self._folder_name = folder_name
        try:
            if not os.path.exists(self._folder_name):
                os.mkdir(self._folder_name)
            else:
                folders = os.listdir(self._folder_name)
                for single_mail_folder in folders:
                    item = thumbnail.Thumbnail.load(self, self._mailboxes_window, self._folder_name, single_mail_folder)
                    self._items.append(item)
                self.update_layout()
                self.update()
        except Exception as ex:
            widgets.QMessageBox.critical(self, "Fehler", "Dateifehler in " + self._folder_name + ":\n" + str(ex))

    def get_folder_name(self) -> str:
        return self._folder_name

    def group_by_person(self, grouped: bool) -> None:
        self._grouped_by_person = grouped
        self.update_layout()

    def update_layout(self) -> None:
        # remove all from layout
        while self._thumbnails_layout.takeAt(0) is not None:
            pass

        items_to_show = sorted(self._items, key=lambda item: item.get_when())
        if self._grouped_by_person:
            seen_addresses = []
            items_to_be_removed = []
            for item in reversed(items_to_show):
                address = item.get_first_address()
                if address is None or address not in seen_addresses:
                    seen_addresses.append(address)
                else:
                    items_to_be_removed.append(item)
            items_to_show = [item for item in items_to_show if item not in items_to_be_removed]
                
        for item in self._items:
            item.setVisible(item in items_to_show)
            item.set_checkbox_state(False)

        n = preferences.get("number_of_columns")
        for i, item in enumerate(items_to_show):
            self._thumbnails_layout.addWidget(item, i // n, i % n)

    def new_item(self) -> None:
        now = datetime.datetime.now(datetime.timezone.utc).astimezone()
        item = thumbnail.Thumbnail(self, self._mailboxes_window, [], [], now, None)
        self._items.append(item)
        item.save()
        self.update_layout()
        self.update()
        item.open_in_editor(False)

    def add_item(self, \
        address: str, \
        name: str, \
        elements: typing.List[graphics.GraphicsObject], \
        when: datetime.datetime, \
        message_id: str) -> None:

        item = thumbnail.Thumbnail(self, self._mailboxes_window, elements, [(address, name)], when, message_id)
        self._items.append(item)
        item.save()
        self.update_layout()
        self.update()

    def collect_addresses_unique(self) -> typing.List[typing.Tuple[str, str]]:
        addresses: typing.List[typing.Tuple[str, str]] = []
        for item in self._items:
            item.collect_addresses_in(addresses)
        return list(set(addresses))

    def add_thumbnail(self, thumb: thumbnail.Thumbnail) -> None:
        self._items.append(thumb)
        thumb.save()
        self.update_layout()
        self.update()

    def remove_thumbnail(self, thumb: thumbnail.Thumbnail) -> None:
        thumb.remove()
        self._items.remove(thumb)
        self.update_layout()
        self.update()

    def contains_thumbnail(self, thumb: thumbnail.Thumbnail) -> bool:
        return thumb in self._items

#    def replace_thumbnail(self, thumb: thumbnail.Thumbnail, new_thumb: thumbnail.Thumbnail) -> None:
#        i = self._items.index(thumb)
#        self._items[i] = new_thumb
#        thumb.save()
#        self.update_layout()
#        self.update()

    def checkbox_state_changed(self, thumb: thumbnail.Thumbnail, state: int) -> None:
        if state == core.Qt.Checked and not (gui.QGuiApplication.keyboardModifiers() == core.Qt.ShiftModifier):
            for th in self._items:
                if th != thumb:
                    th.set_checkbox_state(False)

    def get_message_ids(self) -> typing.List[str]:
        return [item.get_message_id() for item in self._items]

    def export_pdf(self) -> bool:
        to_print = [th for th in self._items if th.get_checkbox_state()]
        if len(to_print) == 0:
            to_print = self._items

        if len(to_print) == 0:
            widgets.QMessageBox.information(self, "Information", "Es gibt nichts zu exportieren!")
            return False

        try:
            if not os.path.isdir("export"):
                os.mkdir("export")
            filename = os.path.join("export", datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".pdf")

            printer = print.QPrinter()
            printer.setOutputFormat(print.QPrinter.PdfFormat)
            printer.setOutputFileName(filename)
            page_rect = printer.pageRect()
            painter = gui.QPainter()

            painter.begin(printer)
            painter.setRenderHints(typing.cast(gui.QPainter.RenderHint, gui.QPainter.Antialiasing | gui.QPainter.SmoothPixmapTransform))
            for th in to_print:
                bb = graphics.get_bounding_box_of_list(th._elements)
                scale = 0.95 * min(page_rect.width() / (bb.width() + 0.1), \
                    page_rect.height() / (bb.height() + 0.1))
                transform = gui.QTransform()
                transform.translate(page_rect.width() / 2, page_rect.height() / 2)
                transform.scale(scale, scale)
                transform.translate(-bb.left() - bb.width() / 2, -bb.top() - bb.height() / 2)
                painter.setTransform(transform)
                for element in th._elements:
                    element.draw(painter, False)
            
                if th != to_print[-1]:
                    printer.newPage()
            painter.end()
        except Exception as ex:
            widgets.QMessageBox.critical(self, "Fehler", str(ex))
            return False
            
        return True
