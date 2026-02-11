# main.py
import sys
from PySide6.QtWidgets import QApplication
from gui import SeedlingImagerGUI

def start_gui():
    app = QApplication(sys.argv)
    window = SeedlingImagerGUI()
    window.showFullScreen()  # dedicated touchscreen kiosk-style fullscreen (changed from window.show())
    sys.exit(app.exec())

if __name__ == "__main__":
    start_gui()