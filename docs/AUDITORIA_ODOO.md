# Auditoría de seguridad, calidad y deuda técnica — `l10n_ve_compliance_manager`

| | |
|---|---|
| **Fecha** | 2026-11-16 |
| **Commit auditado** | `fde5ad4` (`main` = `origin/main`) |
| **Módulo** | `addons/l10n_ve_compliance_manager` (Odoo 19.0, versión `19.0.1.4.0`) |
| **Tamaño** | 91 archivos `.py` / 21.221 líneas · 47 `.xml` / 4.899 líneas · 36 archivos de test / 483 `def test_` |
| **Modo** | Solo lectura. **No se modificó código ni se ejecutaron tests.** |
| **Alcance** | Aislamiento multi-compañía/multi-cliente, wizards, malas prácticas ORM, cobertura de tests, deuda técnica |

---

## Veredicto

El módulo tiene una base sana en convenciones Odoo 19 (no hay `attrs=`, `states=`, `<tree>`, `t-raw`; hay 483 tests; las reglas de compañía existentes son globales y cubren los modelos del núcleo del negocio). **Pero no está listo para venderse como SaaS multi-cliente ni para reabrir 80/443 a Internet**: el aislamiento por cartera está incompleto en la cartelera fiscal, tres modelos financieros persistentes no tienen `ir.rule`, hay una credencial hardcodeada para un usuario interno y el `sid` de la sesión de Odoo se envía a un endpoint externo configurable.

**Semáforo:** 🔴 P0 (5) · 🟠 P1 (9) · 🟡 P2 (12).

---

## 1. Resumen ejecutivo

| ID | Sev. | Hallazgo | Evidencia | Esfuerzo |
|---|---|---|---|---|
| P0-01 | 🔴 | `cartelera.status` y `cartelera.evidence` no tienen regla de cartera ni de compañía; el menú expone todos los snapshots y evidencias | `security/ir_rule.xml` (sin reglas), `security/ir.model.access.csv:37-42`, `views/cartelera_status_views.xml:95-116` | M |
| P0-02 | 🔴 | `l10n.retention`, `l10n.ve.vat.return` y `l10n.ve.vat.book.generate` tienen `company_id` sin `ir.rule`; el último es `models.Model` con ACL de `base.group_user` | `models/retention.py:8`, `models/vat_return.py:20`, `models/vat_book_generate.py:6-10,19`, `security/ir.model.access.csv:25-27,48-52` | M |
| P0-03 | 🔴 | Usuario bot con contraseña hardcodeada `bot_unusable_password_123`, activo y con `base.group_user` | `data/res_users_data.xml:2,8,10,13-15` | S |
| P0-04 | 🔴 | El `sid` real de Odoo se envía como header `X-Odoo-Session` a una URL configurable; `requests.post` sigue redirects conservando el header | `models/discuss_channel.py:120-143,164`; `models/digitize_client.py:46-52` | M |
| P0-05 | 🔴 | (Operativo, no código) Usuario `demo` con contraseña trivial en la BD de producción | `docs/memory.md:1880,1885` | S |
| P1-01 | 🟠 | La validación de importación es un stub: `_validate_line()` devuelve `[]` y `action_import` acepta líneas en `draft` | `models/import_wizard.py:1798-1831,1854-1856` | S |
| P1-02 | 🟠 | Dos generadores de libro IVA calculan distinto (IVA, número de factura y número de control) | `models/account_move.py:110,126-127` vs. `models/vat_book_generate.py:116-118`, `models/vat_book_line.py:245,248` | M |
| P1-03 | 🟠 | `_post` ignora notas de crédito/débito; `button_draft` y `action_generate` borran/sobrescriben ediciones manuales | `models/account_move.py:155-171`; `models/vat_book_generate.py:188-193` | M |
| P1-04 | 🟠 | IGTF nunca se calcula: `calculate_amounts()` lo fija en `0.0` y la tasa 3% es código muerto | `models/retention_service.py:8-12,36` | S |
| P1-05 | 🟠 | `message_post` hace un `requests.post` síncrono con timeout de 60 s; un usuario puede agotar los workers | `models/discuss_channel.py:34-82,164` | L |
| P1-06 | 🟠 | URL de webhook/digitalización sin validación de esquema/host: SSRF a `169.254.169.254` y red interna | `models/discuss_channel.py:114`; `models/digitize_wizard.py:230-239`; `models/digitize_client.py:52` | M |
| P1-07 | 🟠 | `l10n.ve.import.log` sin `company_id` ni regla; el Excel adjunto contiene todas las filas importadas y no tiene `res_id` | `models/import_log.py:4-31`; `models/import_wizard.py:2180-2197`; ACL `28-30` | M |
| P1-08 | 🟠 | El historial de chats es una feature muerta (nadie lo escribe) y, si se escribe, todos los `account.group_account_user` lo leen | `models/chat_history.py:5-52`; sin `create` en `discuss_channel.py`; ACL `77-79` | M |
| P1-09 | 🟠 | La secuencia `l10n.retention` es global (`company_id=False`); la numeración no se aísla por compañía | `data/ir_sequence.xml:12-19`; `models/retention.py:13-20`; `docs/memory.md:1661,1700` | S |

> P2: 12 hallazgos en la sección 5. El detalle completo, con reproducción y fix, está en las secciones 2–5.

---

## 2. P0 — Seguridad

### P0-01 · Fuga de cartera en la cartelera fiscal (snapshots + evidencias)

**Qué pasa.** `l10n.ve.cartelera.status` y `l10n.ve.cartelera.evidence` son los únicos modelos hijos de `l10n.ve.compliance.client` que **no** tienen `ir.rule`. El padre sí tiene dos capas (cartera por `accountant_id` y compañía), pero los hijos no heredan nada: las reglas de Odoo no se propagan por relaciones.

**Evidencia.**
- `models/cartelera_status.py:9-14`: solo `client_id`, sin `company_id`.
- `models/cartelera_evidence.py:14-19`: solo `cartelera_status_id`, sin `company_id`.
- `security/ir_rule.xml`: no hay ninguna regla para `model_l10n_ve_cartelera_status` ni `model_l10n_ve_cartelera_evidence`.
- `security/ir.model.access.csv:37-42`: `account.group_account_user` tiene lectura de ambos modelos.
- `views/cartelera_status_views.xml:95-116`: acción + menú **"Snapshots Cartelera"** sin `groups`; el menú es visible para cualquier usuario interno y el listado no filtra por cartera.

**Impacto.** Un contador con solo el cliente A asignado puede abrir el menú y ver snapshots de todos los clientes de la compañía (estados, documentos faltantes, años/meses). Peor: puede leer las **evidencias fotográficas** de otros clientes (RIF, facturas, comprobantes) por RPC o desde el formulario del snapshot. Es una fuga de datos de terceros, no solo de la compañía.

**Reproducción (ORM, ejecutar en shell; no se ejecutó en esta auditoría).**
```python
Status = env['l10n.ve.cartelera.status'].with_user(accountant_a)
Status.with_context(allowed_company_ids=[company.id]).search([])
# Devuelve snapshots de clientes B, C... aunque accountant_a solo tenga A.
```

**Fix.**
1. Añadir `company_id` related almacenado en ambos modelos:
   ```python
   company_id = fields.Many2one(
       'res.company', related='client_id.company_id', store=True, index=True)
   ```
   (en evidencia: `related='cartelera_status_id.client_id.company_id'`).
2. Añadir reglas de cartera para `account.group_account_user` y `l10n_ve_compliance_accountant`:
   ```xml
   <field name="domain_force">[('client_id.accountant_id', '=', user.id)]</field>
   ```
   y para evidencia: `[('cartelera_status_id.client_id.accountant_id', '=', user.id)]`.
3. Añadir reglas globales de compañía (`[('company_id', 'in', company_ids)]`) para los mismos modelos.
4. Poner `groups=` al menú/acción o, mejor, dejar el menú solo para managers y forzar el flujo desde el cliente.
5. Tests: dos clientes A/B con contadores distintos, snapshots y evidencias; `assertRaises(AccessError)` al leer B como A, y `search_count` acotado.

**Esfuerzo:** M (modelo + reglas + 4–6 tests).

---

### P0-02 · Modelos financieros persistentes con `company_id` sin `ir.rule`

**Qué pasa.** Hay 11 modelos con `company_id`. Solo 4 de ellos tienen regla de compañía (`chat.history`, `compliance.client`, `islr.reconciliation`, `vat.book.line`); `islr.reconciliation.line` no tiene el campo pero hereda la regla por la reconciliación. Los tres persistentes que faltan son financieros y contienen datos sensibles; los cuatro wizards transitorios restantes tienen riesgo menor, pero uno de ellos (`vat.book.generate`) **no es transitorio**.

**Evidencia.**

| Modelo | `company_id` | `ir.rule` | ACL de lectura | Riesgo |
|---|---|---|---|---|
| `l10n.retention` | `retention.py:8` | ❌ | `account.group_account_user` (`csv:25`) | 🔴 P0 |
| `l10n.ve.vat.return` | `vat_return.py:20` | ❌ | `account.group_account_user` (`csv:50`) | 🔴 P0 |
| `l10n.ve.vat.book.generate` | `vat_book_generate.py:19` | ❌ | `base.group_user` (`csv:48`) | 🔴 P0 |
| `l10n.ve.chat.history` | `chat_history.py:17` | ✅ (compañía; sin regla por usuario) | `account.group_account_user` (`csv:77`) | 🟡 P1 (ver P1-08) |
| `l10n.ve.compliance.client` | `compliance_client.py:13` | ✅ | `account.group_account_user` | OK |
| `l10n.ve.islr.reconciliation` | `islr_conciliation.py` | ✅ | `account.group_account_user` | OK |
| `l10n.ve.vat.book.line` | `vat_book_line.py` | ✅ | `account.group_account_user` | OK |
| `l10n.ve.digitize.wizard` | `digitize_wizard.py:30` | ❌ | `base.group_user` (`csv:80`) | 🟡 P2 (transient) |
| `l10n.ve.import.wizard` | `import_wizard.py:95` | ❌ | `base.group_user` (`csv:31`) | 🟡 P2 (transient) |
| `l10n.ve.physical.invoice.wizard` | `physical_invoice_wizard.py` | ❌ | `base.group_user` (`csv:53`) | 🟡 P2 (transient) |
| `l10n.ve.vat.book.export.wizard` | `vat_book_export_wizard.py` | ❌ | `base.group_user` (`csv:57`) | 🟡 P2 (transient) |

**Impacto.** Un usuario con `allowed_company_ids = [A, B]` (caso normal de un contador con varias empresas) ve retenciones, planillas 99030 y wizards de generación de ambas compañías. En `vat.book.generate` el ACL es `base.group_user` **full CRUD** sobre un `models.Model` persistente: cualquier usuario interno puede crear/borrar registros de generación de cualquier compañía y dejar basura permanente. `vat.return` no tiene `currency_id`, así que además mezcla montos de monedas distintas sin advertirlo (P2-11).

**Fix.**
1. Tres reglas globales:
   ```xml
   <record id="rule_l10n_retention_company" model="ir.rule">
     <field name="model_id" ref="model_l10n_retention"/>
     <field name="domain_force">[('company_id', 'in', company_ids)]</field>
   </record>
   ```
   Ídem `model_l10n_ve_vat_return` y `model_l10n_ve_vat_book_generate`.
2. Bajar el ACL de `vat.book.generate` de `base.group_user` a `account.group_account_manager` + `l10n_ve_compliance_accountant` (el menú ya está restringido a manager en `views/vat_book_generate_views.xml:50`).
3. Evaluar pasar `l10n.ve.vat.book.generate` a `TransientModel` (hoy declara `_transient_max_count`/`_transient_max_hours`, que un `Model` ignora; ver P2-03).
4. Tests: crear registros en A y B, `with_user` + `with_context(allowed_company_ids=[A])`, `assertEqual(search_count, 1)` y `assertRaises(AccessError)` en create/unlink.

**Esfuerzo:** M.

---

### P0-03 · Credencial hardcodeada del bot (`bot_unusable_password_123`)

**Qué pasa.** El usuario `contafis_bot` se crea con contraseña literal en el XML de datos, `active=True`, `share=False` (usuario interno) y `group_ids = base.group_user`.

**Evidencia.** `data/res_users_data.xml:2` (`noupdate="1"`), `:8` (`<field name="password">bot_unusable_password_123</field>`), `:10` (`share=False`), `:13-15` (`base.group_user`).

**Impacto.** Cualquiera con acceso al repositorio (o a un backup/dump) conoce una credencial válida en producción. El bot puede autenticarse en `/web/session/authenticate` y usar el cliente web como usuario interno: leer partners, usuarios, conversaciones y todo lo que permita `base.group_user`. No es admin, pero es un foothold real y una violación de secreto. `noupdate="1"` hace que rotar la contraseña en la BD **no** se revierta al actualizar, pero también que el XML siga siendo la fuente de la verdad en instalaciones nuevas.

**Fix.**
1. Eliminar la línea `<field name="password">` del XML. Un usuario sin contraseña no puede autenticarse; el bot solo necesita existir como autor de mensajes (`message_post` con `sudo()` ya está implementado).
2. En producción, ejecutar una vez: `env.ref('l10n_ve_compliance_manager.user_contafis_bot').write({'password': False})` y cerrar sus sesiones (`res.users` → `_clear_session`/`session_ids`).
3. Test: `assertFalse(bot._check_credentials({'password': 'bot_unusable_password_123', 'type': 'password'}, env))` y que el XML no contenga `password`.
4. Si se necesita que el bot reciba correo, usar `mail` alias, no login.

**Esfuerzo:** S.

---

### P0-04 · Reenvío del `sid` de Odoo a un endpoint externo configurable

**Qué pasa.** El pivote de la spec 002 T1 eliminó el `api_token` personal y pasó a mandar el **session id real** de Odoo como header `X-Odoo-Session` al asistente externo, tanto en chat como en digitalización. El endpoint se lee de `ir.config_parameter` (editable por admin) y `requests.post` **sigue redirects por defecto**, conservando los headers custom.

**Evidencia.**
- `models/discuss_channel.py:120-127` lee `request.session.sid`; `:138-143` arma `X-Odoo-Session`; `:164` `requests.post(..., timeout=60)`.
- `models/digitize_client.py:46-52`: mismo header, sin `allow_redirects=False`.
- `models/digitize_wizard.py:230-239`: URL y API key desde `ir.config_parameter`.
- `models/res_config_settings.py:7-21` y `data/ir_config_parameter_data.xml:7-22`: URL/token en texto plano.
- `docs/memory.md:1327`: confirma que se envía "el sid real".

**Impacto.**
1. **Robo de sesión:** un endpoint comprometido, un DNS poisoning o un admin malicioso recibe un `sid` válido y puede suplantar al usuario en Odoo (el `sid` es la cookie de sesión; equivale a la contraseña).
2. **Redirect leak:** `requests` solo elimina `Authorization` en redirects cross-host; `X-Odoo-Session` y `X-API-Key` se conservan. Un `302` a `https://attacker.example` entrega ambos secretos.
3. **Superficie:** la URL es `http://` por defecto y no hay allowlist de hosts.

**Fix.**
1. **No enviar el `sid`.** Firmar un token efímero (JWT/HMAC) con `{uid, company_id, exp, jti}` y un secreto compartido; TTL ≤ 60 s, un solo uso, validado por el asistente. Si el asistente necesita consultar Odoo, que lo haga server-to-server con un usuario de servicio y permisos mínimos, no con la sesión del contador.
2. `requests.post(..., allow_redirects=False)` en ambos clientes.
3. Exigir `https://`, allowlist de hosts y bloquear IPs privadas/link-local (ver P1-06).
4. Rotar `l10n_ve_chat.auth_token` y `l10n_ve_digitize.*` si estuvieron expuestos; revisar logs de nginx del asistente por redirects.
5. Test con `responses`/`requests_mock`: un `302` no debe reenviar `X-Odoo-Session`; el payload no debe contener el `sid`.

**Esfuerzo:** M–L (cambio de contrato con el backend).

---

### P0-05 · (Operativo) Usuario `demo` con contraseña trivial en producción

**Qué pasa.** El usuario `Demo` (`demo@contafis.local` / `demo`) vive en la misma BD `contea` que producción, con `share=False` y grupos de contabilidad. El servidor está pausado y el 8069 está cerrado, pero 80/443 siguen publicados vía nginx.

**Evidencia.** `docs/memory.md:1880` (credenciales) y `:1885` (pendiente explícito).

**Impacto.** Al reabrir 80/443, cualquiera que conozca o adivine la demo entra como usuario interno con acceso a la contabilidad de la empresa demo. Si la demo comparte `allowed_company_ids` con la empresa real, el impacto escala.

**Fix (antes de reabrir).**
1. `active=False` o contraseña fuerte + `share=True` (portal) si se quiere demo pública.
2. Verificar `company_ids` = solo empresa demo y `accountant_id` del cliente demo = usuario demo.
3. No reutilizar la BD de producción para demos comerciales; usar un snapshot separado.

**Esfuerzo:** S.

---

## 3. P1 — Bugs y correctitud

### P1-01 · La validación de importación es un no-op

**Qué pasa.** `action_validate()` llama a `_validate_line()`, que tiene tres `TODO` y **siempre devuelve `[]`**. Por eso todas las líneas se marcan `validated`. Además, `action_import()` incluye explícitamente las líneas en estado `draft`, así que se puede importar sin haber validado nada.

**Evidencia.** `models/import_wizard.py:1818-1831` (stub), `:1798-1808` (marca `validated`), `:1854-1856` (`state in ('validated', 'draft')`), `views/import_views.xml:20` (botón "Validar") y `:148` ("Validar Sintaxis", que sí llama a `import_line._validate_syntax()`).

**Impacto.** El usuario ve "Validación completada" y confía en datos que nunca se validaron. En modo `lax` (default) las filas inválidas se importan o fallan una por una con errores de ORM; en `strict` solo se detectan las que ya estaban en `error`. Es una falsa garantía con impacto directo en la calidad del libro/planilla.

**Fix.**
1. Implementar `_validate_line()` delegando en `line._validate_syntax()` + `line._validate_reference()` + validaciones de negocio (RIF, período, montos, duplicados).
2. `action_import()` debe rechazar `draft` en modo `strict` y advertir en `lax` ("N filas sin validar").
3. Test: fila con RIF inválido/fecha mal formada → `state='error'`; import en strict con draft → `UserError`.

**Esfuerzo:** M.

---

### P1-02 · Dos generadores de libro IVA que producen resultados distintos

**Qué pasa.** Hay dos caminos para crear `l10n.ve.vat.book.line`:
- **Automático** (`account_move._post` → `_generate_vat_book_line`): IVA = `tax.amount * base / 100`; número de factura = `l10n_ve_invoice_number or name`; control = `l10n_ve_control_number or ref or name`.
- **Manual** (`vat.book.generate` → `_prepare_book_line_vals`): IVA = `price_total - price_subtotal`; número de factura = `move.name`; control = `move.ref or move.name`.

**Evidencia.** `models/account_move.py:110,126-127`; `models/vat_book_generate.py:116-118`; `models/vat_book_line.py:245,248`.

**Impacto.** La misma factura puede declarar un IVA distinto según se posteó o se generó desde el wizard. Ejemplos: impuesto fijo (`amount_type='fixed'`, donde `tax.amount` es un monto absoluto y no un porcentaje), impuestos que no son IVA (IGTF) que el manual suma dentro de `price_total - price_subtotal`, o redondeo por línea vs. por factura. Además el manual **pierde el número de factura física SENIAT** y el número de control, que son obligatorios en el libro.

**Fix.** Un solo servicio `l10n.ve.vat.book.line._prepare_from_move(move)` que:
1. Use `tax.compute_all()` (o `line.price_total - line.price_subtotal` **solo** para los impuestos del grupo IVA) y redondee con `currency.round()`.
2. Use `l10n_ve_invoice_number or name` y `l10n_ve_control_number or ref or name`.
3. Sea llamado por `_post`, por `action_regenerate_vat_book_line` y por `vat.book.generate`.
4. Test de paridad: misma factura por ambos caminos → `base_general`, `vat_general`, `invoice_number`, `control_number` idénticos.

**Esfuerzo:** M.

---

### P1-03 · Notas de crédito y ediciones manuales del libro

**Qué pasa.**
- `_post` solo genera libro para `in_invoice`/`out_invoice`; las notas de crédito/débito (`in_refund`/`out_refund`) no generan línea automática.
- `button_draft` borra **todas** las líneas `source='odoo_invoice'`, incluidas las marcadas `is_manually_modified=True`, sin confirmación.
- `vat.book.generate.action_generate` busca la línea existente por `partner/invoice_number/control/period/operation/retention_direction` y hace `existing.write(vals)`, sobrescribiendo ediciones manuales sin mirar `is_manually_modified`.
- El wizard de confirmación solo protege `action_regenerate_vat_book_line`, no los otros dos caminos.

**Evidencia.** `models/account_move.py:155-171`; `models/vat_book_generate.py:188-193`; `models/regenerate_confirm_wizard.py:38-43`.

**Impacto.** Pérdida silenciosa de ajustes manuales (el contador corrige una base y al re-generar desaparece) y libro incompleto cuando hay notas de crédito. En un cierre fiscal esto es un retrabajo costoso.

**Fix.**
1. `_post`: incluir `in_refund`/`out_refund` con signo negativo (ya está resuelto en `_prepare_book_line_vals:239`).
2. `button_draft`: si hay líneas `is_manually_modified`, devolver el wizard de confirmación (mismo patrón que `action_regenerate_vat_book_line`) o preservarlas.
3. `action_generate`: no sobrescribir líneas manuales; crear una nueva o pedir confirmación.
4. Tests: refund genera línea negativa; edición manual sobrevive a `button_draft` y a `action_generate`.

**Esfuerzo:** M.

---

### P1-04 · El IGTF nunca se calcula

**Qué pasa.** `retention_service.calculate_amounts()` devuelve `'igtf': 0.0` hardcodeado. La tasa `igtf: 3.0` de `DEFAULT_RATES` nunca se usa. `generate_retentions()` itera `('islr', 'iva', 'igtf')`, pero el monto siempre es 0 y no crea retención.

**Evidencia.** `models/retention_service.py:8-12,31-37`.

**Impacto.** Si el producto promete retenciones de IGTF (el manifest y la capability 04 lo incluyen), la declaración queda incompleta para pagos en divisa/extranjero. Es un error fiscal silencioso: el usuario no ve ninguna advertencia.

**Fix.**
1. Implementar la regla: IGTF 3% sobre el pago en divisa cuando aplique (billetes/fondos en moneda extranjera), con la exención en VES y las excepciones (pagos a organismos, nómina, etc., según la norma vigente).
2. Si no se va a implementar, **quitar** `igtf` del `DEFAULT_RATES`, del loop y de la UI para no prometer una capacidad inexistente.
3. Test: factura en USD con pago en divisa → retención IGTF 3%; factura en VES → 0.

**Esfuerzo:** M (regla de negocio) / S (si se elimina).

---

### P1-05 · HTTP síncrono de 60 s dentro de `message_post`

**Qué pasa.** Cada mensaje a un canal 1-a-1 con el bot ejecuta `super().message_post()` y luego `requests.post(..., timeout=60)` en el mismo request/worker, antes del commit. No hay cola, reintento ni circuit breaker.

**Evidencia.** `models/discuss_channel.py:34-82` (flujo), `:164` (timeout 60 s).

**Impacto.** Un usuario puede abrir 5–10 conversaciones y mantener ocupados todos los workers de Odoo durante un minuto cada una (DoS de disponibilidad). En `workers=0` (dev) bloquea el hilo del request y degrada toda la instancia. Además el mensaje del usuario ya quedó posteado aunque el webhook falle, generando estados inconsistentes.

**Fix.**
1. Encolar la llamada: crear un modelo `l10n.ve.chat.queue` (o usar `queue_job` de OCA) y procesar por cron; responder al usuario de inmediato con "procesando".
2. Si se mantiene síncrono, bajar el timeout a 5–10 s, añadir reintentos con backoff y un circuit breaker por host.
3. Test: `requests.post` mockeado que tarda > timeout no bloquea el `message_post` (medir con `freezegun`/mock).

**Esfuerzo:** L.

---

### P1-06 · URL de webhook/digitalización sin allowlist (SSRF)

**Qué pasa.** `l10n_ve_chat.webhook_url` y `l10n_ve_digitize.url` se leen de `ir.config_parameter` y se pasan directo a `requests.post`. No se valida esquema, host, IP ni redirects.

**Evidencia.** `models/discuss_channel.py:114`; `models/digitize_wizard.py:230-239`; `models/digitize_client.py:52`; `models/res_config_settings.py:7-21`.

**Impacto.** Un admin comprometido (o un error de configuración) puede apuntar a `http://169.254.169.254/latest/meta-data/iam/security-credentials/` y usar el servidor Odoo como proxy hacia la red interna/AWS. El response se intenta parsear como JSON; aunque no se muestre, el request se ejecuta y permite escaneo de puertos/tiempos. Sumado a P0-04, un redirect permite exfiltrar headers.

**Fix.**
1. Validar en `res.config.settings` y en el cliente: `https` obligatorio, host en allowlist (`l10n_ve_chat.allowed_hosts`), bloquear `localhost`, `127.0.0.0/8`, `10/8`, `172.16/12`, `192.168/16`, `169.254/16`, `::1`, `fc00::/7`.
2. `allow_redirects=False` y `timeout` máximo 15 s.
3. Loguear solo el host, nunca la URL completa con query/token.
4. Test: URL `http://169.254.169.254` → `UserError`; `https://evil.example` fuera de allowlist → `UserError`.

**Esfuerzo:** M.

---

### P1-07 · `import.log` sin compañía y con Excel de datos sensibles

**Qué pasa.** `l10n.ve.import.log` no tiene `company_id` ni `ir.rule`. Guarda `file_name`, contadores, `record_ids` (JSON) y un adjunto Excel con **todas las filas importadas** (fecha, estado, registro, modelo, error). El adjunto se crea con `res_model='l10n.ve.import.log'` pero **sin `res_id`** (el log todavía no existe).

**Evidencia.** `models/import_log.py:4-31`; `models/import_wizard.py:2180-2197`; ACL `security/ir.model.access.csv:28-30` (lectura para `account.group_account_user`).

**Impacto.** Cualquier usuario de facturación puede leer logs y descargar el Excel de importaciones de otros clientes/compañías, con nombres, montos y errores. El adjunto huérfano además queda accesible por su `id` si se filtra la URL `/web/content/<id>`.

**Fix.**
1. Añadir `company_id` (default `env.company`, required, index) y regla global de compañía; opcionalmente regla por `user_id` para no-admin.
2. Crear primero el log y luego el adjunto con `res_id=log.id`; o crear el adjunto después y hacer `log.write({'attachment_id': attachment.id})`.
3. Restringir la lectura a `account.group_account_manager`/`l10n_ve_compliance_accountant` (no a todo billing).
4. Test: log en A invisible desde B; adjunto ligado al log.

**Esfuerzo:** M.

---

### P1-08 · Historial de chats: feature muerta y lectura por todos los billing

**Qué pasa.** `l10n.ve.chat.history` tiene modelo, vistas, menú, ACL, reglas y 6 tests, pero **ningún código del módulo crea registros**. `discuss_channel.message_post` postea en `mail.message` y nunca escribe el historial. El menú "Historial de chats" siempre estará vacío. Si un backend externo lo llenara por RPC, la regla actual (`company_id in company_ids`) permite que **cualquier** `account.group_account_user` lea las conversaciones de todos los usuarios de la compañía.

**Evidencia.** `models/chat_history.py:5-52`; `models/discuss_channel.py` (sin `create` de `l10n.ve.chat.history`); `security/ir_rule.xml:110-126`; ACL `csv:77-79` (write/create para billing); `views/menu.xml:108-112`.

**Impacto.** (a) Feature prometida que no funciona (soporte/confusión). (b) Si se activa sin cambiar la regla, fuga de conversaciones entre contadores (pueden contener datos de clientes).

**Fix.**
1. Decidir: **implementar** (crear un registro por mensaje en `message_post`, con `conversation_id=self.id`, `user_id`, `company_id`) o **eliminar** modelo/menú/tests.
2. Si se implementa, añadir regla `[('user_id', '=', user.id)]` para no-admin y quitar `write` del ACL de billing.
3. Test: usuario A no ve el historial de B; el bot crea 2 registros por intercambio.

**Esfuerzo:** M.

---

### P1-09 · Secuencia de retención global (sin aislamiento por compañía)

**Qué pasa.** `sequence_l10n_retention` se define sin `company_id`, por lo que es una secuencia global. `retention.name` usa `with_company(self.company_id or self.env.company).next_by_code(...)`. En una instalación multi-compañía, la secuencia global se comparte (o, si el fallback no aplica, el alta falla). El `docs/memory.md:1661,1700` ya lo registra como follow-up alto.

**Evidencia.** `data/ir_sequence.xml:12-19`; `models/retention.py:13-20`; `docs/memory.md:1661,1700`.

**Impacto.** Numeración de retenciones compartida entre empresas/clientes (se puede inferir volumen) o error de "no hay secuencia" al crear en una compañía distinta de la principal. No es una fuga de datos, pero rompe el aislamiento que el resto del módulo sí respeta.

**Fix.**
1. Crear una secuencia por compañía (en `res.company.create` o en un `post_init`/migración para las existentes).
2. O documentar explícitamente que la numeración es global y añadir un prefijo por compañía.
3. Test: retención en A y B → prefijos/números independientes; `next_by_code` no devuelve `False`.

**Esfuerzo:** S.

---

## 4. Matriz de wizards y `with_company`

La consigna era verificar si la mayoría usa `with_company(self.company_id)`. El conteo mecánico es engañoso: **5 de 10 wizards usan `with_company`** (specs 008 a 008-F ya endurecieron importación, factura física, libro, export y planilla). Los otros 5 **no lo necesitan** porque operan sobre un registro que ya lleva la compañía o sobre catálogos globales. El riesgo real está en los modelos sin regla (P0-02), no en el `with_company`.

| Wizard | Acciones | `with_company` | Veredicto |
|---|---|---|---|
| `l10n.ve.import.wizard` | `load_file`, `validate`, `import` | ✅ 3/3 | OK; `preview`/`validate_syntax`/`reset` no escriben con compañía |
| `l10n.ve.physical.invoice.wizard` | `action_create_and_post` | ✅ 1/1 | OK; inyecta `company_id` en `account.move` |
| `l10n.ve.vat.book.generate` | `load_moves`, `generate`, `reset` | ✅ 3/3 | OK; ojo: el modelo es persistente (P0-02/P2-03) |
| `l10n.ve.vat.book.export.wizard` | `action_export_xlsx` | ✅ 1/1 | OK |
| `l10n.ve.vat.return` | `load_from_book`, `calculate` | ✅ 2/2 | OK; `open_book_lines` usa domain + `allowed_company_ids` |
| `l10n.ve.digitize.wizard` | `digitize`, `apply_to_invoice`, `digitize_batch`, `digitize_line` | ❌ 0/4 | **No requiere**: `_build_apply_to_invoice_action` inyecta `default_company_id` (008-B); no crea asientos |
| `l10n.ve.cartelera.evidence.wizard` | `action_upload` | ❌ 0/1 | **No aplica**: no tiene `company_id`; el gap es del modelo (P0-01) |
| `l10n.ve.obligation.payment.wizard` | `action_confirm` | ❌ 0/1 | **No aplica**: opera sobre `obligation`, que ya tiene compañía y regla |
| `l10n.ve.regenerate.confirm.wizard` | `action_confirm` | ❌ 0/1 | **No aplica**: opera sobre `move` y crea líneas con `company_id` explícito |
| `l10n.ve.copy.calendar.wizard` | `action_copy` | ❌ 0/1 | **No aplica**: catálogo global; el riesgo es de integridad por ACL `base.group_user` |
| `l10n.ve.vat.book.line` (no wizard) | `action_open_export_wizard` | ❌ 0/1 | **OK**: pasa `default_company_id` por contexto |

**Conclusión:** no hay un bug generalizado de `with_company`. Quedan dos acciones de bajo riesgo (`import.preview`, `import.validate_syntax`) que no lo necesitan. Si se quiere uniformidad, añadir `self = self.with_company(self.company_id)` al inicio de **todas** las acciones públicas, pero no es un bloqueante.

---

## 5. P2 — Deuda técnica y mejoras

| ID | Hallazgo | Evidencia | Acción |
|---|---|---|---|
| P2-01 | `_sql_constraints` deprecado en Odoo 19; warning en cada carga del registry | `models/chat_history.py:46-52` | Migrar a `models.Constraint('UNIQUE(...)', 'msg')` |
| P2-02 | `api_token` muerto: ya no se usa tras el pivote a `X-Odoo-Session`; sin `groups=` | `models/res_users.py:8-18`; `tests/test_chat_history.py:181-208` | Eliminar campo, vista y tests; o `groups="base.group_system"` y `readonly` |
| P2-03 | `l10n.ve.vat.book.generate` es `models.Model` y declara `_transient_max_*` inertes; crece sin límite | `models/vat_book_generate.py:6-10` | Pasar a `TransientModel` o añadir cron de limpieza y ACL de manager |
| P2-04 | `import.log` con tipos débiles: `wizard_id` Char sin FK, `import_type` Char (debería Selection), `record_ids` Text JSON, adjunto sin `res_id` | `models/import_log.py:9-31`; `models/import_wizard.py:2180-2197` | `Many2one` a wizard (o `Integer`), Selection espejo de `import_type`, `fields.Json`, adjunto con `res_id` |
| P2-05 | Código muerto: `_get_conversation_history()` no se usa; `chat.history` no se escribe | `models/discuss_channel.py:205-227`; `models/chat_history.py` | Usar o borrar; ver P1-08 |
| P2-06 | N+1 en computes de cliente: `search` de `document.type` dentro del loop y `filtered` anidados | `models/compliance_client.py:121-167` | `search` fuera del loop, `read_group`/`mapped`, o `store=True` + cron |
| P2-07 | Menús/acciones sin `groups`: raíz "Cumplimiento VE", Clientes, Obligaciones, Documentos, Alertas, Snapshots, Importar | `views/menu.xml:15-113`; `views/import_views.xml:334-338`; `views/cartelera_status_views.xml:112-116` | Poner `groups=` o dejar solo managers; el ACL protege pero la UI invita a errores |
| P2-08 | `cartelera_html` con `sanitize=False`; hoy todo va con `escape()`, pero es frágil | `models/compliance_client.py:68-72,195-259` | `sanitize=True` o un helper `_safe_markup()` con revisión obligatoria |
| P2-09 | `except Exception` amplios (8 en modelos), algunos con `pass` | `models/import_wizard.py:1894`, `discuss_channel.py:78,124`, `digitize_client.py:28`, etc. | Capturar excepciones específicas; loguear con contexto; nunca `pass` silencioso |
| P2-10 | `post_init_hook` con SQL crudo y no-op documentado | `hooks/post_init_hook.py:1-24` | Convertir en migración versionada o eliminar |
| P2-11 | `vat.return` sin `currency_id`; 48 ítems `fields.Float` sin moneda | `models/vat_return.py:35-56` | Añadir `currency_id` + `Monetary`, o documentar que es solo VES |
| P2-12 | `print()` en seed demo; `res.partner.rif` no existe (ramas muertas); `import_wizard.py` 1.952 líneas (god object) | `demo/seed_demo_data.py:782-1195`; `docs/memory.md:1638`; `models/import_wizard.py` | `_logger`, borrar ramas muertas, extraer servicios de importación |

**Nota:** los catálogos globales (`document.type`, `institution`, `obligation.type`, `seniat.calendar`, `bank.holiday`) **no** tienen `company_id` a propósito; no se reportan como fuga.

---

## 6. Cobertura de tests

**Estado:** 36 archivos, 483 tests, todos `@tagged('post_install', '-at_install')`. No se ejecutaron en esta auditoría (restricción explícita).

| Área | Archivos | Tests | ¿Cubre aislamiento? |
|---|---|---|---|
| ISLR | `test_islr_conciliation.py` | 72 | ✅ `test_multi_company_import_islr` (6) |
| Digitalización | `test_digitize_wizard.py`, `test_digitize_batch.py` | 86 | ✅ `test_multi_company_digitize` (4) |
| Importación | `test_import_wizard.py`, `test_import_vat_book.py`, `test_import_cartelera.py` | 44 | ✅ `test_multi_company_wizards` (4) + UX (15) |
| Cartelera | `test_cartelera_status.py`, `test_cartelera_evidence.py` | 19 | ❌ **no hay test de cartera/compañía** |
| Retenciones | `test_retention_service.py` | 9 | ⚠️ cubre cálculo, **no aislamiento** |
| Planilla IVA | `test_vat_return.py` | 9 | ⚠️ cubre cálculo, **no aislamiento** |
| Libro IVA | `test_vat_book*.py` (6 archivos) | 37 | ✅ `test_vat_book.py` (3) + paridad parcial |
| Bot / chat | `test_discuss_bot.py`, `test_chat_history.py` | 14 | ⚠️ historial sin escritura real |
| Obligaciones | `test_obligation*.py` (4) | 25 | ✅ `test_multi_company` (6) |
| Wizards varios | `test_physical_invoice_wizard.py`, `test_obligation_payment_wizard.py` | 21 | ⚠️ faltan `copy_calendar`, `regenerate_confirm` |
| Multi-compañía (transversal) | `test_multi_company*.py` (5) | 35 | ✅ client/obligation/document/vat.book/islr/import/digitize |

**Modelos nunca referenciados en tests:** `l10n.ve.digitize.batch.line`, `l10n.ve.digitize.line`, `l10n.ve.import.log`.

**Tests que faltan (prioridad):**
1. `test_multi_company_cartelera.py`: status/evidence A vs. B, `assertRaises(AccessError)`.
2. `test_multi_company_financial.py`: retention, vat.return, vat.book.generate A vs. B.
3. `test_bot_security.py`: el bot no puede autenticarse; el XML no tiene password.
4. `test_external_http.py`: `allow_redirects=False`; no se envía `sid`; URL no allowlisted → `UserError`.
5. `test_import_validation.py`: `_validate_line` real; strict rechaza draft.
6. `test_vat_book_parity.py`: auto vs. wizard; refunds negativos; edición manual preservada.
7. `test_retention_igtf.py`: USD vs. VES.
8. `test_import_log.py`: compañía y adjunto ligado.

**Objetivo:** pasar de 483 a ≥ 510 tests, con al menos 12 de aislamiento negativos (no solo "el admin ve").

---

## 7. Plan de acción

### Sprint 0 — Bloqueante (1–2 días, antes de reabrir 80/443)

| # | Tarea | Criterio de aceptación |
|---|---|---|
| 1 | P0-01 reglas + `company_id` en cartelera | Menú inaccesible para no asignados; `AccessError` al leer B; tests verdes |
| 2 | P0-02 reglas de retention/vat.return/vat.book.generate | `search_count` acotado por `allowed_company_ids`; ACL de generate a manager |
| 3 | P0-03 quitar password del bot + rotar en prod | `_check_credentials` falla; XML sin `password`; sesiones cerradas |
| 4 | P0-04 `allow_redirects=False` + token firmado (o al menos no enviar `sid` a hosts no allowlisted) | Test de redirect no filtra headers; contrato con el asistente actualizado |
| 5 | P0-05 desactivar `demo` o password fuerte | Login demo falla; `company_ids` solo demo |
| 6 | Regresión | `0 failed, 0 error(s) of ≥ 483 tests`; CI + E2E verdes; `git status` limpio |

### Sprint 1 — Correctitud (3–5 días)

P1-01 (validación real), P1-02 (servicio único de libro), P1-03 (refunds + manuales), P1-04 (IGTF o quitarlo), P1-06 (allowlist), P1-07 (import.log), P1-08 (historial: implementar o borrar), P1-09 (secuencia). P1-05 (async) puede ir a Sprint 2 si se acota el timeout a 10 s como mitigación temporal.

**Criterio:** paridad auto/manual, refunds negativos, validación rechaza basura, IGTF probado, logs aislados, ≥ 500 tests.

### Sprint 2 — Deuda (3–5 días)

P2-01 a P2-12. Priorizar P2-02 (borrar `api_token`), P2-03 (transient/cleanup), P2-06 (N+1), P2-07 (menús), P2-12 (god object). **Criterio:** sin warnings de `_sql_constraints`, sin campos muertos, benchmark de 100 clientes < 2 s en lista, ≥ 510 tests.

**Estimación total:** 7–12 días de un desarrollador Odoo senior, sin contar el cambio de contrato con el backend del asistente (P0-04/P1-05).

---

## 8. Checklist antes de reabrir 80/443

- [ ] `demo` desactivado o con contraseña fuerte; `company_ids` solo demo.
- [ ] Bot sin contraseña; sesiones del bot cerradas; `noupdate` revisado.
- [ ] Reglas P0-01/P0-02 desplegadas y verificadas con un usuario limitado (no admin, no superusuario).
- [ ] `requests.post` sin `allow_redirects` y sin `X-Odoo-Session` hacia hosts no allowlisted.
- [ ] `l10n_ve_chat.auth_token` y `l10n_ve_digitize.*` rotados si estuvieron expuestos.
- [ ] Backup de `contea` + prueba de restore.
- [ ] `git status --short` limpio; CI, E2E y CD verdes.
- [ ] Revisar logs de nginx del asistente por redirects/401 anómalos.

---

## 9. Falsos positivos y riesgos aceptados (para no inflar el reporte)

- **`sudo()` no es excesivo.** Solo hay 3 usos en producción: lectura de `ir.config_parameter` (`cartelera_evidence.py:98`, `discuss_channel.py:86,114,146`) y `message_post` como bot (`discuss_channel.py:93,106,255`). Están acotados y justificados.
- **No hay `search([])` peligroso en código de usuario.** El único de modelos es `cartelera_status.py:170`, dentro del cron mensual global (root), que es intencional.
- **`sanitize=False` en `cartelera_html` hoy es seguro**: todas las interpolaciones usan `escape()` (`compliance_client.py:232,252-253`). Es deuda latente, no una XSS actual.
- **La ausencia de `with_company` en 5 wizards no es un bug** (ver sección 4); el `company_id` viaja por contexto o por el registro.
- **Los catálogos globales no llevan compañía a propósito** (instituciones, tipos de documento, calendario SENIAT, feriados).
- **`networkidle` en E2E** ya está acotado con `timeout: 5000` y `.catch(() => {})` (`tests/e2e/wizard_physical_invoice.spec.js:83-85`); no es un bug de producto.

---

## Anexo A — Método y evidencia

- Inventario: 91 `.py` / 21.221 líneas; 47 `.xml` / 4.899 líneas; 36 archivos de test / 483 `def test_`; 32 modelos con `_name`; 87 filas ACL; 4 grupos referenciados en ACL.
- Búsquedas: `company_id` vs. `ir.rule`; `with_company` vs. `def action_`; `sudo()`; `search([])`; `attrs=|states=|<tree|t-raw`; `_sql_constraints`; `except Exception`; `TODO|FIXME`.
- Verificación de reglas: `security/ir_rule.xml` cubre 8 modelos (`compliance.client`, `obligation`, `document`, `alert`, `vat.book.line`, `islr.reconciliation`, `islr.reconciliation.line`, `chat.history`).
- No se ejecutaron tests ni se abrió el navegador; las reproducciones ORM son propuestas de verificación, no resultados de esta sesión.
- **No se modificó ningún archivo de código.** El único archivo creado es este reporte.

---

*Fin del reporte.*
