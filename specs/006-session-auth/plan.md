# Plan 006 - Session Auth (Odoo ↔ agente FastAPI)

Spec: `specs/006-session-auth/spec.md` · Tasks: `specs/006-session-auth/tasks.md`

## Estado de partida (post T1 + blindaje)

`addons/l10n_ve_compliance_manager/models/discuss_channel.py`

- `message_post` intercepta mensajes 1-a-1 con `user_contafis_bot`, resuelve el
  usuario y llama `_call_webhook(user, body, channel_id)`.
- `_call_webhook` valida configuración (`l10n_ve_chat.webhook_url`), obtiene el
  `session_id` del `request`, arma `payload = {'message': question}` y
  `headers = {'X-Odoo-Session': session_id}`, con `requests.post(..., timeout=60)`.
- Sin `session_id` → warning + mensaje amigable, sin llamada al agente.
- Mapeo de respuestas: timeout / `RequestException` / 401-403 / ≥500 / ≥400 /
  JSON inválido → mensaje del bot. Éxito → `_post_bot_response` (+ warnings +
  `LEGAL_DISCLAIMER`).

`addons/l10n_ve_compliance_manager/tests/test_discuss_bot.py`

- Mockea `requests.post` a nivel de módulo (`patch('requests.post')`) y sustituye
  `discuss_channel_module.request` por un `MagicMock` con `session.sid`.
- Tests: header correcto, ausencia de `X-User-Token`, disclaimer legal, usuario
  sin `api_token`, `request=None` y `request.session` que lanza.

## Contrato con el agente (contafis-assistant)

- `POST {ODOO_URL}/web/session/get_session_info` con `Cookie: session_id=<sid>`
  y `X-Odoo-Database` para validar la sesión; expiración 24 h desde
  `last_activity`.
- Prioridad de headers: `X-Odoo-Session` > `X-User-Token` (legacy).
- Respuestas de error relevantes: `401` sesión inválida/expirada, `503` Odoo
  transitorio.
- Éxito: `{answer: str, warnings: [{message: str}], thread_id?: str}`.

## Archivos que puede tocar cada tarea

- T2 (cualquier candidato): `models/discuss_channel.py` + `tests/test_discuss_bot.py`.
  Sin migraciones, sin vistas, sin cambios de seguridad.

## Estrategia de tests

1. TDD: test en rojo primero, luego implementación.
2. Mocks de red siempre con `patch('requests.post')`; nunca se llama al agente
   real desde tests.
3. Conteo oficial: salida de Odoo (`odoo.tests.result`). Progresión esperada:
   340 → 342 (blindaje T1) → 342 + tests de T2.

## Riesgos

- `message_post` corre en el hilo web: un webhook lento bloquea la petición
  (~60 s de timeout). Fuera de alcance de T1/T2; candidato T2-C.
- El `sid` en logs: `_logger.info` imprime los headers. Mitigación pendiente
  (candidato T2-C) — no bloquea T1 porque el log es local y de nivel INFO.
- El backend puede responder `503` si Odoo está caído mientras valida la sesión.
