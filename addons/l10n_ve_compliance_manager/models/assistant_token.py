"""Token efímero firmado para autenticar al usuario ante contafis-assistant.

Reemplaza el envío del ``session_id`` (``sid``) de Odoo (P0-04). El token es
un payload canónico ``{uid, company_id, exp}`` codificado en base64url y
firmado con HMAC-SHA256 usando el secreto compartido
(``l10n_ve_chat.auth_token`` en Odoo, ``API_SHARED_SECRET`` en el asistente).

El módulo no importa el ORM a propósito: ``digitize_client`` lo usa en un
contexto sin registry.
"""

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass

#: Vida útil del token. El asistente lo valida con un margen mínimo de reloj.
TOKEN_TTL_SECONDS = 60

#: Margen de reloj aceptado entre Odoo y el asistente.
TOKEN_CLOCK_SKEW_SECONDS = 5

#: TTL máximo aceptado al verificar, para rechazar tokens de larga duración.
TOKEN_MAX_FUTURE_SECONDS = TOKEN_TTL_SECONDS + TOKEN_CLOCK_SKEW_SECONDS


@dataclass(frozen=True)
class AssistantTokenClaims:
    """Claims verificados del token."""

    uid: int
    company_id: int
    exp: int


def _b64url_encode(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def _b64url_decode(value):
    padding = '=' * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _canonical_payload(uid, company_id, exp):
    return json.dumps(
        {
            'uid': int(uid),
            'company_id': int(company_id),
            'exp': int(exp),
        },
        separators=(',', ':'),
        sort_keys=True,
    ).encode('utf-8')


def _normalize_secret(secret):
    if not isinstance(secret, str):
        raise ValueError('El secreto compartido debe ser una cadena.')
    secret = secret.strip()
    if not secret:
        raise ValueError('El secreto compartido no está configurado.')
    return secret


def _positive_int(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f'El claim {name} debe ser un entero positivo.')
    return value


def generate_assistant_token(
    secret,
    *,
    uid,
    company_id,
    ttl_seconds=TOKEN_TTL_SECONDS,
    now=None,
):
    """Firma un token de corta duración para el usuario y compañía dados.

    ``now`` se inyecta en los tests; en producción usa ``time.time()``.
    """
    secret = _normalize_secret(secret)
    uid = _positive_int(int(uid), 'uid')
    company_id = _positive_int(int(company_id), 'company_id')
    ttl_seconds = int(ttl_seconds)
    if ttl_seconds <= 0 or ttl_seconds > TOKEN_TTL_SECONDS:
        raise ValueError(
            f'El TTL debe estar entre 1 y {TOKEN_TTL_SECONDS} segundos.'
        )

    issued_at = int(time.time() if now is None else now)
    exp = issued_at + ttl_seconds
    payload_b64 = _b64url_encode(_canonical_payload(uid, company_id, exp))
    signature = hmac.new(
        secret.encode('utf-8'),
        payload_b64.encode('ascii'),
        hashlib.sha256,
    ).digest()
    return f'{payload_b64}.{_b64url_encode(signature)}'


def verify_assistant_token(token, secret, *, now=None):
    """Verifica firma y expiración; devuelve los claims o lanza ``ValueError``."""
    secret = _normalize_secret(secret)
    if not isinstance(token, str):
        raise ValueError('El token debe ser una cadena.')

    parts = token.strip().split('.')
    if len(parts) != 2:
        raise ValueError('El token tiene un formato inválido.')
    payload_b64, signature_b64 = parts
    if not payload_b64 or not signature_b64:
        raise ValueError('El token tiene un formato inválido.')

    try:
        signature = _b64url_decode(signature_b64)
        payload_bytes = _b64url_decode(payload_b64)
    except Exception as exc:  # base64 inválido
        raise ValueError('El token tiene un formato inválido.') from exc

    expected = hmac.new(
        secret.encode('utf-8'),
        payload_b64.encode('ascii'),
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(signature, expected):
        raise ValueError('La firma del token no es válida.')

    try:
        payload = json.loads(payload_bytes.decode('utf-8'))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError('El payload del token no es válido.') from exc
    if not isinstance(payload, dict):
        raise ValueError('El payload del token no es válido.')

    uid = _positive_int(payload.get('uid'), 'uid')
    company_id = _positive_int(payload.get('company_id'), 'company_id')
    exp = _positive_int(payload.get('exp'), 'exp')

    current = time.time() if now is None else float(now)
    if exp < current:
        raise ValueError('El token expiró.')
    if exp > current + TOKEN_MAX_FUTURE_SECONDS:
        raise ValueError('El token tiene una vigencia mayor a la permitida.')

    return AssistantTokenClaims(uid=uid, company_id=company_id, exp=exp)
