# Spec 006 - Session Auth para el asistente de IA

Estado: T1 implementada y blindada (`0 failed, 0 error(s) of 342 tests`).
T2 pendiente de confirmación (ver `tasks.md`).

> Reconstruida el 2026-11-01 a partir del commit `5e724fb` (T1), que se commiteó
> sin haber creado el directorio `specs/006-session-auth/`. No existían
> `spec.md`, `plan.md` ni `tasks.md`; el alcance se deduce del diff de T1 y del
> contrato real del backend (`contafis-assistant`, `api/user_auth.py`).

## Contexto y objetivo

El bot de Discuss (`discuss.channel.message_post`) reenvía cada consulta del
contador a un agente externo (FastAPI) vía `POST` a
`ir.config_parameter` `l10n_ve_chat.webhook_url`. Hasta T1 la autenticación
viajaba en el header `X-User-Token`, que obligaba a cada usuario a generar y
pegar una API key personal en sus preferencias (`res.users.api_token`); si el
usuario no la tenía, el bot solo mostraba un aviso de configuración.

Desde T1 el bot envía `X-Odoo-Session` con el `sid` de la sesión web vigente,
y el backend lo valida contra `/web/session/get_session_info` (cookie
`session_id`), aceptando además `X-User-Token` como *fallback* legacy.
Objetivo: autenticar cada consulta con la sesión que el usuario ya tiene
abierta, sin configuración manual, y degradar con mensajes claros cuando la
sesión falta, expiró o es rechazada.

## Usuarios / actores

- **Contador**: conversa con el bot desde *Discuss → ContaFis AI*.
- **Administrador**: configura la URL del webhook en Ajustes.
- **Bot** (`user_contafis_bot`): publica respuestas, avisos y errores en el canal.
- **Agente externo** (FastAPI): valida la sesión y responde JSON
  `{answer, warnings}`.

## Historias de usuario

- HU-1: Como contador quiero que el asistente me identifique con la sesión que
  ya tengo abierta, sin generar tokens.
- HU-2: Como contador quiero un mensaje claro si mi sesión no puede detectarse,
  en vez de un error genérico.
- HU-3: Como administrador quiero que un fallo de autenticación del agente no
  rompa la conversación ni deje el canal sin respuesta.

## Requisitos funcionales (EARS)

- RF-1: CUANDO el bot invoca al agente desde una petición HTTP autenticada, EL
  SISTEMA envía el header `X-Odoo-Session` con `request.session.sid` y NO envía
  `X-User-Token`.
- RF-2: EL SISTEMA deja de exigir `res.users.api_token` para usar el asistente.
- RF-3: SI el `session_id` no puede obtenerse (contexto no HTTP: crons, tests,
  llamadas sin request), ENTONCES EL SISTEMA no lanza excepción, registra un
  warning y publica en el canal «🔐 Sesión no detectada. Por favor, recargá Odoo
  e intentá de nuevo.», sin llamar al agente.
- RF-4: CUANDO el agente responde con éxito, EL SISTEMA publica la respuesta en
  el canal con el disclaimer legal (aviso de IA, no asesoría profesional) y las
  advertencias del agente en viñetas, evitando HTML no seguro.
- RF-5: SI el agente responde 401/403, ENTONCES EL SISTEMA informa el problema de
  autenticación sin romper el canal (mensaje accionable para el usuario).
- RF-6: SI el agente responde 4xx/5xx, hay timeout o la respuesta no es JSON,
  ENTONCES EL SISTEMA publica un mensaje específico y registra el error con la
  URL y el tiempo transcurrido.
- RF-7: EL SISTEMA nunca entra en bucle: los mensajes publicados por el bot no
  vuelven a disparar la llamada al agente.

## Requisitos no funcionales

- Tests como puerta: cada RF con test en verde; el conteo oficial es el que
  reporta Odoo (`odoo.tests.result`), sin regresiones.
- Seguridad: el `sid` nunca se persiste ni se loguea completo; el token legacy
  no se envía si hay sesión.
- Robustez: el código del bot no debe asumir contexto HTTP (crons, shell, tests).
- Multi-cliente: el agente opera con los permisos del usuario de la sesión.
- Convenciones Odoo 19 y `docs/constitution.md`.

## Casos límite

- `request` no ligado (cron, `odoo shell`, test unitario) → RF-3.
- `request` ligado sin `session` o con `sid` vacío → RF-3.
- Sesión expirada en Odoo → el agente responde 401 → RF-5.
- Webhook sin configurar → aviso de configuración (sin llamada).
- Consulta desde un canal que no es 1-a-1 con el bot → no se intercepta.
- Autor del mensaje es el propio bot → no se reenvía (anti-bucle).

## Fuera de alcance

- Autenticación OAuth/OIDC o *service accounts* por empresa.
- Persistencia de conversaciones o historial en el backend (sigue in-process).
- Cambios al contrato del agente más allá de los headers de autenticación.
- Streaming de respuestas o *typing indicator* en Discuss.
- Rate limiting por usuario (ver candidatos en `tasks.md`).

## Criterios de finalización

- `0 failed, 0 error(s) of N` con N = 340 + tests nuevos.
- Verificación visual en *Discuss → ContaFis AI* vía Chrome DevTools: sin
  errores JS ni respuestas 401/500 en la consola, y disclaimer en la respuesta.
- Un commit por tarea de `tasks.md`.
