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
import xml.dom.minidom
import uuid
import time


class GraphicsObject():
    def __init__(self) -> None:
        self._bounding_box: core.QRectF = core.QRectF()
        self._uuid: str = "i" + str(uuid.uuid4().int)

    def uuid(self) -> str:
        return self._uuid

    @staticmethod
    def deserialize(element: xml.dom.minidom.Element, document: xml.dom.minidom.Document, files: typing.Dict[str, core.QByteArray]) -> typing.Optional[GraphicsObject]:
        options = {
            "text": lambda element, document, file_content: TextObject.deserialize_(element, document),
            "image": lambda element, document, file_content: ImageObject.deserialize_(element, files),
            "polyline": lambda element, document, file_content: PolylineObject.deserialize_(element)
        }
        if element.tagName in options:
            return options[element.tagName](element, document, files)
        else:
            return None

    def serialize(self, document: xml.dom.minidom.Document) -> typing.Optional[typing.Tuple[str, core.QByteArray]]:
        return None

    def clone(self) -> GraphicsObject:
        clone = type(self)()
        clone._bounding_box = core.QRectF(self._bounding_box)
        clone._uuid = self._uuid
        return clone

    def draw(self, painter: gui.QPainter, is_selected: bool) -> None:
        pass

    # overridden in PolylineObject
    def get_bounding_box(self) -> core.QRectF:
        return self._bounding_box

    # overridden in PolylineObject
    def intersects_rect(self, rect: core.QRectF) -> bool:
        return self._bounding_box.intersects(rect)

    def translate(self, dx: float, dy: float) -> None:
        self._bounding_box.translate(core.QPointF(dx, dy))

    def scale(self, dx: float, dy: float, s: float) -> None:
        b = self._bounding_box
        self._bounding_box = core.QRectF(b.left() * s + dx, b.top() * s + dy, b.width() * s, b.height() * s)

    def is_empty(self) -> bool:
        return False

def clone_list(elements: typing.List[GraphicsObject]) -> typing.List[GraphicsObject]:
    result: typing.List[GraphicsObject] = []
    for element in elements:
        result.append(element.clone())
    return result

def get_bounding_box_of_list(elements: typing.List[GraphicsObject]) -> core.QRectF:
    r: core.QRectF = core.QRectF()
    for elem in elements:
        r = r.united(elem.get_bounding_box())
    return r

def serialize(elements: typing.List[GraphicsObject]) -> typing.Tuple[str, typing.Dict[str, core.QByteArray]]:
    document = xml.dom.minidom.parseString('<?xml version="1.0" encoding="utf-8" standalone="yes"?><svg version="1.1" xmlns="http://www.w3.org/2000/svg"><defs></defs></svg>')

    files: typing.Dict[str, core.QByteArray] = {}
    for el in elements:
        ser = el.serialize(document)
        if ser is not None:
            name, content = ser
            files[name] = content

    return (document.toxml(), files)

def deserialize(document_text: str, files: typing.Dict[str, core.QByteArray]) -> typing.List[GraphicsObject]:
    # TODO: sanitize document_text to protect against XML vulnerabilities
    elements: typing.List[GraphicsObject] = []
    document = xml.dom.minidom.parseString(document_text)
    
    svgs = document.getElementsByTagName("svg")
    if len(svgs) != 1:
        pass  # TODO: error
    
    for node in svgs[0].childNodes:
        if node.nodeType == xml.dom.minidom.Node.ELEMENT_NODE:
            element: typing.Optional[GraphicsObject] = GraphicsObject.deserialize(node, document, files)
            if element is not None:
                elements.append(element)

    return elements

def parse_css(css: str) -> typing.Dict[str, str]:
    # TODO: make this robust
    result = {}
    for part in css.split(";"):
        entry = part.partition(":")
        if entry[1] == ":":
            result[entry[0].strip()] = entry[2].strip() 
    return result

class TextObject(GraphicsObject):
    _text_pen: typing.ClassVar[gui.QPen] = gui.QPen()
    _selection_pen: typing.ClassVar[gui.QPen] = gui.QPen()
    _selection_pen.setWidth(1)
    _selection_pen.setColor(gui.QColor(255, 0, 0))
    _text_options: typing.ClassVar[gui.QTextOption] = gui.QTextOption()
    _text_options.setTabStopDistance(80)
    _text_options.setWrapMode(gui.QTextOption.WrapAtWordBoundaryOrAnywhere)

    def __init__(self) -> None:
        super().__init__()
        self._text: str = ""
        self._font_size: float = 10.0
        self._bounding_box: core.QRectF = core.QRectF(0, 0, 100, 100)
    
    @staticmethod
    def deserialize_(element: xml.dom.minidom.Element, document: xml.dom.minidom.Document) -> typing.Optional[TextObject]:
        obj = TextObject()
        
        if not element.hasAttribute("id"):
            return None
        obj._uuid = element.getAttribute("id")
        
        children = element.childNodes
        if len(children) == 0 or not children[0].nodeType == xml.dom.minidom.Node.TEXT_NODE:
            return None
        obj._text = children[0].nodeValue

        if not element.hasAttribute("style"):
            return None
        styles = parse_css(element.getAttribute("style"))
        
        if not "font-size" in styles:
            return None
        try:
            obj._font_size = float(styles["font-size"])
        except:
            return None

        if not "shape-inside" in styles:
            return None
        rect = styles["shape-inside"]
        if not rect.startswith("url(#") or not rect.endswith(")") or len(rect) < 10:
            return None
        uuid = rect[5: -1]
        svgs = document.getElementsByTagName("svg")
        if len(svgs) != 1:
            return None
        defss = svgs[0].getElementsByTagName("defs")
        if len(defss) != 1:
            return None
        defs_children = defss[0].childNodes
        el = None
        for dc in defs_children:
            if dc.nodeType == xml.dom.minidom.Node.ELEMENT_NODE and dc.tagName == "rect":        
                if dc.hasAttribute("id") and dc.getAttribute("id") == uuid:
                    el = dc
                    break
        if el is None:
            return None
        if not el.hasAttribute("x") or not el.hasAttribute("y") or not el.hasAttribute("width") or not el.hasAttribute("height"):
            return None
        try:
            obj._bounding_box = core.QRectF(
                float(el.getAttribute("x")),
                float(el.getAttribute("y")),
                float(el.getAttribute("width")),
                float(el.getAttribute("height")))
        except:
            return None

        return obj

    def serialize(self, document: xml.dom.minidom.Document) -> typing.Optional[typing.Tuple[str, core.QByteArray]]:
        svg = document.getElementsByTagName("svg")[0]

        defs = svg.getElementsByTagName("defs")[0]
        rect = document.createElement("rect")
        defs.appendChild(rect)
        rect.setAttribute("id", "r" + self.uuid())
        rect.setAttribute("x", str(round(self._bounding_box.left(), 1)))
        rect.setAttribute("y", str(round(self._bounding_box.top(), 1)))
        rect.setAttribute("width", str(round(self._bounding_box.width(), 1)))
        rect.setAttribute("height", str(round(self._bounding_box.height(), 1)))

        element = document.createElement("text")
        svg.appendChild(element)
        element.setAttribute("id", self.uuid())
        element.setAttributeNS("xml", "space", "preserve")
        element.setAttribute("x", str(round(self._bounding_box.left(), 1)))
        element.setAttribute("y", str(round(self._bounding_box.top(), 2)))
        element.setAttribute("style", "font-size:" + str(round(self._font_size, 1))
            + ";shape-inside:url(#" + "r" + self.uuid() + ");")
        element.appendChild(document.createTextNode(self._text))

        return None

    def clone(self) -> GraphicsObject:
        clone = typing.cast(TextObject, super().clone())
        clone._font_size = self._font_size
        clone._text = self._text
        return clone

    def draw(self, painter: gui.QPainter, is_selected: bool) -> None:
        font = painter.font()
        font.setPointSizeF(self._font_size)
        painter.setFont(font)
        painter.setPen(TextObject._text_pen)
        painter.drawText(self._bounding_box, self._text, TextObject._text_options)
        if is_selected:
            painter.setPen(TextObject._selection_pen)
            painter.drawRect(self._bounding_box)

    def set_text(self, text: str) -> None:
        self._text = text

    def get_text(self) -> str:
        return self._text

    def set_color(self, color: gui.QColor) -> None:
        self._color = color

    def set_font_size(self, font_size: float) -> None:
        self._font_size = font_size

    def get_font_size(self) -> float:
        return self._font_size

    def set_bounding_box(self, box: core.QRectF) -> None:
        self._bounding_box = box

    def scale(self, dx: float, dy: float, s: float) -> None:
        self._font_size *= s
        super().scale(dx, dy, s)

    def is_empty(self) -> bool:
        return self._text.strip() == ""


class ImageObject(GraphicsObject):
    _selection_pen: typing.ClassVar[gui.QPen] = gui.QPen()
    _selection_pen.setWidth(1)
    _selection_pen.setColor(gui.QColor(255, 0, 0))

    def __init__(self) -> None:
        super().__init__()
        self._image: typing.Optional[gui.QImage] = None

    @staticmethod
    def deserialize_(element: xml.dom.minidom.Element, files: typing.Dict[str, core.QByteArray]) -> typing.Optional[ImageObject]:
        obj = ImageObject()
        if not element.hasAttribute("id"):
            return None
        obj._uuid = element.getAttribute("id")        

        if not element.hasAttribute("x") or not element.hasAttribute("y") or not element.hasAttribute("width") or not element.hasAttribute("height"):
            return None
        try:
            obj._bounding_box = core.QRectF(
                float(element.getAttribute("x")),
                float(element.getAttribute("y")),
                float(element.getAttribute("width")),
                float(element.getAttribute("height")))
        except:
            return None

        if not element.hasAttribute("href"):
            return None
        filename = element.getAttribute("href")
        if filename not in files:
            return None
        try:
            obj._image = gui.QImage.fromData(files[filename])
        except:
            return None

        return obj

    def serialize(self, document: xml.dom.minidom.Document) -> typing.Optional[typing.Tuple[str, core.QByteArray]]:
        svg = document.getElementsByTagName("svg")[0]

        filename = self.uuid() + ".jpg"

        element = document.createElement("image")
        svg.appendChild(element)
        element.setAttribute("id", self.uuid())
        element.setAttribute("x", str(round(self._bounding_box.left(), 1)))
        element.setAttribute("y", str(round(self._bounding_box.top(), 1)))
        element.setAttribute("width", str(round(self._bounding_box.width(), 1)))
        element.setAttribute("height", str(round(self._bounding_box.height(), 1)))
        element.setAttribute("href", filename)

        data = core.QByteArray()
        buf = core.QBuffer(data)
        self._image.save(buf, "JPG")

        return (filename, data)

    def clone(self) -> GraphicsObject:
        clone = typing.cast(ImageObject, super().clone())
        clone._image = self._image
        return clone

    def set_image(self, image: gui.QImage) -> None:
        self._image = image

    def set_bounding_box(self, box: core.QRectF) -> None:
        self._bounding_box = box
        
    def draw(self, painter: gui.QPainter, is_selected: bool) -> None:
        if self._image is not None:
            painter.drawImage(self._bounding_box, self._image)
            if is_selected:
                painter.setPen(ImageObject._selection_pen)
                painter.drawRect(self._bounding_box)

    def is_empty(self) -> bool:
        return self._image is None 


class PolylineObject(GraphicsObject):
    _stroke_pen: typing.ClassVar[gui.QPen]  = gui.QPen()
    _stroke_pen.setJoinStyle(core.Qt.RoundJoin)
    _stroke_pen.setCapStyle(core.Qt.RoundCap)
    _selection_pen: typing.ClassVar[gui.QPen] = gui.QPen()
    _selection_pen.setJoinStyle(core.Qt.RoundJoin)
    _selection_pen.setCapStyle(core.Qt.RoundCap)

    def __init__(self) -> None:
        super().__init__()
        self._points: typing.List[core.QPointF] = []
        self._color: gui.QColor = gui.QColor(0, 0, 0)
        self._stroke_thickness: float = 1.0
        self._paint_with_subdivision: bool = False

    @staticmethod
    def deserialize_(element: xml.dom.minidom.Element) -> typing.Optional[PolylineObject]:
        obj = PolylineObject()
        if not element.hasAttribute("id"):
            return None
        obj._uuid = element.getAttribute("id")  

        if not element.hasAttribute("stroke"):
            return None
        stroke = element.getAttribute("stroke")
        if not stroke.startswith("rgb(") or not stroke.endswith(")"):
            return None
        cols = stroke[4:-1].split(",")
        if len(cols) != 3:
            return None
        try:
            obj._color = gui.QColor(int(cols[0]), int(cols[1]), int(cols[2]))
        except:
            return None

        if not element.hasAttribute("stroke-width"):
            return None
        try:
            obj._stroke_thickness = float(element.getAttribute("stroke-width"))
        except:
            return None

        if not element.hasAttribute("points"):
            return None
        ps = element.getAttribute("points").split(" ")
        try:
            for p in ps:
                part = p.partition(",")
                if part[1] != ",":
                    return None
                obj._points.append(core.QPointF(float(part[0]), float(part[2])))
        except:
            return None
        if len(obj._points) < 2:
            return None
        minX = min([p.x() for p in obj._points])
        maxX = max([p.x() for p in obj._points])
        minY = min([p.y() for p in obj._points])
        maxY = max([p.y() for p in obj._points])
        obj._bounding_box = core.QRectF(minX, minY, maxX - minX, maxY - minY)

        if not element.hasAttribute("paint_with_subdivision"):
            return None
        obj._paint_with_subdivision = (element.getAttribute("paint_with_subdivision") == "True")

        return obj

    def serialize(self, document: xml.dom.minidom.Document) -> typing.Optional[typing.Tuple[str, core.QByteArray]]:
        svg = document.getElementsByTagName("svg")[0]

        element = document.createElement("polyline")
        svg.appendChild(element)
        element.setAttribute("id", self.uuid())
        element.setAttribute("stroke", "rgb(" + str(self._color.red())
            + "," + str(self._color.green())
            + "," + str(self._color.blue()) + ")")
        element.setAttribute("stroke-width", str(round(self._stroke_thickness, 1)))
        element.setAttribute("stroke-linecap", "round")
        element.setAttribute("fill", "none")
        element.setAttribute("stroke-linejoin", "round")

        element.setAttribute("points", " ".join([
            str(round(p.x(), 1)) + ","
            + str(round(p.y(), 1))
            for p in self._points]))

        # not SVG
        element.setAttribute("paint_with_subdivision", str(self._paint_with_subdivision))

        return None

    def clone(self) -> GraphicsObject:
        clone = typing.cast(PolylineObject, super().clone())
        clone._points = []
        for p in self._points:
            clone._points.append(core.QPointF(p))
        clone._color = self._color
        clone._stroke_thickness = self._stroke_thickness
        clone._paint_with_subdivision = self._paint_with_subdivision
        return clone

    def get_bounding_box(self) -> core.QRectF:
        d = self._stroke_thickness / 2.0
        return self._bounding_box.adjusted(-d, -d, d, d)

    def intersects_rect(self, rect: core.QRectF) -> bool:
        #TODO: apply subdivision if corresponding flag is set

        d = self._stroke_thickness / 2.0
        rect = rect.adjusted(-d, -d, d, d)
        if not self._bounding_box.intersects(rect):
            return False

        p1 = self._points[0]
        if rect.contains(p1):
            return True
  
        for i in range(len(self._points) - 1):
            p2 = self._points[i + 1]
            if rect.contains(p2):
                return True

            x1 = p1.x()
            y1 = p1.y()
            x2 = p2.x()
            y2 = p2.y()
            minX = min(x1, x2)
            maxX = max(x1, x2)
            minY = min(y1, y2)
            maxY = max(y1, y2)
            r = core.QRectF(minX, minY, maxX - minX, maxY - minY)
            if r.intersects(rect):
                # Now we know: p1 and p2 are on the outside of rect
                # and rect is contained in the rect spanned by p1 and p2.

                dx = x2 - x1
                dy = y2 - y1
                # Equation for the line through p1 and p2:
                # n.(x - x1) = 0, where n = (dy, -dx)
                # Does rect possess vertices on either side of this line?
                s1 = (dy * (rect.left() - x1) - dx * (rect.top() - y1) > 0)
                s2 = (dy * (rect.right() - x1) - dx * (rect.top() - y1) > 0)
                if s1 != s2:
                    return True
                s2 = (dy * (rect.left() - x1) - dx * (rect.bottom() - y1) > 0)
                if s1 != s2:
                    return True
                s2 = (dy * (rect.right() - x1) - dx * (rect.bottom() - y1) > 0)
                if s1 != s2:
                    return True

            p1 = p2

        return False

    def draw(self, painter: gui.QPainter, is_selected: bool) -> None:
        points_to_draw = self._points

        if self._paint_with_subdivision:
            # Dubuc-Delaurries 4-point interpolatory subdivision scheme
            w1 = - 1.0 / 16.0
            w2 = 0.5 - w1
            for r in range(3):  # do this many rounds of subdivision
                new_points: typing.List[core.QPointF] = []
                n = len(points_to_draw) - 1
                for i in range(n):
                    new_points.append(points_to_draw[i])
                    a = points_to_draw[max(i - 1, 0)]
                    b = points_to_draw[i]
                    c = points_to_draw[min(i + 1, n)]
                    d = points_to_draw[min(i + 2, n)]
                    new_points.append(w1 * (a + d) + w2 * (b + c))
                new_points.append(points_to_draw[-1])
                points_to_draw = new_points

        polygon = gui.QPolygonF(points_to_draw)
        if is_selected:
            col = gui.QColor(255, 0, 0)
            if self._color.red() > 150 and self._color.green() < 100 and self._color.blue() < 150:
                col = gui.QColor(0, 200, 200)
            PolylineObject._selection_pen.setColor(col)
            PolylineObject._selection_pen.setWidthF(self._stroke_thickness + 1.0)
            painter.setPen(PolylineObject._selection_pen)
            painter.drawPolyline(polygon)
        PolylineObject._stroke_pen.setColor(self._color)
        PolylineObject._stroke_pen.setWidthF(self._stroke_thickness)
        painter.setPen(PolylineObject._stroke_pen)
        painter.drawPolyline(polygon)

    def append_point(self, point: core.QPointF) -> None:
        self._points.append(point)
        if len(self._points) == 1:
            self._bounding_box = core.QRectF(point, point)
        else:
            b = self._bounding_box
            minX = min(b.left(), point.x())
            minY = min(b.top(), point.y())
            maxX = max(b.right(), point.x())
            maxY = max(b.bottom(), point.y())
            self._bounding_box = core.QRectF(minX, minY, maxX - minX, maxY - minY)

    def clean_up(self) -> None:
        threshold_distance_squared = 3.0 ** 2
        which_points_to_use = [False] * len(self._points)
        which_points_to_use[0] = True
        which_points_to_use[-1] = True

        # Douglas–Peucker recursion
        def dp(a: int, b: int) -> None:
            dxba = self._points[b].x() - self._points[a].x()
            dyba = self._points[b].y() - self._points[a].y()
            length_ba_squared = dxba * dxba + dyba * dyba + 1e-10  # never 0
            max_index = -1
            max_distance_squared = -42.0
            for i in range(a, b):
                dxia = self._points[i].x() - self._points[a].x()
                dyia = self._points[i].y() - self._points[a].y()
                length_ia_squared = dxia * dxia + dyia * dyia
                dyia_dot_dxba = dxia * dxba + dyia * dyba
                distance_squared = 0.0
                lam = dyia_dot_dxba / length_ba_squared
                if 0.0 <= lam <= 1.0:
                    distance_squared = length_ia_squared - dyia_dot_dxba ** 2 / length_ba_squared
                elif lam < 0.0:
                    distance_squared = length_ia_squared
                else:  #lam > 1.0
                    distance_squared = length_ia_squared + length_ba_squared - 2.0 * dyia_dot_dxba

                if distance_squared > max_distance_squared:
                    max_distance_squared = distance_squared
                    max_index = i
            if max_distance_squared > threshold_distance_squared:
                which_points_to_use[max_index] = True
                if max_index > a + 1:
                    dp(a, max_index)
                if b > max_index + 1:
                    dp(max_index, b)

        dp(0 , len(self._points) - 1)
        self._points = [p for p, use_it in zip(self._points, which_points_to_use) if use_it] 

        self._paint_with_subdivision = True

    def set_color(self, color: gui.QColor) -> None:
        self._color = color

    def get_color(self) -> gui.QColor:
        return self._color

    def set_stroke_thickness(self, thickness: float) -> None:
        self._stroke_thickness = thickness

    def get_stroke_thickness(self) -> float:
        return self._stroke_thickness

    def is_empty(self) -> bool:
        return len(self._points) < 2

    def translate(self, dx: float, dy: float) -> None:
        p = core.QPointF(dx, dy)
        for i in range(len(self._points)):
            self._points[i] += p
        super().translate(dx, dy)

    def scale(self, dx: float, dy: float, s: float) -> None:
        for i in range(len(self._points)):
            p = self._points[i]
            self._points[i] = core.QPointF(p.x() * s + dx, p.y() * s + dy)
        super().scale(dx, dy, s)

    def intersects_line(self, p1: core.QPointF, p2: core.QPointF) -> bool:
        x3 = p1.x()
        y3 = p1.y()
        x4 = p2.x()
        y4 = p2.y()
        surrounding_rect = core.QRectF(min(x3, x4), min(y3, y4), abs(x4 - x3) + 1.0, abs(y4 - y3) + 1.0)
        # a quick test first
        if not self.get_bounding_box().intersects(surrounding_rect):
            return False

        # line: p1 + lambda * (p2 - p1)
        for i in range(len(self._points) - 1):
            q1 = self._points[i]
            x1 = q1.x()
            y1 = q1.y()
            q2 = self._points[i + 1]
            x2 = q2.x()
            y2 = q2.y()
            # line: q1 + mu * (q2 - q1)
            # intersection:
            #     p1 + lambda * (p2 - p1) == q1 + mu * (q2 - q1)
            # <=> lambda * (p2 - p1) +  mu * (q1 - q2) == q1 - p1
            denom = (x4 - x3) * (y1 - y2) - (y4 - y3) * (x1 - x2)
            if abs(denom) < 1e-20:  # almost parallel
                continue  # lame way to deal with this 
            lam = ((x1 - x3) * (y1 - y2) - (y1 - y3) * (x1 - x2)) / denom
            mu = ((x4 - x3) * (y1 - y3) - (y4 - y3) * (x1 - x3)) / denom
            if 0.0 <= lam <= 1.0 and 0.0 <= mu <= 1.0:
                return True
        return False
            