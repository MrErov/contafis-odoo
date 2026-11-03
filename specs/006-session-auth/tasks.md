# Tasks 006 - Session Auth

Spec: `specs/006-session-auth/spec.md` · Plan: `specs/006-session-auth/plan.md`

Reglas: una tarea a la vez, en orden de dependencia. Commit al terminar cada tarea si los tests pasan (el conteo oficial es el de Odoo). Sin archivos temporales.

Comando oficial de tests (única fuente del conteo):
`docker compose run --rm web odoo -d contea -u l10n_ve_compliance_manager --test-enable --stop-after-init --workers 0 --test-tags /l10n_ve_compliance_manager`

- [x] **T1. Autenticación por sesión: `X-Odoo-Session` en vez de `X-User-Token`, sin exigir `api_token`, disclaimer legal en la respuesta + tests.** RF-1, RF-2, RF-4, RF-6, RF-7
      Hecho cuando: `_call_webhook` envía `X-Odoo-Session` con `request.session.sid`; `X-User-Token` ya no se envía; un usuario sin `api_token` puede consultar; `_post_bot_response` agrega `LEGAL_DISCLAIMER`; suite sin regresiones.
      Cerrada (commit `5e724fb`, `0 failed, 0 error(s) of 340 tests`).

- [x] **T1b. Blindaje de T1: `request` fuera de contexto HTTP (cron, shell, tests) no debe romper el bot.** RF-3
      Hecho cuando: la captura del `sid` va en `try/except`, tolera `request` nulo, sin `session` o con `sid` vacío; sin `session_id` se registra un warning y se publica «🔐 Sesión no detectada. Por favor, recargá Odoo e intentá de nuevo.» sin llamar al agente; tests `test_no_http_context_posts_friendly_session_message` y `test_unbound_request_does_not_raise` en verde.
      Cerrada: `0 failed, 0 error(s) of 342 tests`.

- [x] **T2. Sesión expirada o inválida: mensaje accionable en el canal.** RF-5
      Hecho cuando: un `401`/`403` del agente ya no se reporta como «token del webhook» sino como sesión expirada/inválida con instrucción de recargar Odoo; se distingue `503` (Odoo no disponible al validar la sesión) del resto de 5xx; tests para 401 y 503.
      Cerrada: `401/403` → «🔐 Tu sesión de Odoo expiró o no es válida. Recargá Odoo e intentá de nuevo.»; `503` → «🔄 No se pudo validar tu sesión en este momento…»; el resto de `5xx` conserva el mensaje genérico. Las cinco ramas de error usan `_post_bot_error` (se eliminaron ~40 líneas repetidas). Tests `test_expired_session_is_reported_as_session_error` y `test_validation_unavailable_is_not_reported_as_agent_crash`. `0 failed, 0 error(s) of 344 tests`.

## Candidatos de T2 considerados (elegido: T2-A)

| ID | Alcance | Estado |
|----|---------|--------|
| **T2-A** | Mapear `401/403` → sesión expirada y `503` → validación no disponible, distinguiéndolos del 5xx genérico. | **Elegido e implementado.** |
| T2-B | Test de contrato Odoo↔agente con `HttpCase` (requiere backend vivo en CI). | No elegido. |
| T2-C | Sacar el webhook del hilo web, recortar `timeout` y no loguear el `sid`. | No elegido: queda como deuda abierta (ver `plan.md`, riesgos). |
