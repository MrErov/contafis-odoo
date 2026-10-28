# Plan 003 - Odoo OWL Chat: Asistente Fiscal Integrado

## Arquitectura General

### Componentes OWL (static/src/)
- `systray_chat_widget.js` — Widget `owl.SidePanel` registrado en `systray` via `registry.category("systray").add("l10n_ve_chat", ...)`
- `chat_panel/` — Componentes internos del panel:
  - `ChatPanel.js` — Contenedor principal (state: messages[], conversationId, loading, error)
  - `MessageList.js` — Lista virtualizada con paginación (load more)
  - `MessageItem.js` — Renderiza user/assistant + warnings badge
  - `InputArea.js` — Textarea + botón enviar, contador caracteres (4000)
  - `NewConversationButton.js` — Botón header para nueva conversación
- `hooks/useChat.js` — Lógica de negocio: `sendMessage()`, `loadHistory()`, `createConversation()`, `switchCompany()`

### Backend Python (models/)
- `chat_history.py` — Modelo `l10n.ve.chat.history`:
  - Campos: `user_id` (M2O res.users), `company_id` (M2O res.company), `conversation_id` (Char, index), `role` (Selection user/assistant), `content` (Text), `warnings` (Json), `create_date`, `create_uid`
  - `_sql_constraints`: unique `(user_id, company_id, conversation_id, create_date)` para idempotencia
  - `ir.rule`: `domain_force = ['|', ('company_id', '=', user.company_id), ('user_id', '=', user.id)]` + admin bypass
- `res_users.py` — Extiende `res.users` con `api_token` (Char, groups="base.group_system", help="Token para Asistente Fiscal")

### Controladores (controllers/)
- `chat_controller.py` — `@http.route('/l10n_ve_chat/history', type='json', auth='user')`:
  - `get_history(conversation_id, limit, offset)` — retorna messages[]
  - `get_last_conversation()` — retorna conversation_id más reciente por create_date
  - `send_message(question, conversation_id, history)` — proxy a FastAPI, retorna `{response, warnings, conversation_id}`

### Vistas XML (views/)
- `chat_history_views.xml` — `list,form` + `search` para `l10n.ve.chat.history` con `search_default_filter_my_company=1`
- `res_users_views.xml` — Campo `api_token` en form view de usuario (pestaña "Preferencias" o nueva "Integraciones")

### Menús y Acciones (data/)
- `ir_ui_menu.xml` — Menuitem "Historial de chats" bajo Configuración (parent `l10n_ve_compliance_manager.menu_config`)
- `ir_actions.xml` — Action `action_l10n_ve_chat_history` vinculada a vista list

### Configuración (data/)
- `ir_config_parameter.xml` — `l10n_ve_chat.api_url` default `http://localhost:8000/chat`

### Manifest
- Assets: `web.assets_backend` incluye `l10n_ve_compliance_manager/static/src/systray_chat_widget.js`
- Dependencias: `web`, `mail` (para `owl.SidePanel`), `l10n_ve_compliance_manager`

## Flujo de Datos

1. **Click systray** → `ChatPanel` monta → `useChat.loadHistory()` → RPC `/l10n_ve_chat/history/get_last_conversation` → si existe, `get_history()` → render
2. **Usuario escribe + Enter** → `InputArea` → `useChat.sendMessage(question)` → valida token (vacío = error local) → RPC `/l10n_ve_chat/history/send_message` → controller llama FastAPI con headers → FastAPI responde → controller persiste 2 mensajes (user + assistant) en `chat_history` → retorna `{response, warnings, conversation_id}` → widget actualiza state + `conversationId`
3. **Cambio empresa** → `useChat` escucha `session.company_id` (via `useService("company")`) → al cambiar, `createConversation()` + limpia panel
4. **Nueva conversación** → `NewConversationButton` → `useChat.createConversation()` → UUID v4 + limpia panel

## Tests Requeridos (≥ 15)

### Unit (TransactionCase)
- `test_chat_history_model_create` — crea mensaje, verifica campos + ir.rule
- `test_chat_history_multi_company_isolation` — contador A no ve mensajes de contador B
- `test_chat_history_admin_sees_all` — admin ve mensajes de todas las empresas
- `test_res_users_api_token_field` — campo existe, solo admin editable
- `test_controller_get_history_pagination` — offset/limit funcionan
- `test_controller_get_last_conversation_by_create_date` — orden correcto

### Integración (HttpCase)
- `test_widget_opens_from_systray` — click icono abre SidePanel
- `test_send_message_success` — mock FastAPI 200 → mensaje persistido + respuesta renderizada
- `test_send_message_empty_token_error` — token vacío → error traducido
- `test_send_message_401_error` — mock FastAPI 401 → error traducido + reintento
- `test_send_message_500_error` — mock FastAPI 500 → error traducido + log
- `test_new_conversation_button` — genera UUID + limpia panel
- `test_company_switch_creates_new_conversation` — cambio empresa → nueva conversación vacía
- `test_history_menu_access` — menú abre vista con filtro my_company
- `test_message_truncation_4000_chars` — contenido > 4000 → truncado + aviso

## Archivos a Crear/Modificar (resumen)

```
addons/l10n_ve_compliance_manager/
├── models/
│   ├── __init__.py
│   ├── chat_history.py          # NUEVO
│   └── res_users.py             # NUEVO (extend)
├── controllers/
│   ├── __init__.py
│   └── chat_controller.py       # NUEVO
├── views/
│   ├── chat_history_views.xml   # NUEVO
│   └── res_users_views.xml      # NUEVO
├── data/
│   ├── ir_ui_menu.xml           # NUEVO
│   ├── ir_actions.xml           # NUEVO
│   └── ir_config_parameter.xml  # NUEVO
├── security/
│   └── ir_rule.xml              # NUEVO (regla chat_history)
├── static/src/
│   ├── systray_chat_widget.js   # NUEVO (entry point)
│   └── chat_panel/
│       ├── ChatPanel.js
│       ├── MessageList.js
│       ├── MessageItem.js
│       ├── InputArea.js
│       ├── NewConversationButton.js
│       └── hooks/
│           └── useChat.js
└── __manifest__.py              # MODIFICAR (assets + depends)
```

## Orden de Implementación (sub-tareas)

1. **Modelo + Seguridad** — `chat_history.py`, `ir_rule.xml`, `res_users.py` + tests unitarios
2. **Controlador + Parámetros** — `chat_controller.py`, `ir_config_parameter.xml` + tests unitarios
3. **Vistas + Menús** — `chat_history_views.xml`, `res_users_views.xml`, `ir_ui_menu.xml`, `ir_actions.xml` + tests
4. **OWL Widget Core** — `systray_chat_widget.js`, `ChatPanel.js`, `useChat.js` + HttpCase tests
5. **Componentes UI** — `MessageList.js`, `MessageItem.js`, `InputArea.js`, `NewConversationButton.js`
6. **Integración Multi-company** — listener `session.company_id` + test
7. **Pulido + Demo** — truncamiento, accesibilidad, i18n, demo manual, suite completa
