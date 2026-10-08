import io
import os
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

SCOPES = ["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/spreadsheets"]
FIELDS = "id,name,mimeType,parents,modifiedTime,appProperties"


def clients(login=False):
    directory = Path(".secrets")
    directory.mkdir(mode=0o700, exist_ok=True)
    token = directory / "token.json"
    credentials = Credentials.from_authorized_user_file(str(token), SCOPES) if token.exists() else None
    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
    if login:
        flow = InstalledAppFlow.from_client_secrets_file(str(directory / "client_secret.json"), SCOPES)
        credentials = flow.run_local_server(port=0, open_browser=False, access_type="offline", prompt="consent")
    if not credentials or not credentials.valid:
        raise ValueError("Execute login no seu computador com .secrets/client_secret.json configurado.")
    token.write_text(credentials.to_json())
    os.chmod(token, 0o600)
    return build("drive", "v3", credentials=credentials), build("sheets", "v4", credentials=credentials)


def inventory(drive, root):
    queue, seen, files = [root], set(), []
    while queue:
        parent = queue.pop()
        if parent in seen:
            continue
        seen.add(parent)
        page = None
        while True:
            response = drive.files().list(q=f"'{parent}' in parents and trashed=false", pageToken=page,
                fields=f"nextPageToken,files({FIELDS})", pageSize=1000).execute()
            for item in response.get("files", []):
                if item["mimeType"] == "application/vnd.google-apps.folder":
                    queue.append(item["id"])
                else:
                    files.append(item)
            page = response.get("nextPageToken")
            if not page:
                break
    return files, seen


def download(drive, identifier):
    output = io.BytesIO()
    downloader = MediaIoBaseDownload(output, drive.files().get_media(fileId=identifier))
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return output.getvalue()


def normalized_copy(drive, item, data):
    return drive.files().create(body={"name": item["name"], "parents": [item["destination_id"]],
        "appProperties": {"personalCheckSource": item["source_id"], "personalCheckModified": item["source_modified"]}},
        media_body=MediaIoBaseUpload(io.BytesIO(data), mimetype="application/pdf", resumable=True), fields="id").execute()["id"]


HEADERS = ["ID original", "Data atendimento", "Categoria", "Tipo", "Profissional", "Valor solicitado", "Documento PDF", "Status reembolso", "Valor recebido", "Data solicitação", "Data pagamento", "Observações"]


def sync_row(sheets, config, item, identifier):
    title = config.get("sheet_title", "Documentos")
    quoted = "'" + title.replace("'", "''") + "'"
    spreadsheet = config["spreadsheet_id"]
    metadata = sheets.spreadsheets().get(spreadsheetId=spreadsheet, fields="sheets.properties.title").execute()
    if title not in [s["properties"]["title"] for s in metadata["sheets"]]:
        sheets.spreadsheets().batchUpdate(spreadsheetId=spreadsheet, body={"requests": [{"addSheet": {"properties": {"title": title}}}]}).execute()
    api = sheets.spreadsheets().values()
    rows = api.get(spreadsheetId=spreadsheet, range=f"{quoted}!A:L").execute().get("values", [])
    if rows and rows[0] != HEADERS:
        raise ValueError("Cabeçalhos da aba incompatíveis; escolha uma aba exclusiva para o agente.")
    if not rows:
        api.update(spreadsheetId=spreadsheet, range=f"{quoted}!A1:L1", valueInputOption="RAW", body={"values": [HEADERS]}).execute()
    from .core import safe_cell
    values = [safe_cell(v) for v in [item["source_id"], item["date"], item["category"], item["document_type"], item.get("provider", ""), item.get("amount", ""), f"https://drive.google.com/file/d/{identifier}/view"]]
    for index, row in enumerate(rows[1:], start=2):
        if row and row[0] == item["source_id"]:
            api.update(spreadsheetId=spreadsheet, range=f"{quoted}!A{index}:G{index}", valueInputOption="RAW", body={"values": [values]}).execute()
            return
    api.append(spreadsheetId=spreadsheet, range=f"{quoted}!A:L", valueInputOption="RAW", insertDataOption="INSERT_ROWS", body={"values": [values + ["Pendente", "", "", "", ""]]}).execute()
