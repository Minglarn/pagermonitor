import os
import unittest
import re

class TestWaterfallTelemetry(unittest.TestCase):
    def setUp(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.index_html_path = os.path.join(base_dir, 'templates', 'index.html')
        self.waterfall_js_path = os.path.join(base_dir, 'static', 'waterfall.js')
        self.waterfall_css_path = os.path.join(base_dir, 'static', 'waterfall.css')

        with open(self.index_html_path, 'r', encoding='utf-8') as f:
            self.index_html = f.read()

        with open(self.waterfall_js_path, 'r', encoding='utf-8') as f:
            self.waterfall_js = f.read()

        with open(self.waterfall_css_path, 'r', encoding='utf-8') as f:
            self.waterfall_css = f.read()

    def test_no_emojis(self):
        """Verifiera att det inte finns emojis i de uppdaterade filerna."""
        # Enkel kontroll mot typiska emoji-unicodeintervall
        emoji_pattern = re.compile(
            r'[\U0001F600-\U0001F64F]|[\U0001F300-\U0001F5FF]|[\U0001F680-\U0001F6FF]|[\U0001F700-\U0001F77F]|[\U0001F900-\U0001F9FF]|[\U00002702-\U000027B0]|[\U0001FA70-\U0001FAFF]'
        )
        self.assertIsNone(emoji_pattern.search(self.waterfall_js), "Emoji funnen i waterfall.js")
        self.assertIsNone(emoji_pattern.search(self.waterfall_css), "Emoji funnen i waterfall.css")

    def test_instrument_header_structure(self):
        """Verifiera instrument-header och ren layout."""
        self.assertIn('class="activity-ribbon-panel collapsed"', self.index_html)
        self.assertIn('id="activityRibbonPanel"', self.index_html)
        self.assertIn('class="inst-header" onclick="toggleActivityRibbon()"', self.index_html)
        self.assertIn('class="inst-controls" onclick="event.stopPropagation()"', self.index_html)
        self.assertIn('RF ACTIVITY MONITOR', self.index_html)
        self.assertIn('60 MIN', self.index_html)
        self.assertIn('TOTALT:', self.index_html)
        self.assertIn('TAKT:', self.index_html)
        self.assertIn('AKTIVA KANALER:', self.index_html)
        self.assertIn('HÖGST -&gt; 0 MSGS', self.index_html)
        self.assertIn('TYSTA (0) FÖRST', self.index_html)
        self.assertIn('FREKVENS', self.index_html)
        self.assertIn('id="wfCollapseIndicator">[v VISA]</span>', self.index_html)

    def test_8_columns_in_head_and_viewport(self):
        """Verifiera tabellhuvud och kolumner."""
        self.assertIn('wf-head', self.index_html)
        self.assertIn('VAL', self.index_html)
        self.assertIn('PROTO', self.index_html)
        self.assertIn('FREKVENS', self.index_html)
        self.assertIn('MOTTAGARE / KANAL', self.index_html)
        self.assertIn('-60 min', self.index_html)
        self.assertIn('NU (0m)', self.index_html)
        self.assertIn('SENAST', self.index_html)
        self.assertIn('MSG/MIN', self.index_html)
        self.assertIn('VOLYM (1H)', self.index_html)
        self.assertIn('class="wf-scroll-viewport" id="waterfallChannels"', self.index_html)

    def test_css_dimensions_and_intensity_heatbars(self):
        """Verifiera exakta CSS-mått för 10 frekvensrader och färggradienter."""
        self.assertIn('30px 60px 96px 130px 1fr 72px 86px 95px', self.waterfall_css)
        self.assertIn('height: 360px', self.waterfall_css)
        self.assertIn('max-height: 360px', self.waterfall_css)
        self.assertIn('overflow-y: scroll', self.waterfall_css)
        self.assertIn('height: 36px', self.waterfall_css)
        self.assertIn('heat-low', self.waterfall_css)
        self.assertIn('heat-med', self.waterfall_css)
        self.assertIn('heat-burst', self.waterfall_css)
        self.assertIn('is-silent', self.waterfall_css)

    def test_waterfall_js_methods(self):
        """Verifiera att nödvändiga metoder exponeras och hanteras i JS."""
        self.assertIn('window.WaterfallManager', self.waterfall_js)
        self.assertIn('toggleCollapse', self.waterfall_js)
        self.assertIn('setSort', self.waterfall_js)
        self.assertIn('toggleChannelFilter', self.waterfall_js)
        self.assertIn('clearAllFilters', self.waterfall_js)
        self.assertIn('hasActiveFilter', self.waterfall_js)
        self.assertIn('isRowMatchingFilter', self.waterfall_js)
        self.assertIn('INGA MEDDELANDEN MOTTAGNA SENASTE 60 MIN', self.waterfall_js)

if __name__ == '__main__':
    unittest.main()
