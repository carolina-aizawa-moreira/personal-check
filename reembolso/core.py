import io
import re
import unicodedata
from datetime import date
from PIL import Image, ImageOps, ImageSequence
from pypdf import PdfReader

PDF = "application/pdf"
IMAGES = {"image/jpeg", "image/png", "image/tiff", "image/webp", "image/bmp"}


def slug(value):
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()


def extract_date(text):
    for match in re.finditer(r"\b(\d{4})[-_](\d{2})[-_](\d{2})\b|\b(\d{2})[./_-](\d{2})[./_-](\d{4})\b", text):
        parts = match.groups()
        y, m, d = parts[:3] if parts[0] else (parts[5], parts[4], parts[3])
        try:
            return date(int(y), int(m), int(d)).isoformat()
        except ValueError:
            continue
    return ""


def pdf_bytes(data, mime):
    if mime == PDF:
        PdfReader(io.BytesIO(data))
        return data
    if mime not in IMAGES:
        raise ValueError("Formato não suportado: " + mime)
    with Image.open(io.BytesIO(data)) as source:
        frames = [ImageOps.exif_transpose(frame.copy()).convert("RGB") for frame in ImageSequence.Iterator(source)]
    output = io.BytesIO()
    frames[0].save(output, format="PDF", save_all=True, append_images=frames[1:])
    return output.getvalue()


def text_from_pdf(data):
    return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages)


def propose(file, text, current_category, config):
    haystack = file["name"] + "\n" + text
    matches = {rule["category"] for rule in config["rules"] if re.search(rule["pattern"], haystack, re.I)}
    category = next(iter(matches)) if len(matches) == 1 else current_category if not matches else ""
    when = extract_date(file["name"]) or extract_date(text)
    kind = "nota-fiscal" if re.search(r"nota\s*fiscal", haystack, re.I) else "recibo" if re.search(r"recibo", haystack, re.I) else "documento"
    target = config["categories"].get(category, "")
    name = f"{when}_{slug(category)}_{kind}_{file['id']}.pdf" if when and target else ""
    return {"source_id": file["id"], "source_name": file["name"], "source_modified": file["modifiedTime"],
            "source_mime": file["mimeType"], "date": when, "category": category,
            "document_type": kind, "provider": "", "amount": "", "destination_id": target,
            "name": name, "approved": False,
            "auto_eligible": bool(name and category == current_category and len(matches) <= 1 and extract_date(file["name"]) and re.search(r"recibo|nota[ _-]*fiscal", file["name"], re.I)),
            "note": "Revise data, categoria e nome. Preencha profissional e valor quando disponíveis." if name else "Informe data e categoria; classificação insuficiente ou ambígua."}


def safe_cell(value):
    value = str(value)
    return "'" + value if value.startswith(("=", "+", "-", "@")) else value
