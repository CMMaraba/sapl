import unittest

from sapl.modern_components.image_geometry import (
    max_cropping,
    parse_crop_box,
    serialize_crop_box,
)


class CropGeometryTests(unittest.TestCase):
    def test_legacy_box_uses_bottom_right_coordinates(self):
        box, full = parse_crop_box("12,20,212,120")
        self.assertEqual(box, (12, 20, 212, 120))
        self.assertFalse(full)
        self.assertEqual(serialize_crop_box(box), "12,20,212,120")

    def test_fullsize_marker_round_trips_without_changing_coordinates(self):
        box, full = parse_crop_box("-12,20,212,120")
        self.assertEqual(box, (12, 20, 212, 120))
        self.assertTrue(full)
        self.assertEqual(serialize_crop_box(box, fullsize=True), "-12,20,212,120")

    def test_centered_crop_is_legacy_xyxy_format(self):
        self.assertEqual(max_cropping(100, 100, 400, 200), [100, 0, 300, 200])
        self.assertEqual(max_cropping(100, 100, 200, 400), [0, 100, 200, 300])

    def test_free_crop_preserves_full_image(self):
        self.assertEqual(max_cropping(128, 128, 301, 151, free_crop=True), [0, 0, 301, 151])

    def test_invalid_boxes_are_rejected(self):
        self.assertEqual(parse_crop_box("0,0,0,2"), (None, False))
        self.assertEqual(parse_crop_box("nonsense"), (None, False))


if __name__ == "__main__":
    unittest.main()
