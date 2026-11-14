"""HTTP client for the external ``/digitize`` service.

Deliberately free of ORM imports: the module can be imported without the
registry, and tests can replace ``requests.post`` without loading models.
"""

import logging

import requests
from odoo.http import request

_logger = logging.getLogger(__name__)

DIGITIZE_ALLOWED_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp')


def _get_session_id():
    """Return the current HTTP session id, or ``''`` outside an HTTP context.

    Same guard as ``models/discuss_channel.py::_call_webhook``: ``request``
    may be unbound (cron, shell, tests) and any attribute access would raise.
    The failure is contained and an empty session is returned.
    """
    session_id = ''
    try:
        if request and hasattr(request, 'session') and request.session:
            session_id = request.session.sid or ''
    except Exception:
        _logger.warning(
            "Could not read the session id from the request (non-HTTP context)."
        )
    return session_id


def post_digitize(url, session_id, payload, timeout, api_key=None):
    """POST a JSON payload to the ``/digitize`` endpoint.

    No ORM, no logging of the image. ``requests.Timeout`` and
    ``requests.RequestException`` are propagated so the model can map them to
    a localized, actionable message. Returns the raw ``requests.Response``.

    ``api_key`` is the shared secret required by the assistant middleware
    (``X-API-Key``). It is omitted when empty so the service keeps working
    in loopback/development setups without a configured secret.
    """
    headers = {
        'Content-Type': 'application/json',
        'X-Odoo-Session': session_id,
    }
    if api_key:
        headers['X-API-Key'] = api_key
    return requests.post(url, json=payload, headers=headers, timeout=timeout)
