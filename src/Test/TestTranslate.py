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

    def testTranslateUtf8(self):
        translate = Translate()
        data = """
            greeting = "Hi again árvztűrőtökörfúrógép!"
        """
        data_translated = translate.translateData(data, {"Hi again árvztűrőtökörfúrógép!": "Üdv újra árvztűrőtökörfúrógép!"})
        assert data_translated == """
            greeting = "Üdv újra árvztűrőtökörfúrógép!"
        """

    def testTranslateEscape(self):
        _ = Translate()
        _["Hello"] = "Szia"

        # Simple escaping
        data = "{_[Hello]} {username}!"
        username = "Hacker<script>alert('boom')</script>"
        data_translated = _(data)
        assert 'Szia' in data_translated
        assert '<' not in data_translated
        assert data_translated == "Szia Hacker&lt;script&gt;alert(&#x27;boom&#x27;)&lt;/script&gt;!"

        # Escaping dicts
        user = {"username": "Hacker<script>alert('boom')</script>"}
        data = "{_[Hello]} {user[username]}!"
        data_translated = _(data)
        assert 'Szia' in data_translated
        assert '<' not in data_translated
        assert data_translated == "Szia Hacker&lt;script&gt;alert(&#x27;boom&#x27;)&lt;/script&gt;!"

        # Escaping lists
        users = [{"username": "Hacker<script>alert('boom')</script>"}]
        data = "{_[Hello]} {users[0][username]}!"
        data_translated = _(data)
        assert 'Szia' in data_translated
        assert '<' not in data_translated
        assert data_translated == "Szia Hacker&lt;script&gt;alert(&#x27;boom&#x27;)&lt;/script&gt;!"
