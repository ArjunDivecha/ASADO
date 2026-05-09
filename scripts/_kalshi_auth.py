"""
=============================================================================
SCRIPT NAME: scripts/_kalshi_auth.py
=============================================================================

INPUT FILES:
- Optional dotenv-style files (first hit wins per variable):
  - /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/.env.txt
  - /Users/arjundivecha/Dropbox/AAA Backup/.env.txt
  - /Users/arjundivecha/.env.txt
  Format: KEY=VALUE pairs, one per line.
- KALSHI_PRIVATE_KEY_PATH (environment variable):
  Absolute path to an RSA PEM private key file used to sign Kalshi requests.

OUTPUT FILES:
- None (in-memory request signing only).

VERSION: 1.0
LAST UPDATED: 2026-05-08
AUTHOR: Arjun Divecha (with Codex)

DESCRIPTION:
Provides authenticated request signing for Kalshi API calls using RSA-PSS
signatures. This module is additive: if credentials are not configured, callers
can continue using public unauthenticated endpoints without failure.

DEPENDENCIES:
- requests
- cryptography

USAGE:
  from _kalshi_auth import maybe_create_kalshi_auth
  auth = maybe_create_kalshi_auth()
  if auth is not None:
      session.auth = auth

NOTES:
- Never commit PEM keys to git.
- Recommended environment variables:
    KALSHI_API_KEY_ID
    KALSHI_PRIVATE_KEY_PATH
=============================================================================
"""

from __future__ import annotations

import base64
import os
import re
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests
from requests.auth import AuthBase

ENV_KEY_ID = "KALSHI_API_KEY_ID"
ENV_PRIVATE_KEY_PATH = "KALSHI_PRIVATE_KEY_PATH"
ENV_PRIVATE_KEY_INLINE = "KALSHI_PRIVATE_KEY"


def _load_env_file(path: Path) -> None:
    """Best-effort loader for simple KEY=VALUE files."""
    if not path.exists():
        return
    try:
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    except Exception:
        # Silent by design: env-file loading is best effort only.
        return


def _extract_kalshi_freeform_block(path: Path) -> tuple[Optional[str], Optional[str]]:
    """
    Parse non-KEY=VALUE Kalshi notes block from env.txt-style files.

    Expected shape:
        Kalshi
        API Key ID <uuid>
        Private Key
        -----BEGIN RSA PRIVATE KEY-----
        ...
        -----END RSA PRIVATE KEY-----
    """
    if not path.exists():
        return None, None
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None, None

    if "Kalshi" not in text:
        return None, None

    # Restrict search to Kalshi subsection if present to avoid unrelated keys.
    lower_text = text.lower()
    idx = lower_text.find("kalshi")
    scoped = text[idx:] if idx >= 0 else text

    key_id_match = re.search(r"API Key ID\s+([0-9a-fA-F-]{20,})", scoped)
    key_id = key_id_match.group(1).strip() if key_id_match else None

    pem_match = re.search(
        r"-----BEGIN RSA PRIVATE KEY-----[\s\S]+?-----END RSA PRIVATE KEY-----",
        scoped,
    )
    if not pem_match:
        pem_match = re.search(
            r"-----BEGIN PRIVATE KEY-----[\s\S]+?-----END PRIVATE KEY-----",
            scoped,
        )
    pem = pem_match.group(0).strip() if pem_match else None
    return key_id, pem


def _load_env_sources() -> None:
    """Load common env files without overriding process-level env vars."""
    repo_root = Path(__file__).resolve().parents[1]
    candidates = [
        repo_root / ".env.txt",
        Path("/Users/arjundivecha/Dropbox/AAA Backup/.env.txt"),
        Path.home() / ".env.txt",
    ]
    for path in candidates:
        _load_env_file(path)
        if not os.environ.get(ENV_KEY_ID) or not (
            os.environ.get(ENV_PRIVATE_KEY_PATH) or os.environ.get(ENV_PRIVATE_KEY_INLINE)
        ):
            freeform_key_id, freeform_pem = _extract_kalshi_freeform_block(path)
            if freeform_key_id and not os.environ.get(ENV_KEY_ID):
                os.environ[ENV_KEY_ID] = freeform_key_id
            if freeform_pem and not os.environ.get(ENV_PRIVATE_KEY_INLINE):
                os.environ[ENV_PRIVATE_KEY_INLINE] = freeform_pem


def _sign_message(private_key, message: bytes) -> str:
    """Return base64 RSA-PSS-SHA256 signature for message bytes."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    signature = private_key.sign(
        message,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("ascii")


class KalshiRequestAuth(AuthBase):
    """Requests auth adapter that signs only Kalshi-hosted requests."""

    def __init__(self, key_id: str, private_key) -> None:
        self.key_id = key_id
        self._private_key = private_key

    def __call__(self, request: requests.PreparedRequest) -> requests.PreparedRequest:
        parsed = urlparse(request.url or "")
        host = (parsed.netloc or "").lower()
        if "kalshi.com" not in host:
            return request

        timestamp_ms = str(int(time.time() * 1000))
        path = parsed.path or "/"
        method = (request.method or "GET").upper()
        message = f"{timestamp_ms}{method}{path}".encode("utf-8")

        signature_b64 = _sign_message(self._private_key, message)
        request.headers["KALSHI-ACCESS-KEY"] = self.key_id
        request.headers["KALSHI-ACCESS-TIMESTAMP"] = timestamp_ms
        request.headers["KALSHI-ACCESS-SIGNATURE"] = signature_b64
        return request


def maybe_create_kalshi_auth() -> Optional[KalshiRequestAuth]:
    """
    Build a Kalshi auth signer if env credentials are configured.

    Returns:
    - KalshiRequestAuth instance when key id + readable PEM are present
    - None when not configured or key loading fails
    """
    _load_env_sources()
    key_id = os.environ.get(ENV_KEY_ID, "").strip()
    private_key_path = os.environ.get(ENV_PRIVATE_KEY_PATH, "").strip()
    private_key_inline = os.environ.get(ENV_PRIVATE_KEY_INLINE, "").strip()
    if not key_id:
        return None

    try:
        from cryptography.hazmat.primitives import serialization

        private_key = None
        if private_key_path:
            pem_path = Path(private_key_path).expanduser()
            if pem_path.exists():
                private_key = serialization.load_pem_private_key(
                    pem_path.read_bytes(),
                    password=None,
                )
        if private_key is None and private_key_inline:
            normalized = private_key_inline.replace("\\n", "\n").strip()
            private_key = serialization.load_pem_private_key(
                normalized.encode("utf-8"),
                password=None,
            )
        if private_key is None:
            return None
    except Exception:
        return None

    return KalshiRequestAuth(key_id=key_id, private_key=private_key)
