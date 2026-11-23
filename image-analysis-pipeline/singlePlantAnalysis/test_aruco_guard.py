"""
Tests for the ArUco ID filter (analysis/qr.py) and the GUI guard on the analysis button
(run.py: check_aruco_marker / analysis).

Run from singlePlantAnalysis/ in the ChronoRoot env (needs cv2 and PyQt5; no pytest needed):

    python -m unittest test_aruco_guard -v
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# Headless Qt, and a throwaway HOME so importing run.py cannot touch ~/.config/chronoroot.
os.environ["QT_QPA_PLATFORM"] = "offscreen"
_HOME = tempfile.mkdtemp(prefix="aruco-guard-home-")
os.environ["HOME"] = _HOME
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cv2
import numpy as np
from cv2 import aruco
from PyQt5 import QtWidgets

import run
from analysis.qr import aruco_detect, aruco_get_pixel_size
from analysis.utils.calibration import MIN_ARUCO_PIXEL_WIDTH

_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _marker(dictionary, marker_id, size):
    return aruco.generateImageMarker(aruco.getPredefinedDictionary(dictionary), marker_id, size)


def write_image(path, markers=(), canvas=(1400, 2200)):
    """
    White canvas with markers pasted in a row. markers: iterable of
    (dictionary, id, side_px). Returns the path.
    """
    img = np.full(canvas, 255, np.uint8)
    x = 60
    for dictionary, marker_id, size in markers:
        m = cv2.copyMakeBorder(_marker(dictionary, marker_id, size), 40, 40, 40, 40,
                               cv2.BORDER_CONSTANT, value=255)
        img[60:60 + m.shape[0], x:x + m.shape[1]] = m
        x += m.shape[1] + 40
    cv2.imwrite(str(path), img)
    return str(path)


D50 = aruco.DICT_4X4_50
D1000 = aruco.DICT_4X4_1000


class ArucoIdFilterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="aruco-detect-"))

    def test_ids_0_to_6_are_detected(self):
        for marker_id in (0, 3, 6):
            with self.subTest(marker_id=marker_id):
                path = write_image(self.tmp / f"id{marker_id}.png", [(D50, marker_id, 400)])
                detection = aruco_detect(path)
                self.assertIsNotNone(detection)
                self.assertEqual(len(detection), 1)

    def test_ids_above_6_are_ignored(self):
        for marker_id in (7, 20, 49):
            with self.subTest(marker_id=marker_id):
                path = write_image(self.tmp / f"id{marker_id}.png", [(D50, marker_id, 400)])
                self.assertIsNone(aruco_detect(path))

    def test_only_the_allowed_marker_is_kept_when_several_are_present(self):
        # ID 20 is larger and comes first; ID 3 must be the one returned.
        path = write_image(self.tmp / "mixed.png", [(D50, 20, 500), (D50, 3, 400)])
        detection = aruco_detect(path)
        self.assertIsNotNone(detection)
        self.assertEqual(len(detection), 1)
        self.assertAlmostEqual(aruco_get_pixel_size(detection[0]), 400, delta=3)

    def test_returns_all_allowed_markers_in_a_tuple(self):
        path = write_image(self.tmp / "two.png", [(D50, 1, 400), (D50, 2, 400), (D50, 30, 400)])
        detection = aruco_detect(path)
        self.assertIsInstance(detection, tuple)
        self.assertEqual(len(detection), 2)

    def test_marker_width_is_close_to_its_pixel_size(self):
        path = write_image(self.tmp / "w.png", [(D50, 0, 400)])
        self.assertAlmostEqual(aruco_get_pixel_size(aruco_detect(path)[0]), 400, delta=3)

    def test_blank_image_has_no_marker(self):
        self.assertIsNone(aruco_detect(write_image(self.tmp / "blank.png")))

    def test_marker_from_the_old_1000_dictionary_is_not_detected(self):
        # ID 500 exists only in DICT_4X4_1000 (the first 50 codes are shared by both).
        path = write_image(self.tmp / "d1000.png", [(D1000, 500, 400)])
        self.assertIsNone(aruco_detect(path))

    def test_unreadable_image_returns_none_instead_of_raising(self):
        bad = self.tmp / "corrupt.png"
        bad.write_bytes(b"this is not an image")
        self.assertIsNone(aruco_detect(str(bad)))
        self.assertIsNone(aruco_detect(str(self.tmp / "missing.png")))


class ArucoGuardTests(unittest.TestCase):
    """run.Ui_ChronoRootAnalysis.check_aruco_marker and the analysis() button handler."""

    @classmethod
    def setUpClass(cls):
        cls.window = run.Ui_ChronoRootAnalysis()

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="aruco-guard-"))
        self.big = write_image(self.tmp / "big.png", [(D50, 0, MIN_ARUCO_PIXEL_WIDTH + 100)])
        self.small = write_image(self.tmp / "small.png", [(D50, 0, MIN_ARUCO_PIXEL_WIDTH - 100)])
        self.blank = write_image(self.tmp / "blank.png")
        self.wrong_id = write_image(self.tmp / "wrong_id.png", [(D50, 20, MIN_ARUCO_PIXEL_WIDTH + 100)])

        patcher = mock.patch.object(QtWidgets.QMessageBox, "warning")
        self.warning = patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(run.Ui_ChronoRootAnalysis, "show_aruco_precheck", return_value=True)
        self.precheck = patcher.start()
        self.addCleanup(patcher.stop)

    def warned_text(self):
        self.assertTrue(self.warning.called, "expected a warning dialog")
        return self.warning.call_args[0][2]

    def test_no_marker_warns_and_blocks(self):
        self.assertFalse(self.window.check_aruco_marker([self.blank]))
        self.assertIn("No ArUco marker detected, please use manual calibration instead.", self.warned_text())
        self.precheck.assert_not_called()

    def test_marker_with_an_ignored_id_counts_as_no_marker(self):
        self.assertFalse(self.window.check_aruco_marker([self.wrong_id]))
        self.assertIn("No ArUco marker detected", self.warned_text())
        self.precheck.assert_not_called()

    def test_marker_below_the_minimum_width_warns_and_blocks(self):
        self.assertFalse(self.window.check_aruco_marker([self.small]))
        text = self.warned_text()
        self.assertIn("No ArUco marker detected, please use manual calibration instead.", text)
        self.assertIn(f"minimum {MIN_ARUCO_PIXEL_WIDTH} px", text)
        self.precheck.assert_not_called()

    def test_marker_above_the_minimum_width_goes_to_the_precheck(self):
        self.assertTrue(self.window.check_aruco_marker([self.big]))
        self.warning.assert_not_called()
        self.precheck.assert_called_once()
        img_path, detection, width = self.precheck.call_args[0]
        self.assertEqual(img_path, self.big)
        self.assertGreaterEqual(width, MIN_ARUCO_PIXEL_WIDTH)
        self.assertAlmostEqual(width, MIN_ARUCO_PIXEL_WIDTH + 100, delta=3)
        self.assertEqual(len(detection), 1)

    def test_the_users_answer_in_the_precheck_is_returned(self):
        self.precheck.return_value = False
        self.assertFalse(self.window.check_aruco_marker([self.big]))
        self.warning.assert_not_called()  # cancelling is not an error

    def test_a_bad_image_does_not_stop_the_scan(self):
        bad = self.tmp / "corrupt.png"
        bad.write_bytes(b"not an image")
        self.assertTrue(self.window.check_aruco_marker([str(bad), self.big]))
        self.warning.assert_not_called()
        self.assertEqual(self.precheck.call_args[0][0], self.big)

    def test_only_the_first_20_images_are_scanned(self):
        frames = []
        for n in range(1, 21):  # frames 1-20 are blank, frame 21 has the marker
            frames.append(write_image(self.tmp / f"frame_{n:02d}.png"))
        late = write_image(self.tmp / "frame_21.png", [(D50, 0, MIN_ARUCO_PIXEL_WIDTH + 100)])
        self.assertFalse(self.window.check_aruco_marker(frames + [late]))
        self.assertIn("No ArUco marker detected", self.warned_text())
        self.precheck.assert_not_called()

        # ...but a marker in frame 20 (the last one scanned) is still found.
        self.warning.reset_mock()
        on_20 = write_image(self.tmp / "frame_20.png", [(D50, 0, MIN_ARUCO_PIXEL_WIDTH + 100)])
        self.assertTrue(self.window.check_aruco_marker(frames[:19] + [on_20, late]))
        self.assertEqual(self.precheck.call_args[0][0], on_20)

    def test_images_are_scanned_in_natural_order(self):
        # frame_2 has the marker; a plain string sort would put frame_10 (blank) first.
        write_image(self.tmp / "frame_10.png")
        marker = write_image(self.tmp / "frame_2.png", [(D50, 0, MIN_ARUCO_PIXEL_WIDTH + 100)])
        images = [str(self.tmp / "frame_10.png"), marker]
        self.assertTrue(self.window.check_aruco_marker(images))
        self.assertEqual(self.precheck.call_args[0][0], marker)

    def test_the_cursor_is_restored_after_every_outcome(self):
        for images in ([self.blank], [self.small], [self.big]):
            with self.subTest(images=[os.path.basename(i) for i in images]):
                self.window.check_aruco_marker(images)
                self.assertIsNone(QtWidgets.QApplication.overrideCursor())

    # --- the analysis() button handler: the guard must gate the launch ---

    def _project_with(self, image_path):
        """A video folder that passes analysis()'s earlier checks, and a project folder."""
        video = self.tmp / "video"
        (video / "Segmentation" / "Ensemble").mkdir(parents=True)
        target = video / "0001.png"
        target.write_bytes(Path(image_path).read_bytes())
        (video / "Segmentation" / "Ensemble" / "0001.png").write_bytes(target.read_bytes())
        project = self.tmp / "project"
        project.mkdir()
        self.window.videoField.setText(str(video))
        self.window.projectField.setText(str(project))
        self.window.knownDistanceField.setText("10")
        self.window.pixelDistanceField.setText("240")

    def _press_analyze(self):
        with mock.patch.object(run, "GLOBAL_CONFIG_FILE", str(self.tmp / "global.json")), \
                mock.patch.object(run.subprocess, "Popen") as popen:
            self.window.analysis()
        return popen

    def test_analyze_does_not_launch_when_the_guard_rejects(self):
        self._project_with(self.blank)
        self.window.videoHasArucoButton.setChecked(True)
        self.assertFalse(self._press_analyze().called)
        self.assertIn("No ArUco marker detected", self.warned_text())

    def test_analyze_does_not_launch_when_the_user_cancels_the_precheck(self):
        self._project_with(self.big)
        self.window.videoHasArucoButton.setChecked(True)
        self.precheck.return_value = False
        self.assertFalse(self._press_analyze().called)

    def test_analyze_launches_when_the_marker_is_confirmed(self):
        self._project_with(self.big)
        self.window.videoHasArucoButton.setChecked(True)
        popen = self._press_analyze()
        self.assertTrue(popen.called)
        self.assertEqual(popen.call_args[0][0][1], "1_analysis.py")

    def test_the_guard_is_skipped_with_manual_calibration(self):
        self._project_with(self.blank)
        self.window.videoHasArucoButton.setChecked(False)
        with mock.patch.object(run.Ui_ChronoRootAnalysis, "check_aruco_marker") as guard:
            popen = self._press_analyze()
        guard.assert_not_called()
        self.assertTrue(popen.called)


if __name__ == "__main__":
    unittest.main()
