import io
from PIL import Image
from pypdf import PdfReader
from reembolso.core import extract_date, pdf_bytes, propose, safe_cell

CONFIG = {"categories": {"Consulta": "folder-c", "Exame": "folder-e"}, "rules": [{"pattern": "consulta", "category": "Consulta"}, {"pattern": "exame", "category": "Exame"}]}

def file(name):
    return {"id": "abc", "name": name, "modifiedTime": "2026-10-08T00:00:00Z", "mimeType": "application/pdf"}

def test_dates():
    assert extract_date("recibo 31-02-2026 08/10/2026") == "2026-10-08"
    assert extract_date("2026-10-08") == "2026-10-08"
    assert extract_date("documento") == ""

def test_ambiguous_not_automatic():
    p = propose(file("2026-10-08 recibo consulta exame"), "", "Consulta", CONFIG)
    assert not p["auto_eligible"]
    assert not p["destination_id"]

def test_clear_and_incomplete():
    p = propose(file("2026-10-08 recibo consulta"), "", "Consulta", CONFIG)
    assert p["auto_eligible"]
    assert p["name"] == "2026-10-08_consulta_recibo_abc.pdf"
    assert not p["approved"]
    assert not propose(file("recibo consulta"), "", "Consulta", CONFIG)["auto_eligible"]
    assert not propose(file("2026-10-08 recibo consulta"), "", "", CONFIG)["auto_eligible"]

def test_image_pdf():
    image = Image.new("RGB", (100, 100), "white")
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    result = pdf_bytes(buffer.getvalue(), "image/png")
    assert len(PdfReader(io.BytesIO(result)).pages) == 1
    assert pdf_bytes(result, "application/pdf") == result

def test_multiframe_pdf():
    first = Image.new("RGB", (50, 50), "white")
    second = Image.new("RGB", (50, 50), "black")
    buffer = io.BytesIO()
    first.save(buffer, "TIFF", save_all=True, append_images=[second])
    assert len(PdfReader(io.BytesIO(pdf_bytes(buffer.getvalue(), "image/tiff"))).pages) == 2

def test_formula_is_text():
    assert safe_cell("=IMPORTXML()") == "'=IMPORTXML()"
