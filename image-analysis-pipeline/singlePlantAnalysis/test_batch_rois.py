import os
import shutil
import tempfile
import unittest

import cv2
import numpy as np

from analysis.utils.proposeROIs import detect_seed_centroids, propose_boxes

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


if __name__ == "__main__":
    unittest.main()
