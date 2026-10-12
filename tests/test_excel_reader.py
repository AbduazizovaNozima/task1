import io
from zipfile import ZipFile

import pytest

from app.adapters.excel_reader import read_qa_sheet
from app.domain.errors import InvalidSpreadsheetError
from app.domain.models import QAPair
from tests.fakes import xlsx


def test_reads_named_columns_and_reports_incomplete_rows() -> None:
    data = xlsx([["answer", "question"], ["DXM orqali.", "Pasport qanday olinadi?"], [None, "Incomplete"]])
    sheet = read_qa_sheet(io.BytesIO(data))
    assert sheet.pairs == [QAPair(question="Pasport qanday olinadi?", answer="DXM orqali.")]
    assert [(row.row, row.reason) for row in sheet.skipped] == [(3, "empty answer")]


def test_missing_required_columns_explains_the_error() -> None:
    with pytest.raises(InvalidSpreadsheetError, match="question, answer"):
        read_qa_sheet(io.BytesIO(xlsx([["savol", "javob"]])))


@pytest.mark.parametrize("member", [None, "xl/workbook.xml", "xl/worksheets/sheet1.xml"])
def test_malformed_workbook_or_lazy_sheet_xml_is_rejected(member: str | None) -> None:
    data = b"not a workbook"
    if member:
        with io.BytesIO(xlsx([["question", "answer"]])) as source, io.BytesIO() as malformed:
            with ZipFile(source) as original, ZipFile(malformed, "w") as result:
                for name in original.namelist():
                    result.writestr(name, b"<broken" if name == member else original.read(name))
            data = malformed.getvalue()
    with pytest.raises(InvalidSpreadsheetError):
        read_qa_sheet(io.BytesIO(data))
