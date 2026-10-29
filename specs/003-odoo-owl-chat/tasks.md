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

- [x] **T7. Pivot a Discuss nativo: discuss_channel.py + res.users.api_token + res.config.settings**
  **RF cubiertos:** RF-1, RF-2, RF-3, RF-7, RF-9, RF-11
  **Archivos:** models/discuss_channel.py, models/res_users.py, models/res_config_settings.py, views/res_users_views.xml, views/res_config_settings_views.xml, data/res_users_data.xml
  **Hecho cuando:** Pivot de OWL a Discuss nativo (discuss.channel) completado; bot user `contafis_bot` auto-activado con password; message_post intercepta en 1-on-1; api_token en res.users (sin group restriction, editable en preferencias); webhook_url + auth_token en ir.config_parameter; tests suite 0 failed.

- [x] **T8. Llamada webhook FastAPI + timeout 60s + logging de latencia + manejo errores 401/5xx**
  **RF cubiertos:** RF-4, RF-5, RF-6
  **Archivos:** models/discuss_channel.py
  **Hecho cuando:** requests.post con timeout=60s; logging start_time + elapsed en cada request (timeout/error/success); FastAPI espera {"message": "text"} + header X-User-Token; respuestas 401/403/5xx/4xx mapeadas a mensajes amigables; tests suite 0 failed.

- [x] **T9. Formato warnings como texto plano (evita error OWL notIn) + body_is_html=False**
  **RF cubiertos:** RF-42, RF-46
  **Archivos:** models/discuss_channel.py
  **Hecho cuando:** warnings como dict -> extrae campo 'message'; render como bullet points Unicode (·) en texto plano; NO HTML crudo que rompa OWL; body_is_html removido; tests suite 0 failed.

- [x] **T10. Tests E2E MCP Chrome DevTools + verificación visual + cierre spec**
  **RF cubiertos:** RF-1, RF-2, RF-3, RF-4, RF-5, RF-6, RF-7, RF-9, RF-11
  **Archivos:** tests/test_discuss_bot.py (nuevo), MCP verification
  **Hecho cuando:** MCP Chrome DevTools: login admin -> abre canal ContaFis AI -> envía "Hola, ¿qué vencimientos tengo?" -> bot responde con 6 obligaciones reales + warnings formateados; 337 tests pasando (0 failed); spec 003 marcada COMPLETADA en SPEC.md; commit de cierre.
