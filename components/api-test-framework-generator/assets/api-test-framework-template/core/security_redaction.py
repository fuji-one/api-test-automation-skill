"""Shared redaction for requester evidence and generated framework diagnostics."""
from __future__ import annotations

import json
import re
from typing import Any


REDACTED = "__redacted__"
SENSITIVE_KEYS = frozenset({
    "password", "passwd", "pwd", "authorization", "proxyauthorization",
    "cookie", "setcookie", "token", "accesstoken", "refreshtoken", "authtoken",
    "tokenvalue", "sessionsecret", "sessionsecretvalue", "sessionid", "apikey",
    "xapikey", "xauthtoken", "secret", "clientsecret", "secretkey", "privatekey",
    "credential", "credentials", "realname", "idnumber", "identitynumber",
    "accessid", "accesskey", "secretid", "aeskey", "aeskeyvalue", "encryptionkey",
    "publickey", "sessionkey", "secretvalue", "tokentext",
})
TEXT_SECRET = re.compile(
    r'''(?ix)(["']?(?:authorization|proxy[-_]?authorization|password|passwd|pwd|
    (?:access|refresh|auth)?[-_]?token|session[-_]?secret|api[-_]?key|x[-_]?api[-_]?key|
    client[-_]?secret|secret[-_]?key|access[-_]?key|access[-_]?id|secret[-_]?id|
    aes[-_]?key|public[-_]?key|encryption[-_]?key|cookie|set[-_]?cookie)["']?\s*[:=]\s*)
    (?:"[^"\r\n]*"|'[^'\r\n]*'|(?:Bearer\s+|Basic\s+)?[^\s,;&\r\n]+)'''
)
PHONE = re.compile(r"(?<!\d)(1\d{2})\d{4}(\d{4})(?!\d)")


def sensitive_key(key: Any) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
    return normalized in SENSITIVE_KEYS or normalized.endswith(("token", "password")) or normalized.startswith("xauth") or (normalized.startswith("identity") and normalized.endswith(("name", "number")))


class SecretRedactor:
    def __init__(self, *sources: Any, marker: str = REDACTED) -> None:
        self.marker = marker
        self.secrets: set[str] = set()
        for source in sources:
            self.register(source)

    def register(self, value: Any, key_hint: str = "") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                self.register(child, str(key))
        elif isinstance(value, list):
            for child in value:
                self.register(child, key_hint)
        elif sensitive_key(key_hint) and isinstance(value, str) and len(value) >= 8:
            if not value.startswith(("${", "<", "__redacted__")):
                self.secrets.add(value)

    def redact(self, value: Any, key_hint: str = "") -> Any:
        if key_hint == "extract" and isinstance(value, dict):
            return {key: child if isinstance(child, str) and child.startswith("$.") else self.redact(child, str(key)) for key, child in value.items()}
        if sensitive_key(key_hint) and value not in (None, ""):
            return self.marker
        if isinstance(value, dict):
            return {key: self.redact(child, str(key)) for key, child in value.items()}
        if isinstance(value, list):
            return [self.redact(child, key_hint) for child in value]
        if isinstance(value, str):
            # JSON embedded inside a string needs the same key-based treatment.
            try:
                parsed = json.loads(value)
            except (ValueError, TypeError):
                parsed = None
            if isinstance(parsed, (dict, list)):
                return json.dumps(self.redact(parsed), ensure_ascii=False)
            for secret in sorted(self.secrets, key=len, reverse=True):
                value = value.replace(secret, self.marker)
            def mask(match: re.Match[str]) -> str:
                key = re.match(r'''["']?([^"':=\s]+)''', match.group(1))
                return (key.group(1) if key else "secret") + "=" + self.marker
            return PHONE.sub(r"\1****\2", TEXT_SECRET.sub(mask, value))
        return value


def redact(value: Any, key_hint: str = "") -> Any:
    return SecretRedactor(value).redact(value, key_hint)
