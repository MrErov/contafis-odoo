# Spec 003 - Odoo OWL Chat: Asistente Fiscal Integrado

Estado: borrador

## Contexto y objetivo
Integrar el Asistente Fiscal (backend FastAPI/LangGraph) dentro de Odoo 19 mediante un widget OWL accesible desde la barra superior (systray). El contador podrá consultar dudas fiscales, parafiscales y documentales sin salir de Odoo, manteniendo el historial de conversaciones por empresa y usuario, con autenticación mediante token personal.

## Usuarios / actores
- **Contador** (grupos `account.group_account_user` + `l10n_ve_compliance_accountant`): uso diario del chat para consultas fiscales.
- **Administrador** (`base.group_system`): acceso completo, puede ver todas las conversaciones.
- **Sistema externo FastAPI**: recibe preguntas, devuelve respuesta, warnings y conversación_id.

## Historias de usuario
- HU-1: Como contador quiero abrir el chat desde la barra superior para consultar al Asistente Fiscal sin cambiar de ventana.
- HU-2: Como contador quiero que mis preguntas se envíen autenticadas con mi token personal para que el backend sepa quién soy y qué empresas gestiono.
- HU-3: Como contador quiero ver la respuesta del asistente, los warnings (ej. scope_admin_key) y el historial de la conversación para dar seguimiento a mis consultas.
- HU-4: Como contador quiero que el historial se guarde por empresa para no mezclar consultas de distintos clientes.
- HU-5: Como administrador quiero ver todas las conversaciones de todos los contadores para auditoría y soporte.

## Requisitos funcionales (EARS)
- RF-1: CUANDO el usuario hace clic en el icono del systray, EL SISTEMA abre un panel lateral usando `owl.SidePanel` con la interfaz de chat.
- RF-2: CUANDO el usuario envía un mensaje, EL SISTEMA realiza una petición HTTP POST a `http://localhost:8000/chat` con headers `Authorization: Bearer <user.api_token>` y `X-Odoo-Company: <user.company_id>`, body JSON `{question: string, conversation_id: string|null, history: array[{role: string, content: string, warnings?: array}]}`.
- RF-3: SI el token del usuario está vacío, ENTONCES EL SISTEMA muestra un error en el chat usando `_("Token de API no configurado. Contacte al administrador.")` y NO envía la petición al backend. SI el token no está vacío, EL SISTEMA envía la petición y el backend valida el token (devuelve 401/403 si inválido).
- RF-4: CUANDO el backend responde con éxito (2xx), EL SISTEMA renderiza la respuesta del asistente, la lista de warnings (si existe, array de strings) y actualiza el `conversation_id` en el estado del widget con el valor devuelto por el backend.
- RF-5: SI el backend responde con error 401/403, ENTONCES EL SISTEMA muestra `_("Token inválido o expirado")` y ofrece reintentar tras configurar token.
- RF-6: SI el backend responde con error 5xx o timeout (>30s), ENTONCES EL SISTEMA muestra `_("Error de comunicación con el Asistente Fiscal. Reintente en unos minutos.")` y registra el error en `ir.logging`.
- RF-7: MIENTRAS el panel de chat está abierto, EL SISTEMA muestra el historial de mensajes de la conversación actual ordenado por `create_date` ASC (cargado desde `l10n.ve.chat.history` filtrado por `user_id` y `company_id`), paginado a 20 mensajes por página con "Cargar más".
- RF-8: CUANDO se crea un nuevo mensaje (usuario o asistente), EL SISTEMA lo persiste en `l10n.ve.chat.history` con campos `user_id`, `company_id`, `conversation_id`, `role` (user/assistant), `content` (máx. 4000 caracteres), `warnings` (JSON array de strings), `create_date`, `create_uid`. El modelo tiene `ir.rule` para que contadores solo vean su `company_id` (admin ve todo).
- RF-9: CUANDO el usuario cierra y reabre el panel, EL SISTEMA recupera la última conversación activa del usuario en esa empresa (la que tenga `create_date` más reciente en su primer mensaje) y la muestra.
- RF-10: EL SISTEMA permite al usuario iniciar una nueva conversación (botón "Nueva conversación") que genera un nuevo `conversation_id` (UUID v4) y limpia el panel.
- RF-11: EL SISTEMA expone una acción de menú "Historial de chats" (bajo Configuración) que abre una vista `list,form` de `l10n.ve.chat.history` con `search_default_filter_my_company=1`, filtros por usuario, empresa, rango de fechas y búsqueda en contenido (`content`).
- RF-12: EL SISTEMA respeta el principio multi-cliente: todas las consultas y lecturas de historial filtran por `company_id` del usuario actual (excepto admin que ve todo via `ir.rule` sin dominio restrictivo).

## Requisitos no funcionales
- **Rendimiento**: carga inicial del panel < 500ms en red local con BD caliente e historial ≤ 100 mensajes (historial paginado, 20 mensajes por página).
- **Seguridad**: token nunca expuesto en localStorage ni logs; petición HTTPS en producción (configurable via `ir.config_parameter` `l10n_ve_chat.api_url` con default `http://localhost:8000/chat`).
- **Accesibilidad**: panel navegable por teclado, ARIA labels en botones, contraste WCAG AA.
- **Internacionalización**: strings de UI en español usando `_()`; código en inglés.

## Casos límite
- Usuario sin `api_token` configurado → error claro en UI usando `_()`, no llamada a backend.
- Backend devuelve `warnings` array vacío o null → no renderizar sección de warnings.
- Conversación con cientos de mensajes → paginación infinita (load more) en el widget.
- Múltiples pestañas abiertas → cada pestaña mantiene su estado local; persistencia en Odoo evita pérdida.
- Usuario cambia de empresa en el switcher de Odoo → el widget detecta el cambio (via `session.company_id`) y crea una nueva conversación vacía para la nueva empresa.
- Red inestable → reintento automático 1 vez con backoff exponencial (2s), luego error controlado.
- Mensaje `content` > 4000 caracteres → truncar con aviso visual "Mensaje truncado a 4000 caracteres".
- Concurrencia: dos pestañas envían mensaje simultáneo con mismo `conversation_id` → el backend maneja con optimistic locking (version field) o "último gana"; frontend no implementa locking.

## Fuera de alcance
- Streaming de respuesta token a token (SSE/WebSocket) — versión futura.
- Adjuntar archivos/imágenes en el chat — versión futura.
- Notificaciones push cuando el backend responde asíncronamente — versión futura.
- Integración con `mail.channel` o `discuss` — no requerido.
- Autenticación OAuth2/OIDC con el backend FastAPI — token Bearer estático por usuario es suficiente para MVP.
- Panel flotante (botón flotante) — solo systray en esta versión.
- Edición/borrado de mensajes individuales — versión futura.
- Retención/limpieza automática de historial antiguo (GDPR) — versión futura.

## Criterios de finalización
- Todos los RF con test unitario en verde (TransactionCase para modelo/historial, HttpCase para widget/integración).
- Demo manual: contador logueado abre systray, envía pregunta, ve respuesta + warnings + historial persistente tras recargar y cambio de empresa.
- 0 failed, 0 error(s) en suite completa (≥ 331 tests actual + ≥ 15 nuevos tests de chat).
- Ruff, check-xml, trailing-whitespace, mixed-line-ending en verde.

## Dudas abiertas (resueltas)
- [RESUELTO] El campo `api_token` en `res.users` se crea en esta spec (campo `Char`, `groups="base.group_system"` para que solo admin lo vea/edite).
- [RESUELTO] El endpoint FastAPI requiere `X-Odoo-Company` header explícito (el backend no infiere empresa del token).
- [RESUELTO] Formato de `warnings` en respuesta: array de strings (ej. `["scope_admin_key", "rif_invalid"]`).

## Resolución de Dudas (QA 2026-10-27)
1. **UI**: Widget usa `owl.SidePanel` (no flotante, no modal completo).
2. **Historial**: Modelo `l10n.ve.chat.history` con `company_id`, `create_date`, `create_uid`, `ir.rule` por `company_id` (admin sin regla = ve todo).
3. **Orden conversación reciente**: Por `create_date` del primer mensaje de la conversación (no por UUID).
4. **Validación token**: Frontend solo bloquea si token vacío; backend valida y devuelve 401/403.
5. **Multi-company switch**: Al cambiar empresa, widget crea nueva conversación vacía.
6. **Límite content**: 4000 caracteres, truncado con aviso.
7. **Strings traducibles**: Todos los mensajes de error usan `_()`.
8. **Parámetro HTTPS**: `ir.config_parameter` `l10n_ve_chat.api_url` con default `http://localhost:8000/chat`.
9. **Record rules**: `ir.rule` en modelo historial para multi-cliente (Principio 3 Constitución).
10. **Tests mínimos**: ≥ 15 tests nuevos cubriendo modelo, widget, integración, multi-company, errores.
