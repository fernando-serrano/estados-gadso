from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[3]
load_dotenv(BASE_DIR / ".env")


def bool_env(name: str, default: bool = False, fallback: str | None = None) -> bool:
    raw = os.getenv(name)
    if raw is None and fallback:
        raw = os.getenv(fallback)
    if raw is None:
        raw = "1" if default else "0"
    return str(raw).strip().lower() in {"1", "true", "yes", "si", "sí", "on"}


def int_env(name: str, default: int, fallback: str | None = None) -> int:
    raw = os.getenv(name)
    if raw is None and fallback:
        raw = os.getenv(fallback)
    try:
        return int(str(raw if raw is not None else default).strip())
    except Exception:
        return default


def str_env(name: str, default: str = "", fallback: str | None = None) -> str:
    raw = os.getenv(name)
    if raw is None and fallback:
        raw = os.getenv(fallback)
    return str(raw if raw is not None else default).strip()


@dataclass(frozen=True)
class Credentials:
    tipo_documento_valor: str
    numero_documento: str
    usuario: str
    contrasena: str

    def validate(self, grupo: str) -> None:
        missing = []
        if not self.numero_documento:
            missing.append("numero_documento")
        if not self.usuario:
            missing.append("usuario")
        if not self.contrasena:
            missing.append("contrasena")
        if missing:
            raise ValueError(f"Faltan credenciales para {grupo}: {', '.join(missing)}")


@dataclass(frozen=True)
class Settings:
    login_url: str
    headless: bool
    hold_browser_open: bool
    ocr_max_intentos: int
    login_captcha_retries: int
    force_first_captcha: str
    login_validation_timeout_ms: int
    logs_dir: Path
    lots_dir: Path
    screenshots_dir: Path
    input_excel_path: str
    max_records: int
    scheduled_multiworker: bool
    scheduled_workers: int
    worker_max_rows: int


def load_settings() -> Settings:
    return Settings(
        login_url=str_env(
            "SUCAMEC_URL_LOGIN",
            "https://www.sucamec.gob.pe/sel/faces/login.xhtml?faces-redirect=true",
            fallback="CARNET_URL_LOGIN",
        ),
        headless=bool_env("SUCAMEC_HEADLESS", default=False, fallback="CARNET_HEADLESS"),
        hold_browser_open=bool_env(
            "SUCAMEC_HOLD_BROWSER_OPEN",
            default=False,
            fallback="HOLD_BROWSER_OPEN",
        ),
        ocr_max_intentos=max(1, int_env("SUCAMEC_OCR_MAX_INTENTOS", 4, fallback="CARNET_OCR_MAX_INTENTOS")),
        login_captcha_retries=max(1, int_env("SUCAMEC_LOGIN_CAPTCHA_RETRIES", 3)),
        force_first_captcha=str_env("SUCAMEC_FORCE_FIRST_CAPTCHA", ""),
        login_validation_timeout_ms=max(
            1000,
            int_env(
                "SUCAMEC_LOGIN_VALIDATION_TIMEOUT_MS",
                12000,
                fallback="LOGIN_VALIDATION_TIMEOUT_MS",
            ),
        ),
        logs_dir=BASE_DIR / str_env("LOG_DIR", "logs"),
        lots_dir=BASE_DIR / "lotes",
        screenshots_dir=BASE_DIR / str_env("SCREENSHOT_DIR", "screenshots"),
        input_excel_path=str_env("SUCAMEC_INPUT_EXCEL", ""),
        max_records=max(0, int_env("SUCAMEC_MAX_RECORDS", 0)),
        scheduled_multiworker=bool_env("SCHEDULED_MULTIWORKER", default=False),
        scheduled_workers=max(1, int_env("SCHEDULED_WORKERS", 1)),
        worker_max_rows=max(0, int_env("CARNET_WORKER_MAX_ROWS", 0)),
    )


def credentials_for_group(grupo: str) -> Credentials:
    grupo_norm = grupo.strip().upper()
    if grupo_norm == "SELVA":
        return Credentials(
            tipo_documento_valor=str_env("SUCAMEC_SELVA_TIPO_DOC", str_env("SELVA_TIPO_DOC", "RUC")),
            numero_documento=str_env("SUCAMEC_SELVA_NUMERO_DOCUMENTO", fallback="SELVA_NUMERO_DOCUMENTO"),
            usuario=str_env("SUCAMEC_SELVA_USUARIO_SEL", fallback="SELVA_USUARIO_SEL"),
            contrasena=str_env("SUCAMEC_SELVA_CLAVE_SEL", fallback="SELVA_CLAVE_SEL"),
        )

    return Credentials(
        tipo_documento_valor=str_env("SUCAMEC_TIPO_DOC", str_env("TIPO_DOC", "RUC")),
        numero_documento=str_env("SUCAMEC_NUMERO_DOCUMENTO", fallback="NUMERO_DOCUMENTO"),
        usuario=str_env("SUCAMEC_USUARIO_SEL", fallback="USUARIO_SEL"),
        contrasena=str_env("SUCAMEC_CLAVE_SEL", fallback="CLAVE_SEL"),
    )
