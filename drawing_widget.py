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
from enum import IntEnum
import graphics
import drag_button
import text_editor
import preferences
import drawing_window
import undo_redo


class Mode(IntEnum):
    NONE = 0
    DRAWING = 1
    ERASING = 2
    TYPING = 3
    SELECTING = 4

class DrawingWidget(widgets.QWidget):
    def __init__(self, drawing_win: drawing_window.DrawingWindow, elements: typing.List[graphics.GraphicsObject]) -> None:
        super().__init__(drawing_win)
        pal = self.palette()
        pal.setColor(gui.QPalette.Background, core.Qt.white)
        self.setAutoFillBackground(True)
        self.setPalette(pal)

        self._undo_redo = undo_redo.UndoRedo(self)
        self._undo_redo.undo_status_changed.connect(drawing_win.set_undo_status)
        self._undo_redo.redo_status_changed.connect(drawing_win.set_redo_status)

        self._drawing_window: drawing_window.DrawingWindow = drawing_win
        self._elements: typing.List[graphics.GraphicsObject] = elements
        self._selected_elements: typing.List[graphics.GraphicsObject] = []
        self._selection_RectF: typing.Optional[core.QRectF] = None
        self._tablet_in_use: bool = False
        self._previous_point: typing.Optional[core.QPointF] = None
        self._first_point: typing.Optional[core.QPointF] = None
        self._alternate_function: bool = False
        self._mode_of_ongoing_stroke: int = Mode.NONE
        self._rubber_band: typing.Optional[widgets.QRubberBand] = None
        self._text_editor: text_editor.TextEditor = text_editor.TextEditor(self)
        self._current_stroke: typing.Optional[graphics.PolylineObject] = None

        self._widget_on_selection = widgets.QWidget(self)
        self._widget_on_selection.hide()
        layout_on_selection = widgets.QHBoxLayout()
        self._widget_on_selection.setLayout(layout_on_selection)
        self._transform_start = core.QPoint()

        button_move = drag_button.DragButton(self, self._move_function)
        button_move.setToolTip("Bewegen")
        button_move.setIcon(gui.QIcon("move.png"))
        button_move.setIconSize(core.QSize(24, 24))
        layout_on_selection.addWidget(button_move)

        button_scale = drag_button.DragButton(self, self._scale_function)
        button_scale.setToolTip("Skalieren")
        button_scale.setIcon(gui.QIcon("scale.png"))
        button_scale.setIconSize(core.QSize(24, 24))
        layout_on_selection.addWidget(button_scale)
        
        # TODO: turn into class variables
        self._cursor_drawing = gui.QCursor(gui.QBitmap("cursor_drawing_b.png"), gui.QBitmap("cursor_drawing_m.png"), 0, 0)
        self._cursor_erasing = gui.QCursor(gui.QBitmap("cursor_erasing_b.png"), gui.QBitmap("cursor_erasing_m.png"), 0, 0)
        self._cursor_typing = gui.QCursor(gui.QBitmap("cursor_typing_b.png"), gui.QBitmap("cursor_typing_m.png"), 15, 15)
        self._cursor_selecting = gui.QCursor(gui.QBitmap("cursor_selecting_b.png"), gui.QBitmap("cursor_selecting_m.png"), 15, 15)

    def set_cursor(self, mode: Mode) -> None:
        if mode == Mode.DRAWING:
            self.setCursor(self._cursor_drawing)
        elif mode == Mode.ERASING:
            self.setCursor(self._cursor_erasing)
        elif mode == Mode.TYPING:
            self.setCursor(self._cursor_typing)
        elif mode == Mode.SELECTING:
            self.setCursor(self._cursor_selecting)

    def undo(self) -> None:
        self._undo_redo.undo()

    def redo(self) -> None:
        self._undo_redo.redo()

    def clear_selection(self) -> None:
        self._selected_elements.clear()
        self.set_selection_tools_visible(False)
        self.update()

    def _compute_selection_RectF(self) -> typing.Optional[core.QRectF]:
        if len(self._selected_elements) > 0:
            return graphics.get_bounding_box_of_list(self._selected_elements)
        else:
            return None

    def delete_selected_or_all(self) -> None:
        # Note: We must not replace the list self._elements by a new one
        #       because this list is being shared.
        if len(self._selected_elements) == 0:
            reply = widgets.QMessageBox.question(self, "Sicherheitsabfrage", "Alles löschen?", widgets.QMessageBox.Yes | widgets.QMessageBox.Cancel)
            if reply == widgets.QMessageBox.Yes:
                elements_copy = self._elements.copy()
                def undo_function() -> None:
                    self._elements.extend(elements_copy)
                    self.update()
                def redo_function() -> None:
                    self._elements.clear()
                    self.update()
                undo_redo.Command(self._undo_redo, undo_function, redo_function, True)
        else:
            elements_index_copy: typing.List[typing.Tuple[int, graphics.GraphicsObject]] = []
            for i, el in enumerate(self._elements):
                if el in self._selected_elements:
                    elements_index_copy.append((i, el))
            def undo_function() -> None:
                for i, el in elements_index_copy:
                    self._elements.insert(i, el)
                self.update()
            def redo_function() -> None:
                for i, _ in reversed(elements_index_copy):
                    del self._elements[i]
                self.update()
            undo_redo.Command(self._undo_redo, undo_function, redo_function, True)
        self.clear_selection()

    def _place_widget_on_selection(self, x: float, y: float) -> None:
        w = self._widget_on_selection.width()
        h = self._widget_on_selection.height()
        self._widget_on_selection.move(int(x - 0.5 * w), int(y - 0.5 * h))

    def _move_function(self, new_position: typing.Optional[core.QPoint], \
        old_position: typing.Optional[core.QPoint]) -> None:
        if new_position is not None and old_position is None:
            self._transform_start = new_position
        elif new_position is None and old_position is not None:
            delta = typing.cast(core.QPoint, old_position - self._transform_start)
            selected_elements_copy = self._selected_elements.copy()
            def undo_function() -> None:
                for se in selected_elements_copy:
                    se.translate(-delta.x(), -delta.y())
                self.update()
            def redo_function() -> None:
                for se in selected_elements_copy:
                    se.translate(delta.x(), delta.y())
                self.update()
            undo_redo.Command(self._undo_redo, undo_function, redo_function, False)
        elif new_position is not None and old_position is not None:
            delta = typing.cast(core.QPoint, new_position - old_position)
            for se in self._selected_elements:
                se.translate(delta.x(), delta.y())
            self._selection_RectF.translate(delta)
            center = self._selection_RectF.center()
            self._place_widget_on_selection(center.x(), center.y())
            self.update()

    def _scale_function(self, new_position: typing.Optional[core.QPoint], \
        old_position: typing.Optional[core.QPoint]) -> None:
        if new_position is not None and old_position is None:
            self._transform_start = new_position
        elif new_position is None and old_position is not None:
            delta = typing.cast(core.QPoint, old_position - self._transform_start)
            selected_elements_copy = self._selected_elements.copy()
            # danger: code duplicated below
            a = delta.x() - delta.y() # positive for motion left & up
            factor = 2 ** (0.003 * a)
            center = self._selection_RectF.center()
            premultiplied_center: core.QPointF = center * (1.0 - factor)
            preX = premultiplied_center.x()
            preY = premultiplied_center.y()
            factor_inv = 1.0 / factor
            premultiplied_center_inv: core.QPointF = center * (1.0 - factor_inv)
            preX_inv = premultiplied_center_inv.x()
            preY_inv = premultiplied_center_inv.y()
            def undo_function() -> None:
                for se in selected_elements_copy:
                    se.scale(preX_inv, preY_inv, factor_inv)
                self.update()
            def redo_function() -> None:
                for se in selected_elements_copy:
                    se.scale(preX, preY, factor)
                self.update()
            undo_redo.Command(self._undo_redo, undo_function, redo_function, False)
        elif new_position is not None and old_position is not None:
            delta = typing.cast(core.QPoint, new_position - old_position)
            # danger: code duplicated above
            a = delta.x() - delta.y() # positive for motion left & up
            factor = 2 ** (0.003 * a)
            center = self._selection_RectF.center()
            premultiplied_center: core.QPointF = center * (1.0 - factor)
            preX = premultiplied_center.x()
            preY = premultiplied_center.y()
            for se in self._selected_elements:
                se.scale(preX, preY, factor)
            self.update()

    def set_selection_tools_visible(self, state: bool) -> None:
        self._widget_on_selection.setVisible(state)

    def add_image(self, image: gui.QImage) -> None:
        w = self.width()
        h = self.height()
        w1 = image.width()
        h1 = image.height()
        targetW = w
        targetH = h
        if w * h1 > w1 * h:
            targetW = targetH / h1 * w1
        else:
            targetH = targetW / w1 * h1
        img = graphics.ImageObject()
        img.set_image(image)
        img.set_bounding_box(core.QRectF(0.0, 0.0, targetW, targetH))

        def undo_function() -> None:
            self._elements.remove(img)
            self.update()
        def redo_function() -> None:
            self._elements.append(img)
            self.update()
        undo_redo.Command(self._undo_redo, undo_function, redo_function, True)

        self._drawing_window.set_dirty()

    def update_stroke_color(self, color: gui.QColor) -> None:
        if len(self._selected_elements) == 0:
            return

        elements_to_process = [el for el in self._selected_elements if isinstance(el, graphics.PolylineObject)]
        original_colors: typing.List[gui.QColor] = []
        def undo_function() -> None:
            for i, el in enumerate(elements_to_process):
                el.set_color(original_colors[i])
            self.update()
        def redo_function() -> None:
            for el in elements_to_process:
                original_colors.append(el.get_color())
                el.set_color(color)
            self.update()
        undo_redo.Command(self._undo_redo, undo_function, redo_function, True)

        self._drawing_window.set_dirty()
        self.update()

    def update_stroke_thickness(self, thickness: float) -> None:
        if len(self._selected_elements) == 0:
            return
        
        elements_to_process = [el for el in self._selected_elements if isinstance(el, graphics.PolylineObject)]
        original_stroke_thicknesses: typing.List[float] = []
        def undo_function() -> None:
            for i, el in enumerate(elements_to_process):
                el.set_stroke_thickness(original_stroke_thicknesses[i])
            self.update()
        def redo_function() -> None:
            for el in elements_to_process:
                original_stroke_thicknesses.append(el.get_stroke_thickness())
                el.set_stroke_thickness(thickness)
            self.update()
        undo_redo.Command(self._undo_redo, undo_function, redo_function, True)

        self._drawing_window.set_dirty()
        self.update()

    def update_font_size(self, font_size: int) -> None:
        text_editor_text = self._text_editor.get_text_element()
        if len(self._selected_elements) == 0 and text_editor_text is None:
            return

        if text_editor_text is not None:
            text_editor_text_1 = text_editor_text  # for closure
            original_font_size = text_editor_text.get_font_size()
            def undo_function() -> None:
                text_editor_text_1.set_font_size(original_font_size)
                self._text_editor.update_font_size(original_font_size)
                self.update()
            def redo_function() -> None:
                text_editor_text_1.set_font_size(font_size)
                self._text_editor.update_font_size(font_size)
                self.update()
            undo_redo.Command(self._undo_redo, undo_function, redo_function, True)
        else:
            elements_to_process = [el for el in self._selected_elements if isinstance(el, graphics.TextObject)]
            original_font_sizes: typing.List[float] = []
            for el in elements_to_process:
                original_font_sizes.append(el.get_font_size())
            def undo_function() -> None:
                for i, el in enumerate(elements_to_process):
                    el.set_font_size(original_font_sizes[i])
                self.update()
            def redo_function() -> None:
                for el in elements_to_process:
                    el.set_font_size(font_size)
                self.update()
            undo_redo.Command(self._undo_redo, undo_function, redo_function, True)

        self._drawing_window.set_dirty()
        self._text_editor.update_font_size(font_size)
        self.update()

    def move_text_editor(self, delta: core.QPoint) -> None:
        self._text_editor.move(self._text_editor.pos() + delta)

    def paintEvent(self, event: gui.QPaintEvent) -> None:
        qp = gui.QPainter()
        qp.begin(self)
        qp.setRenderHints(typing.cast(gui.QPainter.RenderHints, gui.QPainter.Antialiasing | gui.QPainter.SmoothPixmapTransform))
        for el in self._elements:
            if el == self._text_editor.get_text_element():
                continue  # don't show original text below editor
            el.draw(qp, el in self._selected_elements)
        qp.end()

    def clean_ui(self) -> None:
        # to handle TextEditor as popup
        if self._text_editor.isVisible():
            self._text_editor.hide()
            self.setFocus()
            self._text_editor.set_text_element(None)
            self.update()

    def _start_stroke(self, x: float, y: float, alternate_function: bool) -> None:
        self.clean_ui()

        if self._first_point is not None:
            # something bad happened
            self._end_stroke(x, y)
            return

        self._first_point = core.QPointF(x, y)
        self._alternate_function = alternate_function

        self._previous_point = self._first_point
        self._mode_of_ongoing_stroke = self._drawing_window.get_mode()
        if self._mode_of_ongoing_stroke == Mode.DRAWING and not self._alternate_function:
            stroke = graphics.PolylineObject()  # local variable needed for closure for undo/redo
            self._current_stroke = stroke
            stroke.set_color(gui.QColor(*preferences.get("color")))
            stroke.set_stroke_thickness(preferences.get("stroke_thickness"))
            stroke.append_point(core.QPointF(x, y))

            def undo_function() -> None:
                self._elements.remove(stroke)  # looks safer than: del self._element[-1]
                self.update()
            def redo_function() -> None:            
                self._elements.append(stroke)
                self.update()
            undo_redo.Command(self._undo_redo, undo_function, redo_function, True)

        elif self._mode_of_ongoing_stroke == Mode.ERASING \
            or self._alternate_function and self._mode_of_ongoing_stroke == Mode.DRAWING:
            pass
        elif self._mode_of_ongoing_stroke == Mode.TYPING:
            self._rubber_band = widgets.QRubberBand(widgets.QRubberBand.Rectangle, self)
            self._rubber_band.setGeometry(int(x), int(y), 0, 0)
            self._rubber_band.show()
        elif self._mode_of_ongoing_stroke == Mode.SELECTING:
            self._rubber_band = widgets.QRubberBand(widgets.QRubberBand.Rectangle, self)
            self._rubber_band.setGeometry(int(x), int(y), 0, 0)
            self._rubber_band.show()

    def _continue_stroke(self, x: float, y: float) -> None:
        if self._first_point is None \
            or self._previous_point is None \
            or self._mode_of_ongoing_stroke == Mode.NONE:
            # something bad happened
            self._end_stroke(x, y)
            return

        if self._mode_of_ongoing_stroke == Mode.DRAWING and not self._alternate_function:
            if self._current_stroke is not None:
                self._current_stroke.append_point(core.QPointF(x, y))
            self.update()
        elif self._mode_of_ongoing_stroke == Mode.ERASING \
            or self._alternate_function and self._mode_of_ongoing_stroke == Mode.DRAWING:
            to_erase: typing.List[typing.Tuple[int, graphics.PolylineObject]] = \
                [(i, el) for i, el in enumerate(self._elements) if \
                    isinstance(el, graphics.PolylineObject) \
                    and el.intersects_line(core.QPointF(x, y), self._previous_point)]
            
            if len(to_erase) > 0:
                def undo_function() -> None:
                    for i, el in to_erase:
                        self._elements.insert(i, el)
                    self.update()
                def redo_function() -> None:
                    for _, el in to_erase:
                        self._elements.remove(el)  # looks safer than: del self._element[i] ((which would require "reversed"))
                    self.update()
                undo_redo.Command(self._undo_redo, undo_function, redo_function, True)

        elif self._mode_of_ongoing_stroke == Mode.TYPING:
            pass
        elif self._mode_of_ongoing_stroke == Mode.SELECTING:
            pass
        if self._rubber_band is not None:
            left = min(x, self._first_point.x())
            top = min(y, self._first_point.y())
            width = abs(x - self._first_point.x())
            height = abs(y - self._first_point.y())
            self._rubber_band.setGeometry(int(left), int(top), int(width), int(height))
        self._previous_point = core.QPointF(x, y)

    def _end_stroke(self, x: float, y: float) -> None:
        if self._first_point is not None \
            and self._previous_point is not None:
            if self._mode_of_ongoing_stroke == Mode.DRAWING and not self._alternate_function:
                if self._current_stroke is not None:
                    if preferences.get("smooth_drawing"):
                        self._current_stroke.clean_up()
                    self.update()
            elif self._mode_of_ongoing_stroke == Mode.ERASING \
                or self._alternate_function and self._mode_of_ongoing_stroke == Mode.DRAWING:
                pass
            elif self._mode_of_ongoing_stroke == Mode.TYPING:
                left = min(x, self._first_point.x())
                top = min(y, self._first_point.y())
                width = abs(x - self._first_point.x())
                height = abs(y - self._first_point.y())
                text_element: typing.Optional[graphics.TextObject] = None
                if width < 5 and height < 5:
                    # get the topmost
                    for t in reversed([el for el in self._elements if isinstance(el, graphics.TextObject)]):
                        if t.get_bounding_box().contains(self._first_point):
                            text_element = t
                            break
                    if text_element is None:  # new text element should not be tiny
                        width = 100
                        height = 100
                if text_element is None:
                    text_element_1 = graphics.TextObject()  # variable required for capture for undo/redo
                    text_element = text_element_1
                    text_element.set_font_size(preferences.get("font_size"))

                    # must be in the window and not be too tiny
                    m = self._text_editor.lower_size_limit()
                    f = self._text_editor.frameWidth()
                    left = max(f, min(self.width() - m, left))
                    top = max(f, min(self.height() - m, top))
                    right = left + width
                    right = min(self.width() - f, max(left + m, right))
                    width = right - left
                    bottom = top + height
                    bottom = min(self.height() - f, max(top + m, bottom))
                    height = bottom - top

                    text_element.set_bounding_box(core.QRectF(left, top, width, height))
                    
                    def undo_function() -> None:
                        self._elements.remove(text_element_1)  # looks safer than: del self._element[-1]
                        self.update()
                    def redo_function() -> None:
                        self._elements.append(text_element_1)
                        self.update()
                    undo_redo.Command(self._undo_redo, undo_function, redo_function, True)

                self._text_editor.set_text_element(text_element)
                self.update()  # to remove the text behind the text editor      
                self._text_editor.open()
            elif self._mode_of_ongoing_stroke == Mode.SELECTING:
                left = min(x, self._first_point.x())
                top = min(y, self._first_point.y())
                width = max(1.0, abs(x - self._first_point.x()))  # max(1.0, ...) to handle clicking instead of dragging
                height = max(1.0, abs(y - self._first_point.y()))
                selection_rect = core.QRectF(left, top, width, height)
                new_selected_elements = [el for el in self._elements if el.intersects_rect(selection_rect)]

                modif = widgets.QApplication.keyboardModifiers()
                if modif & core.Qt.ShiftModifier:
                    self._selected_elements.extend([el for el in new_selected_elements if el not in self._selected_elements])
                elif modif & core.Qt.ControlModifier:
                    self._selected_elements = [el for el in self._selected_elements if el not in new_selected_elements]
                else:
                    self._selected_elements = new_selected_elements

                self._selection_RectF = self._compute_selection_RectF()
                if self._selection_RectF is None:
                    self.set_selection_tools_visible(False)
                else:
                    center = self._selection_RectF.center()
                    self._place_widget_on_selection(center.x(), center.y())
                    self.set_selection_tools_visible(True)
                self.update()
        self._mode_of_ongoing_stroke = Mode.NONE
        self._previous_point = None
        self._first_point = None
        self._alternate_function = False
        self._tablet_in_use = False
        self._current_stroke = None
        if self._rubber_band is not None:
            self._rubber_band.hide()
        self._drawing_window.set_dirty()

    def tabletEvent(self, event: gui.QTabletEvent) -> None:
        if self._text_editor.isVisible() and self._text_editor.geometry().contains(event.pos()):
            event.ignore()
            return 
        event.accept()
        et = event.type()
        if et == core.QEvent.TabletPress:
            self._tablet_in_use = True
            p = event.posF()
            self._start_stroke(p.x(), p.y(), \
                event.pointerType() == gui.QTabletEvent.Eraser \
                or event.buttons() == core.Qt.RightButton)
        elif et == core.QEvent.TabletMove:
            p = event.posF()
            self._continue_stroke(p.x(), p.y())
        elif et == core.QEvent.TabletRelease:
            p = event.posF()
            self._end_stroke(p.x(), p.y())
            self._tablet_in_use = False

    def mousePressEvent(self, event: gui.QMouseEvent) -> None:
        event.accept()
        if self._tablet_in_use:
            return
        p = event.pos()
        rmb = gui.QGuiApplication.mouseButtons() == core.Qt.RightButton
        self._start_stroke(p.x(), p.y(), rmb)

    def mouseMoveEvent(self, event: gui.QMouseEvent) -> None:
        event.accept()
        if self._tablet_in_use:
            return
        p = event.pos()
        self._continue_stroke(p.x(), p.y())            

    def mouseReleaseEvent(self, event: gui.QMouseEvent) -> None:
        event.accept()
        if self._tablet_in_use:
            return
        p = event.pos()
        self._end_stroke(p.x(), p.y())
