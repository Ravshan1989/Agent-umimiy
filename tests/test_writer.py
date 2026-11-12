import json
import tempfile
import unittest
from pathlib import Path

from agent_umimiy import docs, writer
from agent_umimiy.orchestrator import Orchestrator
from agent_umimiy.providers import build_agent
from agent_umimiy.tools import Context, Toolbox, available
from tests.test_tools import serve

MARKDOWN = """# Сайёр қабуллар ҳисоботи

Bu **muhim** hujjat, [sayt](https://a.uz) va `kod`.

- bir
- ikki

1. birinchi

| Tuman | Soni |
|---|---|
| Zangiota | 12 |

```
print(1)
```
"""


class WriterTests(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())

    def test_docx_from_markdown(self):
        path = writer.docx(self.d, "Hisobot.docx", MARKDOWN)
        text = docs.extract_text(path)
        for part in ("Сайёр қабуллар ҳисоботи", "Bu muhim hujjat, sayt (https://a.uz) va kod.", "bir", "birinchi",
                     "| Tuman | Soni |", "| Zangiota | 12 |", "print(1)"):
            self.assertIn(part, text)
        self.assertNotIn("**", text)
        self.assertNotIn("|---|", text)

    def test_xlsx_keeps_numbers_and_formulas(self):
        from openpyxl import load_workbook
        path = writer.xlsx(self.d, "jadval", [{"name": "Tuman/lar", "rows": [["Tuman", "Soni"], ["Zangiota", 12], ["Jami", "=SUM(B2:B2)"]]},
                                              {"rows": [["bo'sh"]]}])
        book = load_workbook(path)
        self.assertEqual(book.sheetnames, ["Tuman_lar", "Varaq2"])
        ws = book["Tuman_lar"]
        self.assertEqual((ws["B2"].value, ws["B3"].value, ws["A1"].font.bold, ws.freeze_panes), (12, "=SUM(B2:B2)", True, "A2"))
        for bad in ([], "x", [{"rows": "x"}], [{"name": "a", "rows": []}, {"name": "a", "rows": []}]):
            with self.assertRaises(writer.WriteError):
                writer.xlsx(self.d, "x", bad)

    def test_names_are_safe_and_never_overwrite(self):
        first = writer.text_file(self.d, "../../maxfiy.txt", "bir")
        second = writer.text_file(self.d, "maxfiy.txt", "ikki")
        self.assertEqual((first.parent, first.name, second.name), (self.d, "maxfiy.txt", "maxfiy (2).txt"))
        self.assertEqual(first.read_text(), "bir")
        self.assertEqual(writer.text_file(self.d, "a.csv", "ў,b").read_bytes()[:3], b"\xef\xbb\xbf")  # Excel uchun BOM
        with self.assertRaises(writer.WriteError):
            writer.text_file(self.d, "dastur.exe", "x")


class CreateToolTests(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.events = []
        self.ctx = Context(web=False, files_dir=str(self.d), emit=lambda *a: self.events.append(a))

    def test_tools_only_with_files_dir(self):
        names = {t.name for t in available(self.ctx)}
        self.assertTrue({"create_document", "create_spreadsheet"} <= names)
        self.assertNotIn("write_file", names)  # loyiha papkasi yo'q
        self.assertFalse(Context(web=False).active)
        self.assertNotIn("create_document", {t.name for t in available(Context())})

    def test_create_and_show(self):
        tb = Toolbox(self.ctx, "a")
        out, err = tb.run("create_document", {"name": "xat.docx", "content": "# Salom"})
        self.assertFalse(err, out)
        out, err = tb.run("create_spreadsheet", {"name": "j", "sheets": [{"rows": [["a"], [1]]}]})
        self.assertFalse(err, out)
        self.assertEqual([(k, Path(p).name) for _, k, p in self.events], [("file", "xat.docx"), ("file", "j.xlsx")])
        self.assertTrue(all(Path(p).is_file() for _, _, p in self.events))
        out, err = tb.run("create_spreadsheet", {"name": "j", "sheets": "xato"})
        self.assertTrue(err)

    def test_agent_loop_creates_excel(self):
        sheets = [{"name": "Hisobot", "rows": [["Oy", "Soni"], ["Yanvar", 5]]}]
        srv, seen = serve([
            {"content": [{"type": "tool_use", "id": "1", "name": "create_spreadsheet", "input": {"name": "hisobot", "sheets": sheets}}]},
            {"content": [{"type": "text", "text": "Tayyor"}]}])
        o = Orchestrator([build_agent({"name": "c", "type": "anthropic", "api_key": "k", "base_url": f"http://127.0.0.1:{srv.server_port}"})])
        o.ctx.web, o.ctx.files_dir = False, str(self.d)
        self.assertEqual(o.run("excel qil", "single")[0].text, "Tayyor")
        self.assertIn("create_spreadsheet", seen[0]["system"])
        self.assertIn("hisobot.xlsx", json.dumps(seen[1]["messages"][-1], ensure_ascii=False))
        self.assertIn("Yanvar", docs.extract_text(self.d / "hisobot.xlsx"))


if __name__ == "__main__":
    unittest.main()
