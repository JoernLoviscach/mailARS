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
import cv2


class CameraCapture(widgets.QDialog):
    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.setWindowTitle("Kamera")
        self._image: typing.Optional[gui.QImage] = None
        self._cap = cv2.VideoCapture(cv2.CAP_DSHOW)  # cv2.CAP_DSHOW to not get a "terminating async callback" warning
        if self._cap is None or not self._cap.isOpened():
            raise RuntimeError("Kamera fehlt oder ist belegt.")
        self._viewfinder = widgets.QLabel(self)

        self._buttonBox = widgets.QDialogButtonBox(widgets.QDialogButtonBox.Ok | widgets.QDialogButtonBox.Cancel)
        self._buttonBox.accepted.connect(self.accept)
        self._buttonBox.rejected.connect(self.reject)

        self._layout = widgets.QVBoxLayout()
        self._layout.addWidget(self._viewfinder)
        self._layout.addWidget(self._buttonBox)
        self.setLayout(self._layout)

        self._timer = core.QTimer()
        self._timer.timeout.connect(self._tick)
        self._timer.start(500)

    def _tick(self) -> None:
        _, frame = self._cap.read()
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        lab_planes = cv2.split(lab)

        luma = lab_planes[0]
        basis = cv2.medianBlur(luma, 31)
        diff = cv2.subtract(basis, luma)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (101, 101), (50, 50))
        maximum = cv2.dilate(diff, kernel)
        # 10 to limit amplification 
        amplify = cv2.divide(255, cv2.add(maximum, 10))
        
        # 20 to remove noise floor
        lab_planes[0] = cv2.subtract(255, cv2.subtract(cv2.multiply(amplify, diff), 20))
        
        lab = cv2.merge(lab_planes)
        rgb = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
        rgb_flipped = cv2.flip(rgb, 1)

        height, width, _ = rgb.shape
        bytesPerLine = 3 * width
        qImg = gui.QImage(rgb_flipped.data, width, height, bytesPerLine, gui.QImage.Format_RGB888)  
        self._viewfinder.setPixmap(gui.QPixmap(qImg))
        # Hidden side effect: "mirrored" is also necessary to unbind the QImage from the buffer rgb.data
        self._image = gui.QImage(rgb.data, width, height, bytesPerLine, gui.QImage.Format_RGB888).mirrored().mirrored()

    def accept(self) -> None:
        self._timer.stop()
        self._cap.release()
        super().accept()

    def reject(self) -> None:
        self._timer.stop()
        self._cap.release()
        self._image = None
        super().reject()

    def get_image(self) -> typing.Optional[gui.QImage]:
        return self._image
