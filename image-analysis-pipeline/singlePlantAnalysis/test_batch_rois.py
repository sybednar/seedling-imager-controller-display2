import os
import shutil
import tempfile
import unittest

import cv2
import numpy as np

from unittest import mock

from analysis.utils.proposeROIs import detect_seed_centroids, propose_boxes
from analysis.utils import boxEdit
from analysis.utils import getROIandSeed as gr

H, W = 400, 400


class BatchRoiTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)

    def write(self, name, seeds=(), roots=(), size=8):
        """seeds: (x, y) centres drawn as class 3; roots: (x, y_top, y_bottom) class 1."""
        m = np.zeros((H, W), np.uint8)
        for x, y in seeds:
            m[y - size // 2:y + size // 2, x - size // 2:x + size // 2] = 3
        for x, y0, y1 in roots:
            m[y0:y1 + 1, x] = 1
        p = os.path.join(self.dir, name)
        cv2.imwrite(p, m)
        return p

    def test_three_seeds_sorted_left_to_right(self):
        p = self.write("a.png", seeds=[(250, 50), (50, 50), (150, 50)])
        c = detect_seed_centroids([p])
        self.assertEqual(len(c), 3)
        xs = [x for x, _ in c]
        self.assertEqual(xs, sorted(xs))
        for got, want in zip(xs, [50, 150, 250]):
            self.assertAlmostEqual(got, want, delta=1.0)

    def test_tiny_blob_ignored(self):
        p = self.write("a.png", seeds=[(100, 50)], size=2)
        self.assertEqual(detect_seed_centroids([p], min_area=30), [])

    def test_no_seeds_returns_empty(self):
        p = self.write("a.png")
        self.assertEqual(detect_seed_centroids([p]), [])

    def test_seed_found_in_later_frame(self):
        p0 = self.write("a.png")
        p1 = self.write("b.png", seeds=[(100, 50)])
        c = detect_seed_centroids([p0, p1])
        self.assertEqual(len(c), 1)
        self.assertAlmostEqual(c[0][0], 100, delta=1.0)

    def test_boxes_split_at_midpoints(self):
        p = self.write("a.png", seeds=[(100, 50), (300, 50)])
        c = detect_seed_centroids([p])
        b = propose_boxes(c, [p], (H, W))
        self.assertEqual(b[0][3], 200)
        self.assertEqual(b[1][2], 200)

    def test_single_seed_box_nonzero_width_inside_image(self):
        p = self.write("a.png", seeds=[(200, 50)])
        b = propose_boxes(detect_seed_centroids([p]), [p], (H, W))
        self.assertEqual(len(b), 1)
        self.assertTrue(0 <= b[0][2] < b[0][3] <= W)

    def test_boxes_clipped_to_image_and_ordered(self):
        p = self.write("a.png", seeds=[(5, 5), (200, 50), (395, 395)])
        b = propose_boxes(detect_seed_centroids([p]), [p], (H, W))
        self.assertGreaterEqual(b[0][2], 0)
        for y0, y1, x0, x1 in b:
            self.assertLess(y0, y1)
            self.assertLess(x0, x1)
            self.assertTrue(0 <= y0 and y1 <= H and 0 <= x0 and x1 <= W)

    def test_box_extends_to_lowest_root_pixel(self):
        p0 = self.write("a.png", seeds=[(100, 50), (300, 50)])
        p1 = self.write("b.png", seeds=[(100, 50), (300, 50)], roots=[(100, 55, 300)])
        c = detect_seed_centroids([p0, p1])
        b = propose_boxes(c, [p0, p1], (H, W))
        self.assertGreaterEqual(b[0][1], 300)
        self.assertLessEqual(b[0][1], H)

    def test_root_of_neighbour_does_not_extend_box(self):
        p0 = self.write("a.png", seeds=[(100, 50), (300, 50)])
        base = propose_boxes(detect_seed_centroids([p0]), [p0], (H, W))
        p1 = self.write("b.png", seeds=[(100, 50), (300, 50)], roots=[(300, 55, 380)])
        b = propose_boxes(detect_seed_centroids([p0]), [p0, p1], (H, W))
        self.assertEqual(b[0][1], base[0][1])
        self.assertGreaterEqual(b[1][1], 380)

    def test_merged_seeds_give_one_box(self):
        p = self.write("a.png", seeds=[(100, 50), (108, 50)])
        c = detect_seed_centroids([p])
        self.assertEqual(len(c), 1)
        self.assertEqual(len(propose_boxes(c, [p], (H, W))), 1)


class BoxEditTests(unittest.TestCase):
    SHAPE = (400, 400)

    def test_hit_test_prefers_edge_over_body(self):
        boxes = [[100, 300, 100, 300]]
        self.assertEqual(boxEdit.hit_test(boxes, 102, 200), (0, 'l'))
        self.assertEqual(boxEdit.hit_test(boxes, 298, 200), (0, 'r'))
        self.assertEqual(boxEdit.hit_test(boxes, 200, 103), (0, 't'))
        self.assertEqual(boxEdit.hit_test(boxes, 200, 297), (0, 'b'))
        self.assertEqual(boxEdit.hit_test(boxes, 200, 200), (0, 'body'))

    def test_hit_test_none_outside(self):
        self.assertIsNone(boxEdit.hit_test([[100, 300, 100, 300]], 10, 10))
        self.assertIsNone(boxEdit.hit_test([], 10, 10))

    def test_hit_test_overlap_picks_last(self):
        boxes = [[0, 200, 0, 200], [100, 300, 100, 300]]
        self.assertEqual(boxEdit.hit_test(boxes, 150, 150), (1, 'body'))
        self.assertEqual(boxEdit.hit_test(boxes, 50, 50), (0, 'body'))

    def test_move_box_clamped_to_image(self):
        box = [100, 200, 100, 200]
        self.assertEqual(boxEdit.move_box(box, -500, -500, self.SHAPE), [0, 100, 0, 100])
        self.assertEqual(boxEdit.move_box(box, 500, 500, self.SHAPE), [300, 400, 300, 400])
        self.assertEqual(boxEdit.move_box(box, 10, -20, self.SHAPE), [80, 180, 110, 210])

    def test_resize_box_enforces_min_size(self):
        box = [100, 200, 100, 200]
        r = boxEdit.resize_box(box, 'r', -500, 0, self.SHAPE)
        self.assertEqual(r, [100, 200, 100, 120])
        b = boxEdit.resize_box(box, 't', 0, 500, self.SHAPE)
        self.assertEqual(b, [180, 200, 100, 200])

    def test_resize_box_cannot_invert(self):
        box = [100, 200, 100, 200]
        l = boxEdit.resize_box(box, 'l', 500, 0, self.SHAPE)
        self.assertLess(l[2], l[3])
        bt = boxEdit.resize_box(box, 'b', 0, -500, self.SHAPE)
        self.assertLess(bt[0], bt[1])

    def test_resize_box_clamped_to_image(self):
        r = boxEdit.resize_box([100, 200, 100, 200], 'l', -500, 0, self.SHAPE)
        self.assertEqual(r[2], 0)

    def test_renumber_sorts_by_x(self):
        boxes = [[0, 10, 300, 350], [0, 10, 10, 60], [0, 10, 150, 200]]
        self.assertEqual([b[2] for b in boxEdit.renumber(boxes)], [10, 150, 300])


class PlateRoisTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        m = np.zeros((H, W), np.uint8)
        m[46:54, 96:104] = 3
        self.seg = os.path.join(self.dir, "s.png")
        cv2.imwrite(self.seg, m)
        self.img = os.path.join(self.dir, "i.png")
        cv2.imwrite(self.img, np.zeros((H, W, 3), np.uint8))
        self.conf = {'timeStep': 15}

    def run_with(self, rois, seeds):
        with mock.patch.object(gr, 'selectPlantROIs', return_value=rois) as sp, \
             mock.patch.object(gr, 'selectSeed', side_effect=seeds) as ss:
            out = gr.getPlateROIsAndSeeds(self.conf, [self.img], [self.seg])
        return out, sp, ss

    def test_getPlateROIsAndSeeds_cancel_returns_none(self):
        out, _, ss = self.run_with(None, [])
        self.assertIsNone(out)
        ss.assert_not_called()

    def test_getPlateROIsAndSeeds_zero_boxes_returns_none(self):
        out, _, ss = self.run_with([], [])
        self.assertIsNone(out)
        ss.assert_not_called()

    def test_getPlateROIsAndSeeds_numbers_plants_left_to_right(self):
        rois = [[0, 100, 200, 300], [0, 100, 0, 100]]
        out, _, ss = self.run_with(rois, [[5, 6], [7, 8]])
        self.assertEqual([d['plant'] for d in out], [1, 2])
        self.assertEqual(out[0]['bounding box'], [0, 100, 0, 100])
        self.assertEqual(out[1]['bounding box'], [0, 100, 200, 300])
        self.assertEqual(out[0]['seed'], [5, 6])
        self.assertEqual(out[1]['seed'], [7, 8])
        self.assertEqual(ss.call_args_list[0][0][2], [0, 100, 0, 100])

    def test_getPlateROIsAndSeeds_cancel_during_origin_click_returns_none(self):
        rois = [[0, 100, 0, 100], [0, 100, 200, 300]]
        out, _, _ = self.run_with(rois, [[5, 6], None])
        self.assertIsNone(out)

    def test_getPlateROIsAndSeeds_passes_proposed_boxes(self):
        _, sp, _ = self.run_with([[0, 100, 0, 100]], [[1, 1]])
        proposed = sp.call_args[0][1]
        self.assertEqual(len(proposed), 1)


if __name__ == "__main__":
    unittest.main()
