"""
Tests for the Tab 1 "Batch Analyze" button and the validation it shares with
"Analyze Plant" (run.py: validate_analysis_inputs / analysis / batch_analysis).

Run from singlePlantAnalysis/ in the ChronoRoot env:

    python -m unittest test_batch_gui -v
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# Headless Qt, and a throwaway HOME so importing run.py cannot touch ~/.config/chronoroot.
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["HOME"] = tempfile.mkdtemp(prefix="batch-gui-home-")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5 import QtCore, QtWidgets

import run

_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class BatchGuiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.window = run.Ui_ChronoRootAnalysis()

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="batch-gui-"))
        patcher = mock.patch.object(QtWidgets.QMessageBox, "warning")
        self.warning = patcher.start()
        self.addCleanup(patcher.stop)
        # Start every test from a blank form with manual calibration.
        self.window.videoField.setText("")
        self.window.projectField.setText("")
        self.window.videoHasArucoButton.setChecked(False)
        self.window.knownDistanceField.setText("10")
        self.window.pixelDistanceField.setText("240")

    def _valid_project(self):
        """A video folder that passes every check, and a project folder."""
        video = self.tmp / "video"
        (video / "Segmentation" / "Ensemble").mkdir(parents=True)
        (video / "0001.png").write_bytes(b"x")
        (video / "Segmentation" / "Ensemble" / "0001.png").write_bytes(b"x")
        project = self.tmp / "project"
        project.mkdir()
        self.window.videoField.setText(str(video))
        self.window.projectField.setText(str(project))
        return project

    def _press(self, handler):
        with mock.patch.object(run, "GLOBAL_CONFIG_FILE", str(self.tmp / "global.json")), \
                mock.patch.object(run.subprocess, "Popen") as popen:
            handler()
        return popen


class AnalyzePlantRefactorTests(BatchGuiTestCase):
    def test_analyze_plant_still_launches_1_analysis(self):
        project = self._valid_project()
        popen = self._press(self.window.analysis)
        popen.assert_called_once()
        self.assertEqual(popen.call_args[0][0][1:],
                         ["1_analysis.py", "--config", str(project / "project_config.json")])

    def test_validate_returns_images_on_success_and_none_on_failure(self):
        self.assertIsNone(self.window.validate_analysis_inputs())
        self._valid_project()
        images = self.window.validate_analysis_inputs()
        self.assertEqual([Path(p).name for p in images], ["0001.png"])


class BatchAnalyzeButtonTests(BatchGuiTestCase):
    def test_batch_button_exists_and_is_visible_clickable(self):
        w = self.window
        w.show()
        _APP.processEvents()
        self.addCleanup(w.hide)
        btn = w.batchAnalysisButton
        self.assertEqual(btn.objectName(), "batchAnalysisButton")
        self.assertIs(btn.parent(), w.tab1)
        self.assertEqual(btn.text(), "Batch Analyze")
        self.assertIn("ROI", btn.toolTip())
        self.assertIn("root origin", btn.toolTip())
        # Inside the tab page, and not on top of any other Tab 1 widget or divider.
        rect = btn.geometry()
        self.assertTrue(w.tab1.rect().contains(rect), (rect, w.tab1.rect()))
        for other in w.tab1.findChildren(QtWidgets.QWidget, options=QtCore.Qt.FindDirectChildrenOnly):
            if other is btn:
                continue
            self.assertFalse(rect.intersects(other.geometry()),
                             f"{other.objectName() or other} {other.geometry()} overlaps {rect}")
        self.assertTrue(btn.isEnabled())
        self.assertTrue(btn.isVisible())
        self.assertIs(w.tab1.childAt(rect.center()), btn)

    def test_batch_blocked_without_video_folder(self):
        popen = self._press(self.window.batch_analysis)
        popen.assert_not_called()
        self.assertTrue(self.warning.called)

    def test_batch_blocked_when_aruco_check_fails(self):
        self._valid_project()
        self.window.videoHasArucoButton.setChecked(True)
        with mock.patch.object(run.Ui_ChronoRootAnalysis, "check_aruco_marker", return_value=False):
            popen = self._press(self.window.batch_analysis)
        popen.assert_not_called()

    def test_batch_launches_batch_setup_when_valid(self):
        project = self._valid_project()
        popen = self._press(self.window.batch_analysis)
        popen.assert_called_once()
        self.assertEqual(popen.call_args[0][0][1:],
                         ["batch_setup.py", "--config", str(project / "project_config.json")])

    def test_clicking_the_button_runs_batch_analysis(self):
        with mock.patch.object(run.Ui_ChronoRootAnalysis, "batch_analysis") as handler:
            # connect() captured the bound method at build time, so rebuild a window.
            win = run.Ui_ChronoRootAnalysis()
            win.batchAnalysisButton.click()
        handler.assert_called_once()


if __name__ == "__main__":
    unittest.main()
