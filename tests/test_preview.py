import tempfile
import unittest
from pathlib import Path

from agent_umimiy import preview, writer


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())

    def test_html_is_served_as_written(self):
        path = writer.text_file(self.d, "sahifa.html", "<h1>Salom</h1><script>1</script>")
        self.assertEqual(preview.page(path), "<h1>Salom</h1><script>1</script>")

    def test_tables_are_escaped_and_show_formulas(self):
        path = writer.xlsx(self.d, "j", [{"name": "A<b>", "rows": [["Nom", "Soni"], ["<script>x</script>", 5], ["Jami", "=SUM(B2:B2)"]]},
                                         {"name": "Ikkinchi", "rows": [["x"]]}])
        page = preview.page(path)
        self.assertIn("&lt;script&gt;x&lt;/script&gt;", page)
        self.assertNotIn("<script>", page)
        self.assertIn("<td class=n>5</td>", page)
        self.assertIn("=SUM(B2:B2)", page)
        self.assertIn("<h2>A&lt;b&gt;</h2>", page)  # varaq nomi ham ekranlanadi
        self.assertIn("<h2>Ikkinchi</h2>", page)
        csv = writer.text_file(self.d, "a.csv", "Ism,Yosh\nАли,30\n")
        self.assertIn("<th>Ism</th>", preview.page(csv))
        self.assertIn("<td>Али</td>", preview.page(csv))

    def test_long_tables_are_cut_and_text_is_escaped(self):
        path = writer.text_file(self.d, "katta.csv", "n\n" + "\n".join(str(i) for i in range(900)))
        page = preview.page(path)
        self.assertEqual(page.count("<tr>"), preview.MAX_ROWS)
        self.assertIn("Birinchi 500 qator", page)
        note = writer.text_file(self.d, "a.md", "# <b>sarlavha</b>")
        self.assertIn("<pre># &lt;b&gt;sarlavha&lt;/b&gt;</pre>", preview.page(note))

    def test_word_files_have_no_preview(self):
        self.assertIsNone(preview.page(writer.docx(self.d, "xat", "# Salom")))

    def test_sandbox_policy_blocks_app_access(self):
        self.assertTrue(preview.CSP.startswith("sandbox allow-scripts"))
        self.assertNotIn("allow-same-origin", preview.CSP)
        self.assertIn("default-src 'none'", preview.CSP)
        self.assertNotIn("connect-src", preview.CSP)  # default-src 'none': sahifa hech qayerga so'rov yubora olmaydi
        self.assertIn("img-src data: blob:", preview.CSP)
        self.assertNotIn("img-src data: blob: https:", preview.CSP)


if __name__ == "__main__":
    unittest.main()
