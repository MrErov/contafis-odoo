"""HTTP client for the external ``/digitize`` service.

Deliberately free of ORM imports: the module can be imported without the
registry, and tests can replace ``requests.post`` without loading models.
"""

import logging

import requests

_logger = logging.getLogger(__name__)

DIGITIZE_ALLOWED_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp')


def post_digitize(url, token, payload, timeout, api_key=None):
    """POST a JSON payload to the ``/digitize`` endpoint.

    No ORM, no logging of the image. ``requests.Timeout`` and
    ``requests.RequestException`` are propagated so the model can map them to
    a localized, actionable message. Returns the raw ``requests.Response``.

    ``token`` is the ephemeral signed identity (``X-ContaFis-Token``) that
    replaces the Odoo ``sid``. ``api_key`` is the shared secret required by the
    assistant middleware (``X-API-Key``); it is omitted when empty so the
    service keeps working in loopback/development setups.

    Redirects are not followed on purpose: the token must never be forwarded
    to a different origin (P0-04).
    """
    headers = {
        'Content-Type': 'application/json',
        'X-ContaFis-Token': token,
    }
    if api_key:
        headers['X-API-Key'] = api_key
    return requests.post(
        url,
        json=payload,
        headers=headers,
        timeout=timeout,
        allow_redirects=False,
    )
