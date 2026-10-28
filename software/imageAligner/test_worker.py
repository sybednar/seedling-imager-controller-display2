import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
from run import AlignWorker

def on_progress(current, total, msg):
    print(f"[{current}/{total}] {msg}")

def on_finished(path):
    print(f"Done: {path}")
    app.quit()

def on_error(msg):
    print(f"Error: {msg}")
    app.quit()

app = QApplication(sys.argv)

worker = AlignWorker("/Users/calvinyong/Desktop/UW Madison/Research Materials/Dataset/Experiment  20260528_124038/plate2")
worker.progress.connect(on_progress)
worker.finished.connect(on_finished)
worker.error.connect(on_error)
worker.start()

sys.exit(app.exec_())