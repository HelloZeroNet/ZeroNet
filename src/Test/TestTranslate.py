import os

from Translate import Translate

class TestTranslate:
    def testTranslateStrict(self):
        translate = Translate()
        data = """
            translated = _("original")
            not_translated = "original"
        """
        data_translated = translate.translateData(data, {"_(original)": "translated"})
        assert 'translated = _("translated")' in data_translated
        assert 'not_translated = "original"' in data_translated


    def testTranslateStrictNamed(self):
        translate = Translate()
        data = """
            translated = _("original", "original named")
            translated_other = _("original", "original other named")
            not_translated = "original"
        """
        data_translated = translate.translateData(data, {"_(original, original named)": "translated"})
        assert 'translated = _("translated")' in data_translated
        assert 'not_translated = "original"' in data_translated
