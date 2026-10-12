import unittest

from PIL import Image, ImageOps

from sapl.modern_components.image_geometry import (
    box_to_oriented,
    box_to_stored,
    max_cropping,
    oriented_size,
    parse_crop_box,
    serialize_crop_box,
)


def stored_image_with_marker(orientation, size=(40, 30), box=(5, 3, 17, 11)):
    """Stored image whose only white pixels form `box`, tagged with EXIF."""
    image = Image.new("L", size, 0)
    image.paste(255, box)
    image.getexif()[0x0112] = orientation
    image.info["exif"] = image.getexif().tobytes()
    return image


def white_box(image):
    return list(image.point(lambda value: 255 if value > 127 else 0).getbbox())


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


    def test_oriented_size_swaps_only_rotated_orientations(self):
        for orientation in range(1, 9):
            expected = (30, 40) if orientation >= 5 else (40, 30)
            self.assertEqual(oriented_size(40, 30, orientation), expected)
        self.assertEqual(oriented_size(40, 30, 99), (40, 30))

    def test_box_conversion_matches_pillow_exif_transpose(self):
        stored_box = [5, 3, 17, 11]
        for orientation in range(1, 9):
            with self.subTest(orientation=orientation):
                image = stored_image_with_marker(orientation, box=tuple(stored_box))
                displayed = ImageOps.exif_transpose(image)
                expected = white_box(displayed)
                self.assertEqual(box_to_oriented(stored_box, 40, 30, orientation), expected)
                self.assertEqual(box_to_stored(expected, 40, 30, orientation), stored_box)

    def test_box_conversion_ignores_invalid_orientation(self):
        self.assertEqual(box_to_oriented([1, 2, 3, 4], 40, 30, None), [1, 2, 3, 4])
        self.assertIsNone(box_to_stored(None, 40, 30, 6))


if __name__ == "__main__":
    unittest.main()
