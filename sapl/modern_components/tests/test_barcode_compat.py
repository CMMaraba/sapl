import base64

from django.test import SimpleTestCase
from reportlab.graphics.barcode import createBarcodeDrawing

from sapl.utils import create_barcode


class BarcodeCompatibilityTests(SimpleTestCase):
    @staticmethod
    def png_dimensions(encoded):
        png = base64.b64decode(encoded)
        if png[:8] != b"\x89PNG\r\n\x1a\n":
            raise AssertionError("barcode output is not a PNG")
        return (int.from_bytes(png[16:20], "big"),
                int.from_bytes(png[20:24], "big"))

    def test_normal_protocol_barcode_preserves_requested_dpi(self):
        drawing = createBarcodeDrawing(
            "Code128", value=b"123456", barWidth=170, height=50,
            fontSize=2, humanReadable=True)
        self.assertEqual(
            self.png_dimensions(create_barcode("123456", 170, 50, 72)),
            (int(round(drawing.width)), int(round(drawing.height))))

    def test_long_receipt_barcode_renders_within_cairo_surface_limit(self):
        drawing = createBarcodeDrawing(
            "Code128", value=b"P" * 68, barWidth=100, height=500,
            fontSize=2, humanReadable=True)
        width, height = self.png_dimensions(
            create_barcode("P" * 68, width=100, height=500, dpi=100))
        self.assertGreater(width, 0)
        self.assertGreater(height, 0)
        self.assertLessEqual(max(width, height), 16000)
        self.assertLess(abs(width / float(height) -
                             drawing.width / drawing.height), 2.0)
