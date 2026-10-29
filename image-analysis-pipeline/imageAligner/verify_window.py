import pathlib
import sys

import cv2
import numpy as np
from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QImage, QPainter, QPixmap
from PyQt5.QtWidgets import (QGraphicsPixmapItem, QGraphicsScene, QLabel,
                             QMainWindow, QVBoxLayout, QWidget)

import process

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from singlePlantAnalysis.plant_viewer import ClickJumpSlider, ZoomableGraphicsView

# Matches the slider handle width so ticks line up with the slider's travel
_SLIDER_MARGIN = 9


def found_reference(corners, ids, ref_id):
    """Whether the aligner would find its marker in this frame. With no reference ID, any marker counts."""
    if ref_id is None:
        return corners is not None
    return process.select_marker_index(corners, ids, ref_id) is not None


class DetectScanWorker(QThread):
    frame_done = pyqtSignal(int, bool)  # frame index, reference marker found

    def __init__(self, image_paths, cache, ref_id):
        super().__init__()
        self.image_paths = image_paths
        self.cache = cache  # shared with the window; skip frames it already detected
        self.ref_id = ref_id

    def run(self):
        for i, path in enumerate(self.image_paths):
            if self.isInterruptionRequested():
                return
            if i not in self.cache:
                self.cache[i] = process.detect_frame(path)
            corners, ids = self.cache[i]
            self.frame_done.emit(i, found_reference(corners, ids, self.ref_id))


class FailedFrameStrip(QWidget):
    """Thin strip under the slider with a red tick for every frame with no marker."""

    def __init__(self, n, parent=None):
        super().__init__(parent)
        self.n = n
        self.failed = set()
        self.setFixedHeight(10)

    def add_failed(self, index):
        self.failed.add(index)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(QColor(220, 40, 40))
        span = max(self.width() - 2 * _SLIDER_MARGIN, 1)
        for i in self.failed:
            frac = i / (self.n - 1) if self.n > 1 else 0
            x = int(_SLIDER_MARGIN + frac * span)
            painter.drawLine(x, 0, x, self.height())


class VerifyWindow(QMainWindow):
    def __init__(self, folder_path, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.image_paths = process.get_input_folder(folder_path)
        self.n = len(self.image_paths)
        self.cache = {}  # frame index -> (corners, ids); (None, None) means no marker
        self.idx = 0
        self.fitted = False

        self.setWindowTitle(f"Verify ArUco Detection - {pathlib.Path(folder_path).name}")
        self.resize(1000, 800)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.scene = QGraphicsScene()
        self.view = ZoomableGraphicsView()
        self.view.setScene(self.scene)
        self.pixmap_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmap_item)
        layout.addWidget(self.view, 1)

        self.lbl_info = QLabel()
        self.lbl_info.setAlignment(Qt.AlignCenter)
        self.lbl_info.setStyleSheet("font-size: 13pt; font-weight: bold;")
        layout.addWidget(self.lbl_info)

        self.slider = ClickJumpSlider(Qt.Horizontal)
        self.slider.setRange(0, max(self.n - 1, 0))
        self.slider.valueChanged.connect(self.set_frame)
        layout.addWidget(self.slider)

        self.strip = FailedFrameStrip(self.n)
        layout.addWidget(self.strip)

        self.lbl_scan = QLabel()
        self.lbl_scan.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_scan)

        # Same rule as the aligner: the largest marker in frame 0 is the reference
        self.ref_id = None
        if self.n:
            self.cache[0] = process.detect_frame(self.image_paths[0])
            if self.cache[0][0] is not None:
                self.ref_id = process.pick_reference_id(*self.cache[0])
            else:
                self.strip.add_failed(0)

        self.show_frame()

        self.worker = DetectScanWorker(self.image_paths, self.cache, self.ref_id)
        self.worker.frame_done.connect(self.on_scan_progress)
        self.worker.start()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.fit_image)

    def fit_image(self):
        if self.pixmap_item.pixmap().isNull():
            return
        self.view.fitInView(self.pixmap_item, Qt.KeepAspectRatio)
        self.fitted = True

    def set_frame(self, val):
        self.idx = val
        self.show_frame()

    def on_scan_progress(self, index, found):
        if not found:
            self.strip.add_failed(index)
        scanned = len(self.cache)
        if scanned >= self.n:
            self.lbl_scan.setText(f"Scan complete: {len(self.strip.failed)} of {self.n} frames with no marker")
        else:
            self.lbl_scan.setText(f"Scanning in background... {scanned}/{self.n}")

    def show_frame(self):
        if self.n == 0:
            self.lbl_info.setText("No images found")
            return

        path = self.image_paths[self.idx]
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is None:
            self.lbl_info.setText(f"Could not read {path.name}")
            return

        # Cached by the background scan, otherwise detect this frame right now
        if self.idx not in self.cache:
            self.cache[self.idx] = process.detect_frame(path)
            if not found_reference(*self.cache[self.idx], self.ref_id):
                self.strip.add_failed(self.idx)
        corners, ids = self.cache[self.idx]
        used_index = process.select_marker_index(corners, ids, self.ref_id)

        self.draw_detections(img, corners, ids, used_index)
        self.pixmap_item.setPixmap(self.to_pixmap(img))
        if not self.fitted:
            self.fit_image()

        head = f"Frame {self.idx + 1}/{self.n}  {path.name}"
        error = ""
        if corners is None:
            error = "No marker detected"
        elif self.ref_id is not None and used_index is None:
            seen = ", ".join(str(i) for i in ids.flatten())
            error = f"Reference marker ID {self.ref_id} not found (saw ID {seen})"

        if error:
            self.lbl_info.setText(f"{head}  -  {error}")
            self.lbl_info.setStyleSheet("font-size: 13pt; font-weight: bold; color: #c62828;")
        else:
            id_list = ", ".join(str(i) for i in ids.flatten())
            self.lbl_info.setText(f"{head}  -  {len(corners)} marker(s), IDs: {id_list}")
            self.lbl_info.setStyleSheet("font-size: 13pt; font-weight: bold;")

    def draw_detections(self, img, corners, ids, used_index):
        """Outline + ID for every marker. The one the aligner uses is thicker, with a centroid dot."""
        if corners is None:
            return
        scale = max(img.shape[1] / 1000, 1.0)
        for k, (c, marker_id) in enumerate(zip(corners, ids.flatten())):
            pts = c.reshape(4, 2)
            used = (k == used_index)
            color = (0, 255, 0) if used else (0, 170, 255)
            thickness = int(round((4 if used else 2) * scale))
            cv2.polylines(img, [pts.astype(np.int32)], True, color, thickness)

            label = f"ID {marker_id}" + (" (used)" if used else "")
            x, y = pts[0]
            cv2.putText(img, label, (int(x), int(y) - int(8 * scale)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6 * scale, color, max(int(2 * scale), 1))

            if used:
                cx, cy = pts.mean(axis=0)
                cv2.circle(img, (int(cx), int(cy)), int(5 * scale), (0, 0, 255), -1)

    @staticmethod
    def to_pixmap(img):
        rgb = np.ascontiguousarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        h, w, _ = rgb.shape
        qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888)
        return QPixmap.fromImage(qimg.copy())

    def closeEvent(self, event):
        self.worker.requestInterruption()
        self.worker.wait()
        super().closeEvent(event)
