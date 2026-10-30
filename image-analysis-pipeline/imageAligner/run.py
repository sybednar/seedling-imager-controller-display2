import os
import sys
import cv2
import numpy as np
import process
from pathlib import Path
from verify_window import VerifyWindow

# Suppress Qt and OpenGL warnings
os.environ['QT_LOGGING_RULES'] = '*=false'
os.environ['LIBGL_ALWAYS_INDIRECT'] = '1'

from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                             QWidget, QPushButton, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QProgressBar, QLabel, QFileDialog, QCheckBox,
                             QMessageBox, QTextEdit, QComboBox, QInputDialog, QAbstractItemView)
from PyQt5.QtCore import QTimer, Qt, QThread, pyqtSignal, QDir
from PyQt5.QtGui import QColor

class AlignWorker(QThread):
    progress = pyqtSignal(int, int, str)  # current, total, message
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    warning = pyqtSignal(str)
    
    def __init__(self, folder_path):
        super().__init__()
        self.folder_path = folder_path
    
    def run(self):
        try:
            image_paths = process.get_input_folder(self.folder_path)
            if not image_paths:
                self.error.emit("No images found in folder")
                return
            total = len(image_paths)

            # Detection loop — inlined for per-image progress
            # Every frame is matched to the reference marker (largest marker in frame 0) by ID
            marker_corners = []
            ref_id = None
            for i, image in enumerate(image_paths):
                corners, ids = process.detect_frame(image)
                if i == 0 and corners is not None:
                    ref_id = process.pick_reference_id(corners, ids)
                    self.progress.emit(1, total * 2, f"Reference marker: ID {ref_id}")
                marker = process.select_marker(corners, ids, ref_id)
                if marker is None:
                    self.progress.emit(i + 1, total * 2, f"Warning: reference marker not detected in {image.name}")
                else:
                    self.progress.emit(i + 1, total * 2, f"Detecting: {image.name}")
                marker_corners.append(marker)

            # Check first frame before computing transforms
            if marker_corners[0] is None:
                self.warning.emit("No ArUco marker detected in the first frame — images left unaligned.")
                
                # Create the output directory
                output_folder = Path(image_paths[0]).parent / "aligned"
                output_folder.mkdir(exist_ok=True)
                
                for i in range(0,len(image_paths)):
                    file_name = os.path.basename(image_paths[i])
                    name, extension = os.path.splitext(file_name)
                    file_name = name + "_aligned" + extension
                    
                    
                    image = cv2.imread(str(image_paths[i]))
                    if image is None:
                        self.error.emit(f"Failed to read image: {image_paths[i].name}")
                        return
                        
                    h, w = image.shape[:2]
                    
                    transformed_image = image

                    full_path = os.path.join(output_folder, file_name)
                    cv2.imwrite(full_path, transformed_image)
                    self.progress.emit(total + i + 1, total * 2, f"Aligning: {image_paths[i].name}")

                self.finished.emit(str(self.folder_path))
                return
             
            transform_matrices = process.compute_transforms(marker_corners)    
            
            # Create the output directory
            output_folder = Path(image_paths[0]).parent / "aligned"
            output_folder.mkdir(exist_ok=True)
            
            for i in range(0,len(image_paths)):
                file_name = os.path.basename(image_paths[i])
                name, extension = os.path.splitext(file_name)
                file_name = name + "_aligned" + extension
                
                
                image = cv2.imread(str(image_paths[i]))
                if image is None:
                    self.error.emit(f"Failed to read image: {image_paths[i].name}")
                    return
                    
                h, w = image.shape[:2]
                
                if transform_matrices[i] is None:
                    transformed_image = image
                else:
                    transformed_image = cv2.warpAffine(image, transform_matrices[i], (w, h))

                full_path = os.path.join(output_folder, file_name)
                cv2.imwrite(full_path, transformed_image)
                self.progress.emit(total + i + 1, total * 2, f"Aligning: {image_paths[i].name}")

            self.finished.emit(str(self.folder_path))

        except Exception as e:
            self.error.emit(str(e))


class ImageAlignerUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.folders = {}          # str(path) -> data dict
        self.processing_queue = [] # list of str paths
        self.current_worker = None
        self.current_progress = 0
        self.verify_window = None

        self.init_ui()
        self.setup_timer()

    def init_ui(self):
        self.setWindowTitle("Image Aligner")
        self.setGeometry(100, 100, 1000, 500)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # --- Header ---
        header_layout = QHBoxLayout()

        self.load_button = QPushButton("Load Folder")
        self.load_button.setToolTip("Select one or more folders containing timelapse images")
        self.load_button.clicked.connect(self.load_folder)
        self.load_button.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; padding: 6px; font-weight: bold; }")

        self.queue_label = QLabel("Queue: 0 | Idle")

        self.clear_queue_button = QPushButton("Clear Queue")
        self.clear_queue_button.setToolTip("Remove all pending folders from the queue")
        self.clear_queue_button.clicked.connect(self.clear_queue)
        self.clear_queue_button.setStyleSheet("QPushButton { background-color: #f44336; color: white; }")

        header_layout.addWidget(self.load_button)
        header_layout.addWidget(self.queue_label)
        header_layout.addStretch()
        header_layout.addWidget(self.clear_queue_button)
        layout.addLayout(header_layout)

        # --- Table ---
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Folder", "Images", "Aligned", "Progress", "Status", "Action", "Verify", "Remove"
        ])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setColumnWidth(1, 60)
        self.table.setColumnWidth(2, 70)
        self.table.setColumnWidth(3, 150)
        self.table.setColumnWidth(4, 100)
        self.table.setColumnWidth(5, 150)
        self.table.setColumnWidth(6, 80)
        self.table.setColumnWidth(7, 80)

        layout.addWidget(self.table)

        # --- Log ---
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(100)
        self.log_text.setStyleSheet("QTextEdit { background-color: #f0f0f0; font-family: monospace; font-size: 10px; }")
        layout.addWidget(self.log_text)

    # --- Logic ---

    def analyze_folder(self, folder_path):
        folder = Path(folder_path)
        extensions = {'.png', '.tif', '.tiff'}

        data = {
            'path': str(folder_path),
            'name': folder.name,
            'total_images': 0,
            'aligned_images': 0,
            'status': 'Not Started',
            'progress': 0,
        }

        image_paths = sorted(p for p in folder.glob('*') if p.suffix.lower() in extensions)
        data['total_images'] = len(image_paths)

        if data['total_images'] == 0:
            data['status'] = 'No Images'
            return data

        is_running = (self.current_worker is not None and
                      str(self.current_worker.folder_path) == str(folder_path))
        is_queued = str(folder_path) in self.processing_queue

        if is_running:
            data['status'] = 'Aligning'
            data['progress'] = self.current_progress
            return data

        if is_queued:
            data['status'] = 'Queued'
            return data

        aligned_folder = folder / 'aligned'
        if aligned_folder.exists():
            aligned_paths = sorted(p for p in aligned_folder.glob('*') if p.suffix.lower() in extensions)
            data['aligned_images'] = len(aligned_paths)

            if data['aligned_images'] >= data['total_images']:
                data['status'] = 'Complete'
                data['progress'] = 100
            elif data['aligned_images'] > 0:
                data['status'] = 'Incomplete'
                data['progress'] = int(data['aligned_images'] / data['total_images'] * 100)

        return data

    def update_table(self):
        self.table.setUpdatesEnabled(False)
        try:
            rows = list(self.folders.values())
            self.table.setRowCount(len(rows))

            colors = {
                'Complete':   QColor(200, 255, 200),
                'Aligning':   QColor(255, 255, 224),
                'Queued':     QColor(255, 255, 200),
                'Incomplete': QColor(255, 220, 180),
                'Error':      QColor(255, 200, 200),
                'No Images':  QColor(240, 240, 240),
            }

            for row, data in enumerate(rows):
                self.table.setItem(row, 0, QTableWidgetItem(data['name']))

                for col, key in [(1, 'total_images'), (2, 'aligned_images')]:
                    item = QTableWidgetItem(str(data[key]))
                    item.setTextAlignment(Qt.AlignCenter)
                    self.table.setItem(row, col, item)

                p_bar = QProgressBar()
                p_bar.setValue(data['progress'])
                p_bar.setAlignment(Qt.AlignCenter)
                self.table.setCellWidget(row, 3, p_bar)

                s_item = QTableWidgetItem(data['status'])
                s_item.setBackground(colors.get(data['status'], QColor(255, 255, 255)))
                s_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, 4, s_item)

                self._set_row_action(row, data)

                verify_btn = QPushButton("Verify")
                verify_btn.setToolTip("Scroll through frames and check the detected ArUco marker position")
                verify_btn.setFixedSize(70, 25)
                verify_btn.setEnabled(data['total_images'] > 0)
                verify_btn.clicked.connect(lambda _, p=data['path']: self.open_verify(p))
                w_vf = QWidget()
                l_vf = QHBoxLayout(w_vf)
                l_vf.setContentsMargins(0, 0, 0, 0)
                l_vf.setAlignment(Qt.AlignCenter)
                l_vf.addWidget(verify_btn)
                self.table.setCellWidget(row, 6, w_vf)

                rm_btn = QPushButton("Remove")
                rm_btn.setToolTip("Stop monitoring this folder (does not delete files)")
                rm_btn.setFixedSize(70, 25)
                rm_btn.setStyleSheet("QPushButton { color: #555; }")
                rm_btn.clicked.connect(lambda _, p=data['path']: self.remove_folder(p))
                w_rm = QWidget()
                l_rm = QHBoxLayout(w_rm)
                l_rm.setContentsMargins(0, 0, 0, 0)
                l_rm.setAlignment(Qt.AlignCenter)
                l_rm.addWidget(rm_btn)
                self.table.setCellWidget(row, 7, w_rm)
        finally:
            self.table.setUpdatesEnabled(True)

    def _set_row_action(self, row, data):
        status = data['status']
        path = data['path']

        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignCenter)

        if status == 'Not Started':
            btn = QPushButton("Align")
            btn.setFixedSize(120, 25)
            btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
            btn.clicked.connect(lambda: self.add_to_queue(path))
            layout.addWidget(btn)

        elif status in ['Complete', 'Incomplete']:
            btn = QPushButton("Re-align")
            btn.setFixedSize(120, 25)
            btn.setStyleSheet("QPushButton { background-color: #2196F3; color: white; }")
            btn.clicked.connect(lambda: self.add_to_queue(path))
            layout.addWidget(btn)

        elif status == 'Queued':
            btn = QPushButton("Cancel")
            btn.setFixedSize(120, 25)
            btn.clicked.connect(lambda: self.remove_from_queue(path))
            layout.addWidget(btn)

        elif status == 'Aligning':
            btn = QPushButton("Kill Process")
            btn.setFixedSize(120, 25)
            btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; }")
            btn.clicked.connect(lambda: self.current_worker.terminate())
            layout.addWidget(btn)

        elif status == 'Error':
            btn = QPushButton("Retry")
            btn.setFixedSize(120, 25)
            btn.setStyleSheet("QPushButton { background-color: #FF5722; color: white; }")
            btn.clicked.connect(lambda: self.add_to_queue(path))
            layout.addWidget(btn)

        else:
            item = QTableWidgetItem("—")
            item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 5, item)
            return

        self.table.setItem(row, 5, None)
        self.table.setCellWidget(row, 5, container)

    # --- Queue & Worker ---

    def load_folder(self):
        dialog = QFileDialog(self, "Select Project Folder(s)")
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        dialog.setOption(QFileDialog.ShowDirsOnly, True)
        for view in dialog.findChildren(QAbstractItemView):
            view.setSelectionMode(QAbstractItemView.ExtendedSelection)

        if dialog.exec_():
            for base_path in dialog.selectedFiles():
                if os.path.isdir(base_path):
                    self.discover_subfolders(base_path)
            self.update_table()

    def discover_subfolders(self, base_path):
        """Adds all subdirectories of base_path as individual rows."""
        try:
            subdirs = [
                os.path.join(base_path, item)
                for item in sorted(os.listdir(base_path))
                if os.path.isdir(os.path.join(base_path, item))
            ]
            if not subdirs:
                self.log_message(f"No subdirectories found in {Path(base_path).name}")
                return
            for subfolder in subdirs:
                key = str(subfolder)
                if key not in self.folders:
                    self.folders[key] = self.analyze_folder(subfolder)
            self.log_message(f"Loaded {len(subdirs)} folder(s) from {Path(base_path).name}")
        except Exception as e:
            self.log_message(f"Error loading {Path(base_path).name}: {e}")

    def add_to_queue(self, path):
        if path not in self.processing_queue:
            self.processing_queue.append(path)
            self.log_message(f"Queued: {Path(path).name}")
            self.update_queue_label()
            self.refresh_data()

    def remove_from_queue(self, path):
        if path in self.processing_queue:
            self.processing_queue.remove(path)
            self.update_queue_label()
            self.refresh_data()

    def open_verify(self, path):
        # Owned here, not by the row: the table is rebuilt every 1-3 seconds
        if self.verify_window is not None:
            self.verify_window.close()
        window = VerifyWindow(path, self)
        # destroyed fires late (deleteLater), so only clear if it's still the current window
        window.destroyed.connect(lambda: setattr(self, 'verify_window', None) if self.verify_window is window else None)
        self.verify_window = window
        window.show()

    def remove_folder(self, path):
        self.folders.pop(path, None)
        self.update_table()

    def process_queue(self):
        if self.current_worker or not self.processing_queue:
            return

        path = self.processing_queue.pop(0)
        self.current_progress = 0

        self.current_worker = AlignWorker(path)
        self.current_worker.progress.connect(self.on_progress)
        self.current_worker.finished.connect(self.on_worker_done)
        self.current_worker.error.connect(self.on_error)
        self.current_worker.warning.connect(self.on_warning)
        self.current_worker.start()

        self.update_queue_label()
        self.log_message(f"Starting: {Path(path).name}")

    def on_progress(self, current, total, msg):
        self.current_progress = int(current / total * 100) if total > 0 else 0
        self.log_message(msg)
        self.refresh_data()

    def on_worker_done(self, path):
        self.log_message(f"Complete: {Path(path).name}")
        self._cleanup_worker()
    
    def on_warning(self, msg):
        self.log_message(f"Warning: {msg}")

    def on_error(self, msg):
        self.log_message(f"Error: {msg}")
        if self.current_worker:
            key = str(self.current_worker.folder_path)
            if key in self.folders:
                self.folders[key]['status'] = 'Error'
        self._cleanup_worker()

    def _cleanup_worker(self):
        if self.current_worker:
            self.current_worker.quit()
            self.current_worker.wait()
            self.current_worker = None
        self.current_progress = 0
        self.refresh_data()
        self.update_queue_label()

    def setup_timer(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self.timer_update)
        self.timer.start(2000)

    def timer_update(self):
        self.timer.setInterval(1000 if (self.current_worker or self.processing_queue) else 3000)
        self.refresh_data()
        self.process_queue()

    def refresh_data(self):
        for path, data in self.folders.items():
            if data['status'] != 'Error':
                self.folders[path] = self.analyze_folder(path)
        self.update_table()

    def update_queue_label(self):
        q = len(self.processing_queue)
        curr = f"Processing: {Path(str(self.current_worker.folder_path)).name}" if self.current_worker else "Idle"
        self.queue_label.setText(f"Queue: {q} | {curr}")

    def clear_queue(self):
        self.processing_queue.clear()
        self.update_queue_label()
        self.refresh_data()

    def log_message(self, msg):
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{ts}] {msg}")

    def closeEvent(self, event):
        if self.current_worker and self.current_worker.isRunning():
            reply = QMessageBox.question(
                self, 'Process Running',
                f"Alignment is running for {Path(str(self.current_worker.folder_path)).name}.\n\nForce quit?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.current_worker.terminate()
                self.current_worker.wait(3000)
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


def main():
    app = QApplication(sys.argv)
    window = ImageAlignerUI()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()