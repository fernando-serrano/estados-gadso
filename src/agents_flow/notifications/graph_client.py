from __future__ import annotations

import base64
import json
import mimetypes
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .mail_config import MailConfig


def classify_graph_failure(status_code: int, detail: str = "") -> tuple[str, str]:
    detail_upper = str(detail or "").upper()
    if status_code in {401, 403}:
        return "AUTH_ERROR", "La autenticacion o permisos de Microsoft Graph no permitieron enviar el correo"
    if status_code == 404:
        return "SENDER_NOT_FOUND", "La cuenta remitente configurada no fue encontrada en Microsoft 365"
    if status_code == 429:
        return "RATE_LIMIT", "Microsoft Graph aplico limite temporal de solicitudes"
    if status_code >= 500:
        return "GRAPH_SERVER_ERROR", "Microsoft Graph devolvio un error interno del servicio"
    if "INVALID_CLIENT" in detail_upper:
        return "INVALID_CLIENT", "Las credenciales OAuth de Microsoft Graph no son validas"
    return "GRAPH_ERROR", "No se pudo completar el envio del correo por Microsoft Graph"


def _request_json(url: str, data: bytes, headers: dict[str, str]) -> dict:
    request = urllib.request.Request(url=url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read().decode("utf-8", errors="replace")
    return json.loads(payload or "{}")


def acquire_access_token(config: MailConfig) -> str:
    token_url = f"https://login.microsoftonline.com/{config.tenant_id}/oauth2/v2.0/token"
    data = urllib.parse.urlencode(
        {
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        }
    ).encode("utf-8")
    payload = _request_json(
        token_url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    return str(payload.get("access_token", "") or "").strip()


def _attachment_payload(path: Path) -> dict:
    mime_type, _ = mimetypes.guess_type(path.name)
    content_type = mime_type or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return {
        "@odata.type": "#microsoft.graph.fileAttachment",
        "name": path.name,
        "contentType": content_type,
        "contentBytes": encoded,
    }


def send_mail(config: MailConfig, subject: str, html_body: str, attachments: list[Path]) -> None:
    token = acquire_access_token(config)
    if not token:
        raise RuntimeError("No se pudo obtener access_token de Microsoft Graph")

    message = {
        "subject": subject,
        "body": {
            "contentType": "HTML",
            "content": html_body,
        },
        "toRecipients": [{"emailAddress": {"address": address}} for address in config.to],
        "ccRecipients": [{"emailAddress": {"address": address}} for address in config.cc],
        "attachments": [_attachment_payload(path) for path in attachments if path.exists()],
    }

    payload = json.dumps(
        {
            "message": message,
            "saveToSentItems": True,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url=f"https://graph.microsoft.com/v1.0/users/{config.sender}/sendMail",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120):
        return
