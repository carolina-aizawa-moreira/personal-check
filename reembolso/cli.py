import argparse
import json
from pathlib import Path
from .core import PDF, IMAGES, pdf_bytes, text_from_pdf, propose
from .google import clients, inventory, download, normalized_copy, sync_row


def run(args):
    if args.command == "login":
        clients(login=True)
        print("Autorização salva localmente em .secrets/token.json.")
        return
    config = json.loads(Path(args.config).read_text())
    drive, sheets = clients()
    files, folders = inventory(drive, config["root_folder_id"])
    if args.command == "folders":
        details = [drive.files().get(fileId=f, fields="id,name").execute() for f in sorted(folders)]
        print(json.dumps(details, ensure_ascii=False, indent=2))
        return
    if args.command == "create-sheet":
        if config.get("spreadsheet_id") and config["spreadsheet_id"] != "ID_DA_PLANILHA":
            raise ValueError("Planilha já configurada; não será substituída.")
        result = sheets.spreadsheets().create(body={"properties": {"title": "Controle de reembolsos"}, "sheets": [{"properties": {"title": config.get("sheet_title", "Documentos")}}]}, fields="spreadsheetId").execute()
        config["spreadsheet_id"] = result["spreadsheetId"]
        Path(args.config).write_text(json.dumps(config, ensure_ascii=False, indent=2))
        print("Planilha criada; ID salvo na configuração local.")
        return
    if not set(config["categories"].values()).issubset(folders):
        raise ValueError("Todas as categorias devem ser subpastas da raiz configurada.")
    copies = {(f.get("appProperties", {}).get("personalCheckSource"), f.get("appProperties", {}).get("personalCheckModified")): f["id"] for f in files if f.get("appProperties", {}).get("personalCheckSource")}
    originals = {f["id"]: f for f in files if not f.get("appProperties", {}).get("personalCheckSource")}
    if args.command == "scan":
        plan = []
        for file in originals.values():
            if file["mimeType"] not in {PDF, *IMAGES}:
                continue
            if (file["id"], file["modifiedTime"]) in copies:
                continue
            text = ""
            note = ""
            if file["mimeType"] == PDF:
                try:
                    text = text_from_pdf(download(drive, file["id"]))
                except Exception:
                    note = "Não foi possível ler o PDF. Verifique o arquivo antes de aprovar."
            categories = [category for category, folder in config["categories"].items() if folder in file.get("parents", [])]
            item = propose(file, text, categories[0] if len(categories) == 1 else "", config)
            if note:
                item["note"] = note
                item["auto_eligible"] = False
            plan.append(item)
        path = Path(args.plan)
        if path.exists():
            raise ValueError("Plano já existe; preserve sua revisão ou use --plan com outro caminho.")
        path.write_text(json.dumps(plan, ensure_ascii=False, indent=2))
        path.chmod(0o600)
        print(f"{len(plan)} documentos no plano. Nenhuma alteração remota realizada.")
    else:
        plan = json.loads(Path(args.plan).read_text())
        # Recompute eligibility: never trust the editable auto_eligible flag.
        for item in plan:
            if item["source_id"] in originals:
                file = originals[item["source_id"]]
                current = next((k for k, v in config["categories"].items() if v in file.get("parents", [])), "")
                checked = propose(file, "", current, config)
                item["auto_eligible"] = item.get("auto_eligible", False) and checked["auto_eligible"] and all(item.get(k) == checked.get(k) for k in ("name", "date", "category", "destination_id"))
        # Validate the whole approved plan before any writes.
        for item in plan:
            if not (item.get("approved") or (args.auto_clear and item.get("auto_eligible"))):
                continue
            file = originals.get(item["source_id"])
            if not file or file["modifiedTime"] != item["source_modified"]:
                raise ValueError("Original removido ou alterado desde a revisão; gere um novo plano.")
            if item["destination_id"] != config["categories"].get(item["category"]) or not item["name"].lower().endswith(".pdf") or "/" in item["name"]:
                raise ValueError("Destino ou nome inválido no plano.")
            from datetime import date
            date.fromisoformat(item["date"])
        count = 0
        for item in plan:
            if not (item.get("approved") or (args.auto_clear and item.get("auto_eligible"))):
                continue
            key = (item["source_id"], item["source_modified"])
            identifier = copies.get(key)
            if not identifier:
                data = pdf_bytes(download(drive, item["source_id"]), originals[item["source_id"]]["mimeType"])
                identifier = normalized_copy(drive, item, data)
                copies[key] = identifier
            sync_row(sheets, config, item, identifier)
            count += 1
        print(f"{count} documentos aprovados processados. Originais preservados.")


def main():
    parser = argparse.ArgumentParser(description="Organiza documentos de reembolso com revisão humana.")
    parser.add_argument("command", choices=["login", "folders", "create-sheet", "scan", "apply"])
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--plan", default="plano.json")
    parser.add_argument("--auto-clear", action="store_true", help="Processa casos claros sem aprovação manual.")
    args = parser.parse_args()
    try:
        run(args)
    except (ValueError, OSError) as error:
        parser.exit(1, f"Erro: {error}\n")


if __name__ == "__main__":
    main()
