from __future__ import annotations

from dataclasses import dataclass

from src.agents_flow.login_flow.config import bool_env, str_env


@dataclass(frozen=True)
class MailConfig:
    enabled: bool
    summary_enabled: bool
    tenant_id: str
    client_id: str
    client_secret: str
    sender: str
    to: tuple[str, ...]
    cc: tuple[str, ...]
    subject_prefix: str


def _split_recipients(raw: str) -> tuple[str, ...]:
    values = []
    for item in str(raw or "").replace(";", ",").split(","):
        value = item.strip()
        if value:
            values.append(value)
    return tuple(values)


def graph_mail_enabled() -> bool:
    return bool_env("MS_GRAPH_MAIL_ENABLED", default=False)


def summary_mail_enabled() -> bool:
    return bool_env("MS_GRAPH_MAIL_SUMMARY_ENABLED", default=graph_mail_enabled())


def load_mail_config() -> MailConfig:
    return MailConfig(
        enabled=graph_mail_enabled(),
        summary_enabled=summary_mail_enabled(),
        tenant_id=str_env("MS_GRAPH_TENANT_ID", ""),
        client_id=str_env("MS_GRAPH_CLIENT_ID", ""),
        client_secret=str_env("MS_GRAPH_CLIENT_SECRET", ""),
        sender=str_env("MS_GRAPH_SENDER", ""),
        to=_split_recipients(str_env("MS_GRAPH_TO", "")),
        cc=_split_recipients(str_env("MS_GRAPH_CC", "")),
        subject_prefix=str_env("MS_GRAPH_SUBJECT_PREFIX", "BOT ARMAS-GADSO"),
    )


def validate_mail_config(config: MailConfig) -> str:
    if not config.enabled:
        return "MS_GRAPH_MAIL_ENABLED desactivado"
    if not config.summary_enabled:
        return "MS_GRAPH_MAIL_SUMMARY_ENABLED desactivado"

    missing = []
    if not config.tenant_id:
        missing.append("MS_GRAPH_TENANT_ID")
    if not config.client_id:
        missing.append("MS_GRAPH_CLIENT_ID")
    if not config.client_secret:
        missing.append("MS_GRAPH_CLIENT_SECRET")
    if not config.sender:
        missing.append("MS_GRAPH_SENDER")
    if not config.to:
        missing.append("MS_GRAPH_TO")

    return f"Faltan variables: {', '.join(missing)}" if missing else ""


def mask_secret(secret: str) -> str:
    value = str(secret or "").strip()
    if len(value) <= 6:
        return "*" * len(value)
    return f"{value[:3]}{'*' * max(1, len(value) - 6)}{value[-3:]}"
