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
import os
import graphics
import preferences
import drawing_widget
import camera_capture
import thumbnail
import mailboxes_window


class DrawingWindow(widgets.QMainWindow):
    def __init__(self, parent: thumbnail.Thumbnail, \
            elements: typing.List[graphics.GraphicsObject], \
            is_already_dirty: bool):
        super().__init__()  # No parent, so that this window can be behind the mailbox window and can be screenshared on its own
        self._mailboxes_window: mailboxes_window.MailboxesWindow = typing.cast(mailboxes_window.MailboxesWindow, parent.parent().parent().parent().parent().parent().parent())
        self._mailboxes_window.append_other_main_window(self)
        self._thumbnail: thumbnail.Thumbnail = parent
        self._is_dirty: bool = is_already_dirty

        self._drawing_widget = drawing_widget.DrawingWidget(self, elements)
        self.setCentralWidget(self._drawing_widget)

        self._toolbar = widgets.QToolBar(self)
        self.addToolBar(self._toolbar)

        self._button_send = widgets.QToolButton()
        self._button_send.setToolTip(self.tr("Send"))
        self._button_send.setIcon(gui.QIcon("need_to_send.png" if self._is_dirty else "send.png"))
        self._button_send.setIconSize(core.QSize(32, 32))
        self._button_send.clicked.connect(self._drawing_widget.clean_ui)
        self._button_send.clicked.connect(self._send)
        self._toolbar.addWidget(self._button_send)

        self._button_addresses = widgets.QToolButton()
        self._button_addresses.setToolTip(self.tr("Addressees"))
        self._button_addresses.setIcon(gui.QIcon("addressees.png"))
        self._button_addresses.setIconSize(core.QSize(32, 32))
        self._button_addresses.clicked.connect(self._exec_addressees_dialog)
        self._toolbar.addWidget(self._button_addresses)

        self._button_undo = widgets.QToolButton()
        self._button_undo.setToolTip(self.tr("Undo"))
        self._button_undo.setIcon(gui.QIcon("undo.png"))
        self._button_undo.setIconSize(core.QSize(32, 32))
        self._button_undo.clicked.connect(self._undo)
        self._button_undo.setEnabled(False)
        self._toolbar.addWidget(self._button_undo)

        self._button_redo = widgets.QToolButton()
        self._button_redo.setToolTip(self.tr("Redo"))
        self._button_redo.setIcon(gui.QIcon("redo.png"))
        self._button_redo.setIconSize(core.QSize(32, 32))
        self._button_redo.clicked.connect(self._redo)
        self._button_redo.setEnabled(False)
        self._toolbar.addWidget(self._button_redo)

        #TODO: solve this with stylesheets
        label_separator = widgets.QLabel()
        label_separator.setText("      ")
        self._toolbar.addWidget(label_separator)

        label_separator = widgets.QLabel()
        label_separator.setText(self.tr("Drawing:"))
        self._toolbar.addWidget(label_separator)

        self._button_group_mode = widgets.QButtonGroup(self._toolbar)
        self._button_group_mode.buttonClicked.connect(self._drawing_widget.clean_ui)
        self._button_group_mode.buttonClicked.connect(self._tool_changed)
        
        self._button_draw = widgets.QToolButton()
        self._button_draw.setToolTip(self.tr("Draw"))
        self._button_draw.setIcon(gui.QIcon("draw.png"))
        self._button_draw.setIconSize(core.QSize(32, 32))
        self._button_group_mode.addButton(self._button_draw, drawing_widget.Mode.DRAWING)
        self._toolbar.addWidget(self._button_draw)
        self._button_draw.setCheckable(True)
        self._button_draw.setChecked(True)
        self._tool_changed(self._button_draw)  # fire once, for initial cursor shape

        self._label_stroke_preview = widgets.QLabel()
        self._toolbar.addWidget(self._label_stroke_preview)

        self._button_stroke_color = widgets.QToolButton()
        self._button_stroke_color.setToolTip(self.tr("Color"))
        self._button_stroke_color.setIcon(gui.QIcon("color.png"))
        self._button_stroke_color.setIconSize(core.QSize(32, 32))
        self._button_stroke_color.clicked.connect(self._exec_color_dialog)
        self._toolbar.addWidget(self._button_stroke_color)

        self._frame_stroke_thickness = widgets.QFrame(self._toolbar, core.Qt.Popup)
        layout_stroke_thickness = widgets.QHBoxLayout()
        self._frame_stroke_thickness.setLayout(layout_stroke_thickness)
        self._silder_stroke_thickness = widgets.QSlider()
        layout_stroke_thickness.addWidget(self._silder_stroke_thickness)
        self._silder_stroke_thickness.setMinimum(1)
        self._silder_stroke_thickness.setMaximum(17)
        self._silder_stroke_thickness.setTickInterval(4)
        self._silder_stroke_thickness.setTickPosition(widgets.QSlider.TicksLeft)
        self._silder_stroke_thickness.valueChanged.connect(self._stroke_thickness_changed)
        self._button_stroke_thickness = widgets.QToolButton()
        self._button_stroke_thickness.setToolTip(self.tr("Thickness"))
        self._button_stroke_thickness.setIcon(gui.QIcon("stroke_thickness.png"))
        self._button_stroke_thickness.setIconSize(core.QSize(32, 32))
        self._button_stroke_thickness.clicked.connect(self._exec_stroke_thickness_slider)
        self._toolbar.addWidget(self._button_stroke_thickness)

        self._set_stroke_icon()

        self._button_erase = widgets.QToolButton()
        self._button_erase.setToolTip(self.tr("Erase"))
        self._button_erase.setIcon(gui.QIcon("erase.png"))
        self._button_erase.setIconSize(core.QSize(32, 32))
        self._button_erase.setCheckable(True)
        self._toolbar.addWidget(self._button_erase)
        self._button_group_mode.addButton(self._button_erase, drawing_widget.Mode.ERASING)

        #TODO: solve this with stylesheets
        label_separator = widgets.QLabel()
        label_separator.setText("      ")
        self._toolbar.addWidget(label_separator)

        label_separator = widgets.QLabel()
        label_separator.setText(self.tr("Text:"))
        self._toolbar.addWidget(label_separator)

        self._button_text = widgets.QToolButton()
        self._button_text.setToolTip(self.tr("Type"))
        self._button_text.setIcon(gui.QIcon("text.png"))
        self._button_text.setIconSize(core.QSize(32, 32))
        self._button_text.setCheckable(True)
        self._toolbar.addWidget(self._button_text)
        self._button_group_mode.addButton(self._button_text, drawing_widget.Mode.TYPING)

        self._frame_font_size = widgets.QFrame(self._toolbar, core.Qt.Popup)
        layout_font_size = widgets.QHBoxLayout()
        self._frame_font_size.setLayout(layout_font_size)
        self._silder_font_size = widgets.QSlider()
        layout_font_size.addWidget(self._silder_font_size)
        self._silder_font_size.setMinimum(10)
        self._silder_font_size.setMaximum(43)
        self._silder_font_size.setTickInterval(4)
        self._silder_font_size.setTickPosition(widgets.QSlider.TicksLeft)
        self._silder_font_size.valueChanged.connect(self._font_size_changed)
        self._button_font_size = widgets.QToolButton()
        self._button_font_size.setToolTip(self.tr("Size"))
        self._button_font_size.setIcon(gui.QIcon("font_size.png"))
        self._button_font_size.setIconSize(core.QSize(32, 32))
        self._button_font_size.clicked.connect(self._exec_font_size_slider)
        self._toolbar.addWidget(self._button_font_size)

        #TODO: solve this with stylesheets
        label_separator = widgets.QLabel()
        label_separator.setText("      ")
        self._toolbar.addWidget(label_separator)

        label_separator = widgets.QLabel()
        label_separator.setText(self.tr("Photo:"))
        self._toolbar.addWidget(label_separator)

        self._button_photo = widgets.QToolButton()
        self._button_photo.setToolTip(self.tr("Take Photo"))
        self._button_photo.setIcon(gui.QIcon("photo.png"))
        self._button_photo.setIconSize(core.QSize(32, 32))
        self._button_photo.clicked.connect(self._shoot)
        self._toolbar.addWidget(self._button_photo)

        #TODO: solve this with stylesheets
        label_separator = widgets.QLabel()
        label_separator.setText("      ")
        self._toolbar.addWidget(label_separator)

        label_separator = widgets.QLabel()
        label_separator.setText(self.tr("Selection:"))
        self._toolbar.addWidget(label_separator)

        self._button_select = widgets.QToolButton()
        self._button_select.setToolTip(self.tr("Select"))
        self._button_select.setIcon(gui.QIcon("select.png"))
        self._button_select.setIconSize(core.QSize(32, 32))
        self._button_select.setCheckable(True)
        self._toolbar.addWidget(self._button_select)
        self._button_group_mode.addButton(self._button_select, drawing_widget.Mode.SELECTING)

        self._button_delete = widgets.QToolButton()
        self._button_delete.setToolTip(self.tr("Delete"))
        self._button_delete.setIcon(gui.QIcon("delete.png"))
        self._button_delete.setIconSize(core.QSize(32, 32))
        self._button_delete.clicked.connect(self._drawing_widget.clean_ui)
        self._button_delete.clicked.connect(self._delete)
        self._toolbar.addWidget(self._button_delete)

        screen = preferences.get("drawing_screen")
        self.setGeometry(screen[0], screen[1], screen[2], screen[3])
        
        self.setWindowIcon(gui.QIcon("program.png"))
        self.show()

    def closeEvent(self, event: gui.QCloseEvent) -> None:
        if self.isVisible():  # workaround for https://bugreports.qt.io/browse/QTBUG-43344
            self._drawing_widget.clean_ui()
            screen = self.geometry()
            preferences.set("drawing_screen", (screen.x(), screen.y(), screen.width(), screen.height()))
            self._thumbnail.editor_is_closed(self._is_dirty)
        event.accept()

    def resizeEvent(self, event: gui.QResizeEvent) -> None:
        screen = self.geometry()
        preferences.set("drawing_screen", (screen.x(), screen.y(), screen.width(), screen.height()))
        return super().resizeEvent(event)

    def moveEvent(self, event: gui.QMoveEvent) -> None:
        screen = self.geometry()
        preferences.set("drawing_screen", (screen.x(), screen.y(), screen.width(), screen.height()))
        return super().moveEvent(event)

    @core.pyqtSlot(bool)
    def set_send_mail_status(self, status: bool) -> None:
        self._button_send.setEnabled(status)

    def _toggle_toolbar(self) -> None:
            if self._toolbar.isVisible():
                self._toolbar.hide()
                self.hide()  # must not change flags on a visible window
                self.setWindowFlag(core.Qt.FramelessWindowHint, True)
                self.show()
            else:
                self._toolbar.show()
                self.hide()  # must not change flags on a visible window
                self.setWindowFlag(core.Qt.FramelessWindowHint, False)
                self.show()

    def keyPressEvent(self, event: gui.QKeyEvent) -> None:
        event.accept()
        key = event.key()
        control = bool(event.modifiers() & core.Qt.ControlModifier)
        if key == core.Qt.Key_P:
            self._toggle_toolbar()
        # must handle shortcut keys here instead of assigning them to the buttons
        # because they wouldn't work if the toolbar is hidden
        elif key == core.Qt.Key_Return and control:
            self._button_send.click()
        elif key == core.Qt.Key_A:
            self._button_addresses.click() 
        elif key == core.Qt.Key_Z:
            self._button_undo.click()
        elif key == core.Qt.Key_Y:
            self._button_redo.click()
        elif key == core.Qt.Key_Q:
            self._button_draw.click()
        elif key == core.Qt.Key_S:
            self._button_stroke_color.click()
        elif key == core.Qt.Key_D:
            self._button_stroke_thickness.click()
        elif key == core.Qt.Key_W:
            self._button_erase.click()
        elif key == core.Qt.Key_E:
            self._button_text.click()
        elif key == core.Qt.Key_F:
            self._button_font_size.click()
        elif key == core.Qt.Key_G:
            self._button_photo.click()
        elif key == core.Qt.Key_R:
            self._button_select.click()
        elif key == core.Qt.Key_Delete:
            self._button_delete.click()
        elif key == core.Qt.Key_1:
            self._set_color(gui.QColor(0, 0, 0))
        elif key == core.Qt.Key_2:
            self._set_color(gui.QColor(255, 0, 0))
        elif key == core.Qt.Key_3:
            self._set_color(gui.QColor(0, 196, 0))
        elif key == core.Qt.Key_4:
            self._set_color(gui.QColor(0, 0, 255))
        elif key == core.Qt.Key_5:
            self._set_color(gui.QColor(128, 128, 128))
        elif key == core.Qt.Key_6:
            self._set_color(gui.QColor(256, 165, 0))
        else:
            event.ignore()
        super().keyPressEvent(event)  # for shortcut of buttons

    def _undo(self) -> None:
        self._drawing_widget.clean_ui()
        self._drawing_widget.clear_selection()
        self._drawing_widget.undo()

    def _redo(self) -> None:
        self._drawing_widget.clean_ui()
        self._drawing_widget.clear_selection()
        self._drawing_widget.redo()

    def set_undo_status(self, status: bool) -> None:
        self._button_undo.setEnabled(status)

    def set_redo_status(self, status: bool) -> None:
        self._button_redo.setEnabled(status)

    def _delete(self):
        self._drawing_widget.delete_selected_or_all()
        pass

    def _exec_addressees_dialog(self):
        self._drawing_widget.clean_ui()
        self._thumbnail.exec_addressees_dialog(self)

    def _tool_changed(self, button: widgets.QToolButton) -> None:
        self._drawing_widget.set_cursor(self.get_mode())
        if self.get_mode() != drawing_widget.Mode.SELECTING:            
            self._drawing_widget.set_selection_tools_visible(False)
            self._drawing_widget.clear_selection()

    def _set_color(self, color: gui.QColor) -> None:
        preferences.set("color", (color.red(), color.green(), color.blue()))
        self._drawing_widget.update_stroke_color(color)
        self._set_stroke_icon()

    def _exec_color_dialog(self) -> None:
        color = widgets.QColorDialog.getColor(gui.QColor(*preferences.get("color")))
        self._set_color(color)

    def _exec_stroke_thickness_slider(self) -> None:
        self._frame_stroke_thickness.move(self.mapToGlobal(self._button_stroke_thickness.geometry().bottomLeft()))
        self._silder_stroke_thickness.setValue(preferences.get("stroke_thickness"))
        self._frame_stroke_thickness.show()

    def _stroke_thickness_changed(self, value: int) -> None:
        preferences.set("stroke_thickness", value)
        self._drawing_widget.update_stroke_thickness(value)
        self._set_stroke_icon()

    def _set_stroke_icon(self) -> None:
        col = preferences.get("color")
        th = preferences.get("stroke_thickness")
        qcol = gui.QColor(*col)
        pxm = gui.QPixmap(30, th)
        pxm.fill(qcol)
        self._label_stroke_preview.setPixmap(pxm)

    def _exec_font_size_slider(self) -> None:
        self._frame_font_size.move(self.mapToGlobal(self._button_font_size.geometry().bottomLeft()))
        self._silder_font_size.setValue(preferences.get("font_size"))
        self._frame_font_size.show()

    def _font_size_changed(self, value: int) -> None:
        preferences.set("font_size", value)
        self._drawing_widget.update_font_size(value)

    def get_mode(self) -> drawing_widget.Mode:
        return typing.cast(drawing_widget.Mode, self._button_group_mode.checkedId())

    def set_dirty(self) -> None:
        if not self._is_dirty:
            self._button_send.setIcon(gui.QIcon("need_to_send.png"))
            self._is_dirty = True

    def set_clean(self) -> None:
        if self._is_dirty:
            self._button_send.setIcon(gui.QIcon("send.png"))
            self._is_dirty = False

    def _shoot(self) -> None:
        self._drawing_widget.clean_ui()
        dlg: typing.Optional[camera_capture.CameraCapture] = None
        try:
            dlg = camera_capture.CameraCapture(self)
            dlg.exec_()
            img = dlg.get_image()
            if img is not None:
                self._drawing_widget.add_image(img)
                self.set_dirty()
        except Exception as ex:
            widgets.QMessageBox.critical(self, self.tr("Warning"), str(ex))
        finally:
            if dlg is not None:
                dlg.close()  #TODO: Get completely rid of it.

    def _send(self) -> None:
        self._drawing_widget.clean_ui()
        now = datetime.datetime.now(datetime.timezone.utc).astimezone()
        addresses = self._thumbnail.get_definitive_addresses()
        thumb_clone = self._mailboxes_window.copy_from_drafts_to_outbox(self._thumbnail, addresses, now)
        thumb_clone.send(self, addresses, now)
        self.set_clean()  # If we can't send successfully (which we don't know yet), at least the copy in the outbox is ok.
