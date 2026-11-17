"""Contrato del token efímero firmado para contafis-assistant (P0-04).

El ``sid`` de Odoo ya no se envía al asistente. En su lugar se firma un
payload ``{uid, company_id, exp}`` con HMAC-SHA256 y el secreto compartido
(``l10n_ve_chat.auth_token`` / ``API_SHARED_SECRET``).
"""

import base64
import hashlib
import hmac
import json

from odoo.addons.l10n_ve_compliance_manager.models.assistant_token import (
    TOKEN_TTL_SECONDS,
    generate_assistant_token,
    verify_assistant_token,
)
from odoo.tests import TransactionCase, tagged


def _b64url_decode(value):
    padding = '=' * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _decode_payload(token):
    payload_b64, _signature = token.split('.')
    return json.loads(_b64url_decode(payload_b64).decode('utf-8'))


@tagged('post_install', '-at_install')
class TestAssistantToken(TransactionCase):
    """Generación y verificación del token firmado."""

    def test_payload_contains_uid_company_and_exp(self):
        token = generate_assistant_token(
            'shared-secret', uid=7, company_id=3, now=1000,
        )

        payload = _decode_payload(token)

        self.assertEqual(
            payload,
            {
                'uid': 7,
                'company_id': 3,
                'exp': 1000 + TOKEN_TTL_SECONDS,
            },
        )

    def test_token_is_signed_with_hmac_sha256(self):
        token = generate_assistant_token(
            'shared-secret', uid=7, company_id=3, now=1000,
        )
        payload_b64, signature_b64 = token.split('.')

        expected = hmac.new(
            b'shared-secret',
            payload_b64.encode('ascii'),
            hashlib.sha256,
        ).digest()

        self.assertEqual(_b64url_decode(signature_b64), expected)

    def test_valid_token_returns_claims(self):
        token = generate_assistant_token(
            'shared-secret', uid=7, company_id=3, now=1000,
        )

        claims = verify_assistant_token(token, 'shared-secret', now=1000)

        self.assertEqual(claims.uid, 7)
        self.assertEqual(claims.company_id, 3)
        self.assertEqual(claims.exp, 1000 + TOKEN_TTL_SECONDS)

    def test_tampered_payload_is_rejected(self):
        token = generate_assistant_token(
            'shared-secret', uid=7, company_id=3, now=1000,
        )
        _payload_b64, signature_b64 = token.split('.')
        tampered = base64.urlsafe_b64encode(
            b'{"uid": 8, "company_id": 3, "exp": 1060}'
        ).rstrip(b'=').decode('ascii')

        with self.assertRaises(ValueError):
            verify_assistant_token(
                f'{tampered}.{signature_b64}', 'shared-secret', now=1000,
            )

    def test_wrong_secret_is_rejected(self):
        token = generate_assistant_token(
            'shared-secret', uid=7, company_id=3, now=1000,
        )

        with self.assertRaises(ValueError):
            verify_assistant_token(token, 'other-secret', now=1000)

    def test_expired_token_is_rejected(self):
        token = generate_assistant_token(
            'shared-secret', uid=7, company_id=3, now=1000,
        )

        with self.assertRaises(ValueError):
            verify_assistant_token(
                token,
                'shared-secret',
                now=1000 + TOKEN_TTL_SECONDS + 1,
            )

    def test_empty_secret_cannot_sign(self):
        with self.assertRaises(ValueError):
            generate_assistant_token('', uid=7, company_id=3, now=1000)

    def test_malformed_tokens_are_rejected(self):
        for token in ('', 'abc', 'a.b.c', '!!!.???'):
            with self.subTest(token=token):
                with self.assertRaises(ValueError):
                    verify_assistant_token(token, 'shared-secret', now=1000)

    def test_negative_ids_are_rejected(self):
        token = generate_assistant_token(
            'shared-secret', uid=7, company_id=3, now=1000,
        )
        payload_b64, _signature = token.split('.')
        signature = hmac.new(
            b'shared-secret',
            base64.urlsafe_b64encode(
                b'{"uid": -1, "company_id": 3, "exp": 1060}'
            ).rstrip(b'='),
            hashlib.sha256,
        ).digest()
        forged = (
            base64.urlsafe_b64encode(
                b'{"uid": -1, "company_id": 3, "exp": 1060}'
            ).rstrip(b'=').decode('ascii')
        )
        forged += '.' + base64.urlsafe_b64encode(signature).rstrip(b'=').decode('ascii')

        with self.assertRaises(ValueError):
            verify_assistant_token(forged, 'shared-secret', now=1000)
