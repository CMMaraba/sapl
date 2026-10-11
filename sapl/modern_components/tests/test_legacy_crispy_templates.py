from django import forms
from django.template.loader import render_to_string
from django.test import SimpleTestCase


class LegacyCrispyTemplatesTests(SimpleTestCase):
    def render(self, **options):
        class TestForm(forms.Form):
            title = forms.CharField(help_text='Ajuda <em>permitida</em>')
        form = TestForm({'title': ''})
        form.is_valid()
        return render_to_string('bootstrap3/layout/help_text_and_errors.html', {
            'field': form['title'], 'form_show_errors': True,
            'help_text_inline': False, 'error_text_inline': False, **options})

    def test_block_errors_and_help_keep_production_markup(self):
        html = self.render()
        self.assertIn('id="error_1_id_title" class="help-block"', html)
        self.assertIn('<strong>', html)
        self.assertIn('id="hint_id_title" class="help-block"', html)
        self.assertIn('Ajuda <em>permitida</em>', html)
        self.assertLess(html.index('error_1_'), html.index('hint_'))

    def test_inline_help_precedes_block_errors(self):
        html = self.render(help_text_inline=True)
        self.assertIn('<span id="hint_id_title" class="help-block"', html)
        self.assertLess(html.index('hint_'), html.index('error_1_'))

    def test_inline_errors_keep_production_markup(self):
        html = self.render(error_text_inline=True)
        self.assertIn('id="error_1_id_title"', html)
        self.assertIn('help-block', html)

    def test_errors_can_be_hidden(self):
        html = self.render(form_show_errors=False)
        self.assertNotIn('error_1_', html)
        self.assertIn('hint_id_title', html)
