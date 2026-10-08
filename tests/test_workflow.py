import argparse
import io
import json
from PIL import Image
import pytest
from reembolso import cli
from reembolso.core import propose
from pypdf import PdfReader


def setup(tmp_path, monkeypatch):
    config = {"root_folder_id": "root", "spreadsheet_id": "sheet", "categories": {"Consulta": "folder"}, "rules": [{"pattern": "consulta", "category": "Consulta"}]}
    source = {"id": "source", "name": "2026-10-08 recibo consulta.png", "mimeType": "image/png", "modifiedTime": "v1", "parents": ["folder"]}
    files = [source]
    writes, rows = [], {}
    data = io.BytesIO()
    Image.new("RGB", (32, 32), "white").save(data, "PNG")
    monkeypatch.setattr(cli, "clients", lambda: (object(), object()))
    monkeypatch.setattr(cli, "inventory", lambda *args: (files, {"root", "folder"}))
    monkeypatch.setattr(cli, "download", lambda *args: data.getvalue())
    def copy(drive, item, pdf):
        assert len(PdfReader(io.BytesIO(pdf)).pages) == 1
        writes.append(item)
        files.append({"id": "copy", "appProperties": {"personalCheckSource": "source", "personalCheckModified": "v1"}})
        return "copy"
    monkeypatch.setattr(cli, "normalized_copy", copy)
    monkeypatch.setattr(cli, "sync_row", lambda sheets, config, item, identifier: rows.update({item["source_id"]: identifier}))
    cp, pp = tmp_path / "config.json", tmp_path / "plan.json"
    cp.write_text(json.dumps(config))
    args = argparse.Namespace(command="scan", config=str(cp), plan=str(pp), auto_clear=False)
    return args, pp, source, writes, rows


def test_review_auto_and_reapply(tmp_path, monkeypatch):
    args, plan, source, writes, rows = setup(tmp_path, monkeypatch)
    cli.run(args)
    assert not writes
    args.command = "apply"
    cli.run(args)
    assert not writes
    args.auto_clear = True
    cli.run(args)
    cli.run(args)
    assert len(writes) == 1
    assert rows == {"source": "copy"}
    assert source["name"].endswith(".png")


def test_stale_source_blocks_before_writes(tmp_path, monkeypatch):
    args, plan, source, writes, rows = setup(tmp_path, monkeypatch)
    cli.run(args)
    source["modifiedTime"] = "v2"
    args.command = "apply"
    args.auto_clear = True
    with pytest.raises(ValueError, match="alterado"):
        cli.run(args)
    assert not writes
    assert not rows


def test_scan_preserves_review(tmp_path, monkeypatch):
    args, plan, source, writes, rows = setup(tmp_path, monkeypatch)
    cli.run(args)
    original = plan.read_text()
    with pytest.raises(ValueError, match="já existe"):
        cli.run(args)
    assert plan.read_text() == original


def test_modified_destination_requires_review(tmp_path, monkeypatch):
    args, plan, source, writes, rows = setup(tmp_path, monkeypatch)
    cli.run(args)
    items = json.loads(plan.read_text())
    items[0]["destination_id"] = "outside"
    items[0]["approved"] = True
    plan.write_text(json.dumps(items))
    args.command = "apply"
    with pytest.raises(ValueError, match="Destino"):
        cli.run(args)
    assert not writes
