from pathlib import Path

from crispy_forms.layout import Row
from django.template.loader import get_template, render_to_string
from django.test import SimpleTestCase
from django.utils.safestring import mark_safe


class CrispyRowCompatibilityTests(SimpleTestCase):
    def test_row_uses_original_grid_and_preserves_attributes(self):
        template = get_template('bootstrap4/layout/row.html')
        self.assertTrue(Path(template.origin.name).is_relative_to(
            Path(__file__).resolve().parents[2] / 'templates'))

        row = Row('field', css_id='row-probe', css_class='extra-row',
                  data_probe='kept')
        html = render_to_string('bootstrap4/layout/row.html', {
            'div': row,
            'fields': mark_safe('<span id="field-probe"></span>'),
        })
        self.assertIn('class="row extra-row"', html)
        self.assertIn('id="row-probe"', html)
        self.assertIn('data-probe="kept"', html)
        self.assertIn('<span id="field-probe"></span>', html)
        self.assertNotIn('form-row', html)
