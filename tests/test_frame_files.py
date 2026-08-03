"""The frame file readers: CSV was already proven, .xlsx joins it here.

The .xlsx fixture is built by hand with zipfile — no spreadsheet library on
either side. What the test writes is exactly the subset the reader claims to
understand: first worksheet, shared and inline strings, a header row.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from researchcall.sampling import read_frame_file, read_xlsx_frame


CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
</Types>"""

ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

WORKBOOK = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="Frame" sheetId="1" r:id="rId1"/></sheets></workbook>"""

WORKBOOK_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>"""

SHARED = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="4" uniqueCount="4">
<si><t>external_ref</t></si><si><t>phone</t></si><si><t>p-001</t></si><si><t>p-002</t></si></sst>"""

SHEET = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>
<row r="2"><c r="A2" t="s"><v>2</v></c><c r="B2" t="inlineStr"><is><t>+15550100011</t></is></c></row>
<row r="3"><c r="A3" t="s"><v>3</v></c><c r="B3" t="inlineStr"><is><t>+15550100012</t></is></c></row>
<row r="4"><c r="A4"/><c r="B4"/></row>
</sheetData></worksheet>"""


def write_xlsx(path: Path, sheet_xml: str = SHEET, shared_xml: str = SHARED) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", CONTENT_TYPES)
        archive.writestr("_rels/.rels", ROOT_RELS)
        archive.writestr("xl/workbook.xml", WORKBOOK)
        archive.writestr("xl/_rels/workbook.xml.rels", WORKBOOK_RELS)
        archive.writestr("xl/sharedStrings.xml", shared_xml)
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)


class XlsxFrameTestCase(unittest.TestCase):
    def setUp(self):
        self.directory = Path(tempfile.mkdtemp())
        self.path = self.directory / "frame.xlsx"

    def test_reads_header_shared_and_inline_strings_and_skips_the_empty_row(self):
        write_xlsx(self.path)
        rows = read_xlsx_frame(self.path, "external_ref", "phone")
        self.assertEqual(
            rows, [("p-001", "+15550100011"), ("p-002", "+15550100012")]
        )

    def test_a_missing_column_is_named_in_the_error(self):
        write_xlsx(self.path)
        with self.assertRaises(ValueError) as caught:
            read_xlsx_frame(self.path, "external_ref", "telefon")
        self.assertIn("telefon", str(caught.exception))

    def test_a_workbook_without_a_worksheet_is_refused(self):
        with zipfile.ZipFile(self.path, "w") as archive:
            archive.writestr("[Content_Types].xml", CONTENT_TYPES)
        with self.assertRaises(ValueError):
            read_xlsx_frame(self.path, "external_ref", "phone")

    def test_read_frame_file_dispatches_on_the_suffix(self):
        write_xlsx(self.path)
        via_dispatcher = read_frame_file(self.path, "external_ref", "phone")
        self.assertEqual(len(via_dispatcher), 2)

        csv_path = self.directory / "frame.csv"
        csv_path.write_text(
            "external_ref,phone\np-009,+15550100099\n", encoding="utf-8"
        )
        self.assertEqual(
            read_frame_file(csv_path, "external_ref", "phone"),
            [("p-009", "+15550100099")],
        )


if __name__ == "__main__":
    unittest.main()
