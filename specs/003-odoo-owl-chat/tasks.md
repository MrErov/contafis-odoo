# Tasks 003 - Odoo OWL Chat: Asistente Fiscal Integrado

- [x] **T1. Modelo l10n.ve.chat.history + ir.rule multi-cliente + api_token en res.users**
  **RF cubiertos:** RF-7, RF-8, RF-12, RF-2, RF-3
  **Archivos:** models/chat_history.py, models/res_users.py, security/ir_rule.xml, security/ir.model.access.csv, models/__init__.py
  **Hecho cuando:** docker compose run --rm web odoo -d contea -u l10n_ve_compliance_manager --stop-after-init --workers 0 instala sin errores; modelo visible en UI; ir.rule filtra por company_id (verificado con 2 usuarios contadores en empresas distintas); tests test_chat_history.py (6 tests) en verde; suite completa 331 tests (0 failed).

- [x] **T2. Vista res.users para campo api_token**
  **RF cubiertos:** RF-2, RF-3
  **Archivos:** views/res_users_views.xml, __manifest__.py
  **Hecho cuando:** Campo api_token visible en form view de usuario (pestaña Preferencias), solo editable por base.group_system; módulo actualiza sin errores.

- [x] **T3. Controlador JSON /l10n_ve_chat/history + ir.config_parameter**
  **RF cubiertos:** RF-2, RF-4, RF-5, RF-6, RF-7, RF-9
  **Archivos:** controllers/chat_proxy.py, controllers/__init__.py, data/ir_config_parameter_data.xml, __init__.py
  **Hecho cuando:** Endpoints get_history, get_last_conversation, send_message responden 200 via RPC; send_message llama FastAPI con headers Authorization + X-Odoo-Company; parámetro l10n_ve_chat.api_url existe con default http://localhost:8000/chat.

- [x] **T4. Tests unitarios: modelo + seguridad (6 tests)**
  **RF cubiertos:** RF-7, RF-8, RF-12, RF-2, RF-3
  **Archivos:** tests/test_chat_history.py
  **Hecho cuando:** 6 tests nuevos en verde (test_create_message, test_multi_company_isolation, test_admin_sees_all, test_conversation_order_by_create_date, test_api_token_field_exists, test_api_token_only_admin_editable, test_api_token_help_text); suite completa 331 tests (0 failed).

- [x] **T5. Vistas list,form,search historial + menú Historial de chats**
  **RF cubiertos:** RF-11
  **Archivos:** views/chat_history_views.xml, views/menu.xml, __manifest__.py
  **Hecho cuando:** Módulo actualiza sin errores (-u); menú "Historial de chats" visible bajo Configuración; action abre vista list con search_default_filter_my_company=1; filtros usuario/empresa/rol/búsqueda funcionan; admin ve todo, contador solo su empresa (ir.rule); tests suite 0 failed.

- [x] **T6. Widget OWL core: systray_chat_widget.js + ChatPanel.js + useChat.js (registro systray + carga inicial)**
  **RF cubiertos:** RF-1, RF-7, RF-9
  **Archivos:** static/src/systray_chat_widget.js, static/src/chat_panel/ChatPanel.js, static/src/chat_panel/hooks/useChat.js, static/src/chat_panel/MessageList.js, static/src/chat_panel/MessageItem.js, static/src/chat_panel/InputArea.js, static/src/chat_panel/NewConversationButton.js, static/src/xml/chat_templates.xml, __manifest__.py (assets)
  **Hecho cuando:** Módulo actualiza sin errores (-u); icono en systray registrado; click abre panel lateral (owl.SidePanel equivalente); useChat.loadHistory() llama RPC get_last_conversation + get_history; panel muestra mensajes históricos; tests suite 0 failed.

- [ ] **T7. Componente InputArea.js + envío mensaje + validación token vacío + truncamiento 4000 chars**
  **RF cubiertos:** RF-2, RF-3, RF-47 (límite content)
  **Archivos:** static/src/chat_panel/InputArea.js, static/src/chat_panel/hooks/useChat.js (método sendMessage)
  **Hecho cuando:** Escribir mensaje + Enter llama sendMessage; token vacío muestra _("Token de API no configurado...") y NO hace RPC; mensaje > 4000 chars trunca con aviso "Mensaje truncado a 4000 caracteres"; RPC incluye headers Authorization + X-Odoo-Company + body correcto.

- [ ] **T8. Manejo respuestas backend: éxito (RF-4), 401/403 (RF-5), 5xx/timeout (RF-6) + warnings + reintento 1x**
  **RF cubiertos:** RF-4, RF-5, RF-6, RF-42, RF-46
  **Archivos:** static/src/chat_panel/hooks/useChat.js (manejo respuestas), static/src/chat_panel/MessageItem.js (render warnings)
  **Hecho cuando:** Mock FastAPI 200 -> render respuesta + warnings array + actualiza conversation_id; Mock 401 -> muestra _("Token inválido o expirado") + botón reintentar; Mock 500/timeout -> muestra _("Error de comunicación...") + log en ir.logging; reintento 1 vez con backoff 2s antes de error final.

- [ ] **T9. Botón Nueva conversación + cambio de empresa (listener session.company_id)**
  **RF cubiertos:** RF-10, RF-45
  **Archivos:** static/src/chat_panel/NewConversationButton.js, static/src/chat_panel/hooks/useChat.js (createConversation, switchCompany), static/src/chat_panel/ChatPanel.js (integración listener)
  **Hecho cuando:** Click Nueva conversación genera UUID v4, limpia panel, nuevo conversation_id; cambiar empresa en switcher Odoo -> widget detecta y crea conversación vacía automáticamente; demo manual: 2 empresas, switch -> historial aislado por empresa.

- [ ] **T10. Componentes UI restantes + pulido: MessageList.js (load more), MessageItem.js, accesibilidad, i18n + tests HttpCase (9 tests) + demo final**
  **RF cubiertos:** RF-1, RF-2, RF-3, RF-4, RF-5, RF-6, RF-7, RF-10, RF-11, RF-43, RF-44, RF-47
  **Archivos:** static/src/chat_panel/MessageList.js, static/src/chat_panel/MessageItem.js, tests/test_chat_widget_http.py (nuevo HttpCase)
  **Hecho cuando:** 9 HttpCase tests en verde (widget abre, envío éxito, token vacío, 401, 500, nueva conversación, switch empresa, menú historial, truncamiento); demo manual completa: contador abre systray -> pregunta -> respuesta + warnings -> recarga -> historial persiste -> switch empresa -> nueva conversación vacía; suite completa >= 337 tests (0 failed); ruff/check-xml/trailing-whitespace/mixed-line-ending verdes.
