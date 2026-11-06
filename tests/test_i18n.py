import unittest

from agent_umimiy import i18n


class I18nTest(unittest.TestCase):
    def tearDown(self):
        i18n.set_lang("uz")  # testlar bir-biriga ta'sir qilmasin

    def test_default_is_uzbek_passthrough(self):
        self.assertEqual(i18n.get_lang(), "uz")
        self.assertEqual(i18n.t("Saqlash"), "Saqlash")
        self.assertEqual(i18n.t("Nomalum matn"), "Nomalum matn")

    def test_switch_to_russian(self):
        i18n.set_lang("ru")
        self.assertEqual(i18n.t("Saqlash"), "Сохранить")
        self.assertEqual(i18n.t("Avtomatik"), "Автоматический")

    def test_switch_to_english(self):
        i18n.set_lang("en")
        self.assertEqual(i18n.t("Saqlash"), "Save")
        self.assertEqual(i18n.t("Kengash"), "Council")

    def test_unknown_key_falls_back_to_source(self):
        i18n.set_lang("ru")
        self.assertEqual(i18n.t("Bunday kalit yo'q"), "Bunday kalit yo'q")

    def test_invalid_lang_ignored(self):
        i18n.set_lang("ru")
        i18n.set_lang("xx")  # noto'g'ri — e'tiborsiz
        self.assertEqual(i18n.get_lang(), "ru")

    def test_empty_string(self):
        i18n.set_lang("en")
        self.assertEqual(i18n.t(""), "")

    def test_all_entries_have_all_languages(self):
        for src, entry in i18n.TR.items():
            self.assertIn("ru", entry, f"ru yo'q: {src}")
            self.assertIn("en", entry, f"en yo'q: {src}")


if __name__ == "__main__":
    unittest.main()
