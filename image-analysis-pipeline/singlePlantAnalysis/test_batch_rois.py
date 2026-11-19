import os
import shutil
import tempfile
import unittest

import cv2
import numpy as np

from unittest import mock

from analysis.utils import boxEdit
from analysis.utils import componentROIs as cr
from analysis.utils import segOverlay
from analysis.utils import getROIandSeed as gr

H, W = 400, 400


def setUpModule():
    # Tests read deliberately missing masks; keep cv2's warning out of the output.
    try:
        cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
    except AttributeError:
        pass


class ComponentRoiTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.m = np.zeros((H, W), np.uint8)

    def save(self):
        p = os.path.join(self.dir, "m.png")
        cv2.imwrite(p, self.m)
        return p

    def seed(self, y, x, size=20):
        # size >= MIN_SIZE so a bare seed is a real plant, not a fragment
        self.m[y:y + size, x:x + size] = 3

    def test_two_separate_plants_two_boxes_with_exact_bounds(self):
        self.seed(200, 100, size=8)         # left plant seed
        self.m[150:200, 103] = 4            # hypocotyl above
        self.m[208:260, 103] = 1            # root below
        self.seed(200, 300, size=8)
        self.m[208:240, 303] = 1
        boxes, n_seeds = cr.propose_component_boxes_info(self.save(), margin=20)
        self.assertEqual(n_seeds, 2)
        left = [b for b in boxes if b[2] < 200][0]
        right = [b for b in boxes if b[2] >= 200][0]
        self.assertEqual(left, [130, 280, 80, 128])    # y 150-259 +-20, x 100-107 +-20
        self.assertEqual(right, [180, 260, 280, 328])  # y 200-239 +-20
        self.assertEqual(len(boxes), 2)

    def test_plant_parts_all_inside_box(self):
        self.seed(200, 100)
        self.m[120:200, 100] = 5
        self.m[100:120, 100] = 6
        self.m[208:300, 107] = 2
        (y0, y1, x0, x1), = cr.propose_component_boxes(self.save(), margin=0)
        self.assertLessEqual(y0, 100)
        self.assertGreaterEqual(y1, 300)
        self.assertLessEqual(x0, 100)
        self.assertGreaterEqual(x1, 108)

    def test_touching_plants_merge_into_one_box_but_count_two_seeds(self):
        self.seed(200, 100)
        self.seed(200, 130)
        self.m[203, 120:130] = 1            # bridge
        boxes, n_seeds = cr.propose_component_boxes_info(self.save())
        self.assertEqual(n_seeds, 2)
        self.assertEqual(len(boxes), 1)

    def test_detail_counts_split_seed_as_merged_component(self):
        self.m[200:206, 100:108] = 3
        self.m[208:214, 100:108] = 3      # second blob of the same seed
        self.m[206:240, 100] = 1          # joined by a root pixel column
        d = cr.propose_component_boxes_detail(self.save())
        self.assertEqual(d['n_seed_blobs'], 2)
        self.assertEqual(d['n_components_with_seed'], 1)
        self.assertEqual(d['n_merged_components'], 1)
        self.assertEqual(len(d['boxes']), 1)

    def test_detail_separate_plants_not_merged(self):
        self.seed(200, 100)
        self.seed(200, 300)
        d = cr.propose_component_boxes_detail(self.save())
        self.assertEqual((d['n_seed_blobs'], d['n_components_with_seed'],
                          d['n_merged_components'], d['n_attached'], d['n_unattached']), (2, 2, 0, 0, 0))

    def test_detached_root_attaches_to_standalone_seed(self):
        self.seed(200, 100)
        self.m[260:340, 100:104] = 1
        d = cr.propose_component_boxes_detail(self.save())
        self.assertEqual(d['boxes'], [[180, 360, 80, 140]])
        self.assertEqual((d['n_attached'], d['n_unattached']), (1, 0))

    def test_each_root_attaches_to_its_own_nearest_seed(self):
        self.seed(200, 50)
        self.m[260:340, 50:54] = 1
        self.seed(200, 300)
        self.m[260:340, 300:304] = 1
        d = cr.propose_component_boxes_detail(self.save())
        self.assertEqual(d['boxes'], [[180, 360, 30, 90], [180, 360, 280, 340]])
        self.assertEqual(d['n_attached'], 2)

    def test_equidistant_root_goes_to_lower_label(self):
        self.seed(200, 50)
        self.seed(200, 150)
        self.m[200:261, 105:115] = 1      # gap 36 px to both seeds
        d = cr.propose_component_boxes_detail(self.save())
        self.assertEqual(sorted(d['boxes']), [[180, 240, 130, 190], [180, 281, 30, 135]])
        self.assertEqual(d['n_attached'], 1)

    def test_root_beyond_max_distance_not_attached_and_counted(self):
        self.seed(200, 100)
        self.m[260:340, 100:104] = 1      # gap 41
        d = cr.propose_component_boxes_detail(self.save(), max_attach_distance=30)
        self.assertEqual(d['boxes'], [[180, 240, 80, 140]])
        self.assertEqual((d['n_attached'], d['n_unattached']), (0, 1))
        d = cr.propose_component_boxes_detail(self.save(), max_attach_distance=41)
        self.assertEqual(d['n_attached'], 1)

    def test_speck_under_min_attach_area_ignored(self):
        self.seed(200, 100)
        self.m[230:235, 100:105] = 1      # area 25, gap 10
        d = cr.propose_component_boxes_detail(self.save())
        self.assertEqual(d['boxes'], [[180, 240, 80, 140]])
        self.assertEqual((d['n_attached'], d['n_unattached']), (0, 1))

    def test_lone_seed_still_gets_its_small_box(self):
        self.seed(200, 100)
        d = cr.propose_component_boxes_detail(self.save())
        self.assertEqual(d['boxes'], [[180, 240, 80, 140]])
        tiny = np.zeros((H, W), np.uint8)
        tiny[200:206, 100:106] = 3        # area 36, 6x6
        cv2.imwrite(os.path.join(self.dir, "t.png"), tiny)
        d = cr.propose_component_boxes_detail(os.path.join(self.dir, "t.png"))
        self.assertEqual(d['boxes'], [[180, 226, 80, 126]])

    def test_attached_components_extend_box_in_all_directions(self):
        self.seed(200, 200)
        self.m[100:150, 200:205] = 1      # above
        self.m[270:330, 200:205] = 1      # below
        self.m[205:210, 100:150] = 1      # left
        self.m[205:210, 270:310] = 1      # right
        d = cr.propose_component_boxes_detail(self.save())
        self.assertEqual(d['boxes'], [[80, 350, 80, 330]])
        self.assertEqual(d['n_attached'], 4)

    def test_attached_component_box_clipped_at_border(self):
        self.seed(200, 200)
        self.m[5:150, 205:210] = 1
        d = cr.propose_component_boxes_detail(self.save())
        self.assertEqual(d['boxes'], [[0, 240, 180, 240]])

    def test_unseeded_big_component_beyond_range_left_out(self):
        self.seed(20, 20)
        self.m[350:395, 350:360] = 1      # far away, area 450
        d = cr.propose_component_boxes_detail(self.save())
        self.assertEqual(len(d['boxes']), 1)
        self.assertEqual(d['n_unattached'], 1)

    def test_small_but_real_plant_keeps_its_box(self):
        self.m[200:208, 100:108] = 3      # 8 wide
        self.m[208:240, 103] = 1          # 40 tall >= MIN_SIZE
        d = cr.propose_component_boxes_detail(self.save())
        self.assertEqual(len(d['boxes']), 1)
        self.assertEqual(d['n_unattached'], 0)

    def test_ignore_class_does_not_bridge_plants(self):
        self.seed(200, 100)
        self.seed(200, 130)
        self.m[203, 120:130] = 7
        boxes, n_seeds = cr.propose_component_boxes_info(self.save())
        self.assertEqual((len(boxes), n_seeds), (2, 2))

    def test_noise_component_without_seed_gets_no_box(self):
        self.seed(200, 100)
        self.m[50:60, 300:310] = 1
        self.assertEqual(len(cr.propose_component_boxes(self.save())), 1)

    def test_small_seed_blob_ignored(self):
        self.m[200:203, 100:103] = 3        # area 9 < 30
        self.assertEqual(cr.propose_component_boxes_info(self.save()), ([], 0))

    def test_box_clipped_at_image_borders(self):
        self.seed(0, 0)
        self.seed(H - 20, W - 20)
        boxes = cr.propose_component_boxes(self.save(), margin=20)
        self.assertEqual(sorted(boxes), [[0, 40, 0, 40], [H - 40, H, W - 40, W]])

    def test_empty_and_unreadable_mask_give_no_boxes(self):
        self.assertEqual(cr.propose_component_boxes_info(self.save()), ([], 0))
        self.assertEqual(cr.propose_component_boxes_info(os.path.join(self.dir, "nope.png")), ([], 0))

    def test_boxes_ordered_with_plant_order(self):
        self.seed(50, 100)     # top-left
        self.seed(300, 300)    # bottom-right
        self.seed(300, 50)     # bottom-left
        boxes = cr.propose_component_boxes(self.save())
        self.assertEqual(boxes, boxEdit.renumber(boxes))
        self.assertEqual([b[2] for b in boxes], [30, 280, 80])


class NoticeTests(unittest.TestCase):
    def d(self, n, merged=0, attached=0, unattached=0):
        return {'boxes': [[0, 1, 0, 1]] * n, 'n_seed_blobs': n, 'n_components_with_seed': n,
                'n_merged_components': merged, 'n_attached': attached,
                'n_unattached': unattached}

    def test_plain_notice_has_no_warnings(self):
        t = cr.proposal_notice(self.d(3))
        self.assertIn("3 boxes", t)
        for word in ("share", "attached", "left out"):
            self.assertNotIn(word, t)

    def test_merge_attach_unattached_mentioned_only_when_present(self):
        t = cr.proposal_notice(self.d(2, merged=1, attached=7, unattached=2))
        self.assertIn("seed blobs share a box", t)
        self.assertIn("7 roots/shoots attached to seeds", t)
        self.assertIn("2 far/small pieces left out", t)
        self.assertIn("1 box", cr.proposal_notice(self.d(1)))

    def test_notice_lines_short_and_none_when_no_boxes(self):
        t = cr.proposal_notice(self.d(11, merged=7, attached=12, unattached=30))
        self.assertTrue(all(len(line) <= 60 for line in t.split("\n")))
        self.assertIsNone(cr.proposal_notice(self.d(0, unattached=3)))


class SegOverlayTests(unittest.TestCase):
    def test_each_class_colour_and_background_untouched(self):
        img = np.full((2, 4, 3), 50, np.uint8)
        seg = np.array([[0, 1, 2, 3], [4, 5, 6, 7]], np.uint8)
        out = segOverlay.colorize_segmentation(img, seg)
        self.assertEqual(tuple(out[0, 0]), (50, 50, 50))
        self.assertEqual(tuple(out[0, 1]), (0, 0, 255))
        self.assertEqual(tuple(out[0, 2]), (0, 255, 0))
        self.assertEqual(tuple(out[0, 3]), (255, 0, 0))
        self.assertEqual(tuple(out[1, 0]), (0, 255, 255))
        for x in (1, 2, 3):
            self.assertEqual(tuple(out[1, x]), (255, 0, 255))   # classes 5, 6, 7
        self.assertTrue((img == 50).all())                      # input not modified

    def test_mismatched_seg_is_resized_nearest(self):
        img = np.zeros((4, 4, 3), np.uint8)
        seg = np.array([[1, 2], [3, 4]], np.uint8)
        out = segOverlay.colorize_segmentation(img, seg)
        self.assertEqual(out.shape, (4, 4, 3))
        self.assertEqual(tuple(out[0, 0]), (0, 0, 255))
        self.assertEqual(tuple(out[0, 3]), (0, 255, 0))
        self.assertEqual(tuple(out[3, 0]), (255, 0, 0))
        self.assertEqual(tuple(out[3, 3]), (0, 255, 255))


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

    def test_key_action_outside_add_mode(self):
        k = boxEdit.key_action
        self.assertEqual(k(27, False), 'cancel')
        self.assertEqual(k(ord('q'), False), 'cancel')
        self.assertEqual(k(ord('Q'), False), 'cancel')
        self.assertEqual(k(13, False), 'confirm')
        self.assertEqual(k(ord('d'), False), 'delete')
        self.assertEqual(k(ord('a'), False), 'enter_add')
        self.assertIsNone(k(ord('x'), False))
        self.assertIsNone(k(255, False))

    def test_key_action_in_add_mode_esc_and_a_leave_add_mode(self):
        k = boxEdit.key_action
        self.assertEqual(k(27, True), 'exit_add')
        self.assertEqual(k(ord('a'), True), 'exit_add')
        self.assertEqual(k(ord('A'), True), 'exit_add')
        self.assertEqual(k(ord('q'), True), 'cancel')
        self.assertEqual(k(13, True), 'confirm')

    def test_key_action_s_toggles_segmentation_in_and_out_of_add_mode(self):
        for adding in (False, True):
            self.assertEqual(boxEdit.key_action(ord('s'), adding), 'toggle_seg')
            self.assertEqual(boxEdit.key_action(ord('S'), adding), 'toggle_seg')

    def test_legend_lists_s_key_only_with_segmentation(self):
        self.assertNotIn("S: toggle segmentation", " ".join(boxEdit.legend_lines(False, 2)))
        lines = boxEdit.legend_lines(False, 2, has_seg=True)
        self.assertIn("S: toggle segmentation", " ".join(lines))
        self.assertTrue(all(len(l) <= 80 for l in lines))

    def test_press_action_empty_space_draws_without_add_mode(self):
        boxes = [[10, 60, 10, 60]]
        self.assertEqual(boxEdit.press_action(boxes, 200, 200, 8, False), ('draw',))
        self.assertEqual(boxEdit.press_action([], 5, 5, 8, False), ('draw',))

    def test_press_action_add_mode_always_draws(self):
        boxes = [[10, 60, 10, 60]]
        self.assertEqual(boxEdit.press_action(boxes, 30, 30, 8, True), ('draw',))

    def test_press_action_on_box_drags_it(self):
        boxes = [[10, 60, 10, 60]]
        self.assertEqual(boxEdit.press_action(boxes, 30, 30, 8, False), ('drag', 0, 'body'))
        self.assertEqual(boxEdit.press_action(boxes, 10, 30, 8, False), ('drag', 0, 'l'))

    def test_legend_mentions_drag_to_draw_and_hints_when_empty(self):
        text = " ".join(boxEdit.legend_lines(False, 0))
        self.assertIn("Drag on empty space to draw a plant box", text)
        self.assertIn("No boxes:", text)
        text = " ".join(boxEdit.legend_lines(False, 2))
        self.assertIn("Drag on empty space to draw a plant box", text)
        self.assertNotIn("No boxes:", text)
        self.assertTrue(boxEdit.legend_lines(True, 2)[0].startswith("ADD MODE"))

    def test_is_click_identical_within_and_beyond_tolerance(self):
        self.assertTrue(boxEdit.is_click((50, 60), (50, 60), 5))
        self.assertTrue(boxEdit.is_click((50, 60), (53, 64), 5))
        self.assertFalse(boxEdit.is_click((50, 60), (56, 60), 5))
        self.assertFalse(boxEdit.is_click((50, 60), (50, 70), 5))

    def test_renumber_sorts_by_x(self):
        boxes = [[0, 10, 300, 350], [0, 10, 10, 60], [0, 10, 150, 200]]
        self.assertEqual([b[2] for b in boxEdit.renumber(boxes)], [10, 150, 300])

    def test_plant_order_single_row_left_to_right(self):
        boxes = [[100, 200, 300, 350], [100, 200, 10, 60], [100, 200, 150, 200]]
        self.assertEqual(boxEdit.plant_order(boxes), [1, 2, 0])

    def test_plant_order_empty_and_single(self):
        self.assertEqual(boxEdit.plant_order([]), [])
        self.assertEqual(boxEdit.plant_order([[5, 105, 5, 50]]), [0])
        self.assertEqual(boxEdit.renumber([]), [])

    def test_plant_order_bottom_row_first_then_top_row(self):
        # top row: y 0-100, bottom row: y 300-400 (height 100)
        boxes = [
            [0, 100, 50, 100],     # 0 top, x small
            [300, 400, 400, 450],  # 1 bottom, rightmost
            [0, 100, 600, 650],    # 2 top, x larger than every bottom box
            [300, 400, 200, 250],  # 3 bottom, left
        ]
        self.assertEqual(boxEdit.plant_order(boxes), [3, 1, 0, 2])
        self.assertEqual(boxEdit.renumber(boxes), [boxes[i] for i in [3, 1, 0, 2]])

    def test_plant_order_higher_x_lower_row_still_indexed_lower(self):
        boxes = [[0, 100, 10, 60], [300, 400, 900, 950]]
        self.assertEqual(boxEdit.plant_order(boxes), [1, 0])

    def test_plant_order_jitter_within_row_does_not_split(self):
        # height 100 -> threshold 25 px; jitter of 10 px stays one row
        boxes = [[310, 410, 300, 350], [300, 400, 10, 60], [305, 405, 150, 200]]
        self.assertEqual(boxEdit.plant_order(boxes), [1, 2, 0])

    def test_plant_order_gap_just_over_threshold_splits_rows(self):
        boxes = [[0, 100, 10, 60], [26, 126, 200, 250]]
        self.assertEqual(boxEdit.plant_order(boxes), [1, 0])
        boxes = [[0, 100, 10, 60], [25, 125, 200, 250]]
        self.assertEqual(boxEdit.plant_order(boxes), [0, 1])

    def test_plant_order_three_rows(self):
        boxes = [
            [0, 100, 500, 550],     # 0 top-right
            [150, 250, 100, 150],   # 1 middle-left
            [300, 400, 300, 350],   # 2 bottom-right
            [300, 400, 20, 70],     # 3 bottom-left
            [150, 250, 700, 750],   # 4 middle-right
            [0, 100, 40, 90],       # 5 top-left
        ]
        self.assertEqual(boxEdit.plant_order(boxes), [3, 2, 1, 4, 5, 0])

    def test_row_gap_fraction_is_named_constant(self):
        self.assertEqual(boxEdit.ROW_GAP_FRACTION, 0.25)


class PlateRoisTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        m = np.zeros((H, W), np.uint8)
        m[46:54, 96:104] = 3
        m[54:100, 99] = 1
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

    def test_getPlateROIsAndSeeds_numbers_bottom_row_first(self):
        top_left = [0, 100, 0, 100]
        bottom_right = [300, 400, 200, 300]
        bottom_left = [300, 400, 0, 100]
        out, _, ss = self.run_with([top_left, bottom_right, bottom_left],
                                   [[1, 1], [2, 2], [3, 3]])
        self.assertEqual([d['plant'] for d in out], [1, 2, 3])
        self.assertEqual([d['bounding box'] for d in out],
                         [bottom_left, bottom_right, top_left])
        self.assertEqual([d['seed'] for d in out], [[1, 1], [2, 2], [3, 3]])

    def test_getPlateROIsAndSeeds_cancel_during_origin_click_returns_none(self):
        rois = [[0, 100, 0, 100], [0, 100, 200, 300]]
        out, _, _ = self.run_with(rois, [[5, 6], None])
        self.assertIsNone(out)

    def test_getPlateROIsAndSeeds_resets_module_pos_before_every_seed_call(self):
        seen = []

        def fake_select_seed(images, segs, bbox, conf):
            seen.append(gr.pos)
            gr.pos = [3, 4]   # the real selectSeed leaves the click here
            return [3, 4]

        gr.pos = [99, 99]     # stale click from a previous run
        self.addCleanup(setattr, gr, 'pos', None)
        rois = [[0, 100, 0, 100], [0, 100, 200, 300]]
        with mock.patch.object(gr, 'selectPlantROIs', return_value=rois), \
             mock.patch.object(gr, 'selectSeed', side_effect=fake_select_seed):
            gr.getPlateROIsAndSeeds(self.conf, [self.img], [self.seg])
        self.assertEqual(seen, [None, None])

    @staticmethod
    def detail(boxes, blobs=None, merged=0, skipped=0):
        return {'boxes': boxes, 'n_seed_blobs': blobs if blobs is not None else len(boxes),
                'n_components_with_seed': len(boxes), 'n_merged_components': merged,
                'n_attached': 0, 'n_unattached': skipped}

    def patch_detail(self, **kw):
        return mock.patch.object(gr.componentROIs, 'propose_component_boxes_detail', **kw)

    def test_getPlateROIsAndSeeds_passes_proposals_and_notice(self):
        boxes = [[10, 60, 10, 60], [10, 60, 100, 150]]
        with self.patch_detail(return_value=self.detail(boxes, blobs=3, merged=1)) as pr:
            _, sp, _ = self.run_with([[0, 100, 0, 100]], [[1, 1]])
        self.assertEqual(pr.call_args[0][0], self.seg)
        self.assertEqual(sp.call_args[0][1], boxes)
        notice = sp.call_args[1]['notice']
        self.assertIn("2 boxes", notice)
        self.assertIn("seed blobs share a box", notice)

    def test_getPlateROIsAndSeeds_passes_last_segmentation_mask(self):
        _, sp, _ = self.run_with([[0, 100, 0, 100]], [[1, 1]])
        seg = sp.call_args[1]['seg']
        self.assertEqual(seg.shape, (H, W))
        self.assertEqual(int(seg[48, 98]), 3)

    def test_getPlateROIsAndSeeds_unreadable_mask_passes_no_seg(self):
        missing = os.path.join(self.dir, "nope.png")
        with mock.patch.object(gr, 'selectPlantROIs', return_value=[[0, 100, 0, 100]]) as sp, \
             mock.patch.object(gr, 'selectSeed', return_value=[1, 1]):
            gr.getPlateROIsAndSeeds(self.conf, [self.img], [missing])
        self.assertIsNone(sp.call_args[1]['seg'])

    def test_getPlateROIsAndSeeds_real_mask_gives_one_box(self):
        _, sp, _ = self.run_with([[0, 100, 0, 100]], [[1, 1]])
        self.assertEqual(len(sp.call_args[0][1]), 1)

    def test_getPlateROIsAndSeeds_no_seeds_found_starts_empty(self):
        with self.patch_detail(return_value=self.detail([])):
            _, sp, _ = self.run_with([[0, 100, 0, 100]], [[1, 1]])
        self.assertEqual(sp.call_args[0][1], [])
        self.assertIsNone(sp.call_args[1]['notice'])

    def test_getPlateROIsAndSeeds_falls_back_to_manual_when_proposal_raises(self):
        with self.patch_detail(side_effect=RuntimeError("boom")), \
             mock.patch('builtins.print') as pr:
            out, sp, _ = self.run_with([[0, 100, 0, 100]], [[1, 1]])
        self.assertIn("boom", str(pr.call_args))
        self.assertEqual(sp.call_args[0][1], [])
        self.assertIsNone(sp.call_args[1].get('notice'))
        self.assertEqual(len(out), 1)

    def test_getPlateROIsAndSeeds_unreadable_seg_mask_gives_manual_start(self):
        missing = os.path.join(self.dir, "nope.png")
        with mock.patch.object(gr, 'selectPlantROIs', return_value=[[0, 100, 0, 100]]) as sp, \
             mock.patch.object(gr, 'selectSeed', return_value=[1, 1]):
            out = gr.getPlateROIsAndSeeds(self.conf, [self.img], [missing])
        self.assertEqual(len(out), 1)
        self.assertEqual(sp.call_args[0][1], [])


class ConfigPrepTests(unittest.TestCase):
    def test_prepare_conf_manual_calibration_sets_pixel_size(self):
        from analysis.utils.configPrep import prepare_conf
        conf = prepare_conf({'Experiment': 'E', 'Images': '/x', 'plant': 1,
                             'knownDistance': 15, 'pixelDistance': 300})
        self.assertAlmostEqual(conf['pixel_size'], 0.05)

    def test_prepare_conf_sequence_label(self):
        from analysis.utils.configPrep import prepare_conf
        conf = prepare_conf({'Experiment': 'E', 'Images': '/x', 'plant': 2,
                             'knownDistance': 15, 'pixelDistance': 300})
        self.assertEqual(conf['sequenceLabel'], 'E_/x_2')
        self.assertEqual(conf['fileKey'], 'E')
        self.assertEqual(conf['Plant'], 'Arabidopsis thaliana')

    def test_set_plant_updates_label_and_fields(self):
        from analysis.utils.configPrep import set_plant
        conf = set_plant({'Experiment': 'E', 'Images': '/x', 'plant': '1'}, 4)
        self.assertEqual((conf['plant'], conf['plantField'], conf['sequenceLabel']),
                         ('4', '4', 'E_/x_4'))

    def test_prepare_conf_identifier_fallback(self):
        from analysis.utils.configPrep import prepare_conf
        conf = prepare_conf({'identifierField': 'ID', 'Images': '/x', 'plant': 1,
                             'knownDistance': 15, 'pixelDistance': 300})
        self.assertEqual(conf['Experiment'], 'ID')
        self.assertEqual(conf['fileKey'], 'ID')



class RunBatchTests(unittest.TestCase):
    PLANTS = [
        {'plant': 1, 'bounding box': [0, 10, 0, 10], 'seed': [1, 1]},
        {'plant': 2, 'bounding box': [0, 10, 20, 30], 'seed': [2, 2]},
        {'plant': 3, 'bounding box': [0, 10, 40, 50], 'seed': [3, 3]},
    ]

    def test_run_batch_runs_every_plant_with_its_own_box_and_seed(self):
        import batch_setup
        calls = []

        labels = []

        def stub(conf, replicate):
            calls.append((conf['plant'], conf['bounding box'], conf['seed'], replicate))
            labels.append((conf['sequenceLabel'], conf['plantField']))

        failed = batch_setup.run_batch({'Experiment': 'E', 'Images': '/x'}, self.PLANTS, analyse=stub)
        self.assertEqual(failed, [])
        self.assertEqual(labels, [('E_/x_1', '1'), ('E_/x_2', '2'), ('E_/x_3', '3')])
        self.assertEqual(calls, [
            ('1', [0, 10, 0, 10], [1, 1], True),
            ('2', [0, 10, 20, 30], [2, 2], True),
            ('3', [0, 10, 40, 50], [3, 3], True),
        ])

    def test_run_batch_continues_after_failure(self):
        import batch_setup
        seen = []

        def stub(conf, replicate):
            seen.append(conf['plant'])
            if conf['plant'] == '2':
                raise RuntimeError("boom")

        failed = batch_setup.run_batch({'Experiment': 'E', 'Images': '/x'}, self.PLANTS, analyse=stub)
        self.assertEqual(seen, ['1', '2', '3'])
        self.assertEqual(failed, [2])

    def test_run_batch_does_not_mutate_shared_conf(self):
        import batch_setup
        shared = {'Experiment': 'E', 'Images': '/x'}
        snapshots = []

        def stub(conf, replicate):
            snapshots.append('bounding box' in conf and conf['bounding box'])
            conf['leak'] = True

        batch_setup.run_batch(shared, self.PLANTS, analyse=stub)
        self.assertEqual(shared, {'Experiment': 'E', 'Images': '/x'})
        self.assertEqual(snapshots, [p['bounding box'] for p in self.PLANTS])


class BatchSetupMainTests(unittest.TestCase):
    def setUp(self):
        import json
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.cfg = os.path.join(self.dir, "project.json")
        with open(self.cfg, "w") as f:
            json.dump({'Experiment': 'E', 'Images': '/x', 'plant': 1,
                       'knownDistance': 15, 'pixelDistance': 300,
                       'MainFolder': self.dir}, f)

    def run_main(self, rois=None, raises=None):
        import batch_setup
        analyse = mock.Mock()
        with mock.patch.object(batch_setup, 'getImages', return_value=(['a.png'], ['a_seg.png'])), \
             mock.patch.object(batch_setup, 'getPlateROIsAndSeeds',
                               side_effect=raises, return_value=rois), \
             mock.patch.object(batch_setup, 'plantAnalysis', analyse):
            code = batch_setup.main(["--config", self.cfg])
        return code, analyse

    def _limited_lists(self, limit):
        import batch_setup, json
        with open(self.cfg) as f:
            c = json.load(f)
        if limit is not None:
            c['processingLimit'] = limit
        with open(self.cfg, 'w') as f:
            json.dump(c, f)
        imgs = ['i%d.png' % n for n in range(300)]
        segs = ['s%d.png' % n for n in range(300)]
        with mock.patch.object(batch_setup, 'getImages', return_value=(imgs, segs)), \
             mock.patch.object(batch_setup, 'getPlateROIsAndSeeds', return_value=None) as g:
            batch_setup.main(["--config", self.cfg])
        return g.call_args[0][1], g.call_args[0][2]

    def test_main_applies_processing_limit_like_single_plant(self):
        imgs, segs = self._limited_lists(2)       # 2 days * 24 * 4 = 192
        self.assertEqual((len(imgs), len(segs)), (192, 192))

    def test_main_no_limit_keeps_everything(self):
        for limit in (0, None):
            imgs, segs = self._limited_lists(limit)
            self.assertEqual((len(imgs), len(segs)), (300, 300))

    def test_main_cancel_exits_zero_without_analysing(self):
        code, analyse = self.run_main(rois=None)
        self.assertEqual(code, 0)
        analyse.assert_not_called()
        self.assertFalse(os.path.exists(os.path.join(self.dir, "batch_plants.json")))

    def test_main_error_in_roi_selection_exits_nonzero_without_analysing(self):
        import io
        from contextlib import redirect_stdout, redirect_stderr
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            code, analyse = self.run_main(raises=IndexError("empty"))
        self.assertNotEqual(code, 0)
        analyse.assert_not_called()
        self.assertIn("empty", buf.getvalue())
        self.assertFalse(os.path.exists(os.path.join(self.dir, "batch_plants.json")))

    def test_main_writes_batch_plants_and_analyses_each(self):
        import json
        plants = [{'plant': 1, 'bounding box': [0, 1, 0, 1], 'seed': [1, 1]},
                  {'plant': 2, 'bounding box': [0, 1, 2, 3], 'seed': [2, 2]}]
        code, analyse = self.run_main(rois=plants)
        self.assertEqual(code, 0)
        self.assertEqual(analyse.call_count, 2)
        with open(os.path.join(self.dir, "batch_plants.json")) as f:
            self.assertEqual(json.load(f), plants)


if __name__ == "__main__":
    unittest.main()
