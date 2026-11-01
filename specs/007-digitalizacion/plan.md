# Plan 007 - Wizard de Digitalización

Spec: `specs/007-digitalizacion/spec.md`
Baseline: `0 failed, 0 error(s) of 344 tests` (rama `19.0`, commit `2ddf9aa`).

## 1. Arquitectura

Flujo de dos pasos, con una sola frontera hacia el exterior:

```
[Menú Impuestos → Digitalizar Factura]
        ▼
l10n.ve.digitize.wizard  (TransientModel, estado draft/done/error)
   │  action_digitize()
   │      ├─ valida imagen (extensión, tamaño)          ← ValidationError
   │      ├─ obtiene sid (patrón discuss_channel)        ← sin sid ⇒ UserError
   │      ├─ post_digitize(...)                          ← requests.post (mockeable)
   │      └─ mapea errores HTTP / JSON inválido           ← UserError
   ▼
resultado en el mismo modal: confianza, warnings, líneas, descuadre
   │  action_apply_to_invoice()
   ▼
ir.actions.act_window → l10n.ve.physical.invoice.wizard (target=new, context default_*)
   │  action_create_and_post()   (ya existe; se extiende solo para tipo de documento)
   ▼
account.move posted (+ vat.book.line por el flujo existente)
```

Decisiones estructurales:

- **El wizard de digitalización no crea asientos.** Delega en el wizard de factura
  física, que ya valida RIF módulo 11, resuelve diario/cuenta/impuestos por compañía
  y postea (principio 1 de la constitución).
- **El paso de datos entre wizards es por contexto `default_*`**, no por un registro
  transitorio intermedio ni por campos espejo. El wizard de factura física sigue
  siendo la única entidad con los campos de la factura.
- **El cliente HTTP vive en su propio módulo** (`models/digitize_client.py`): sin
  imports de ORM, para que los tests lo mockeen sin cargar el registry.

### 1.1 Flujo de estados del wizard

| Estado  | Disparador                              | Botones visibles                                  |
|---------|-----------------------------------------|---------------------------------------------------|
| `draft` | apertura / reintento tras error         | Analizar, Cancelar                                |
| `done`  | respuesta 200 válida                    | Usar datos en Factura Física Rápida, Reanalizar, Cancelar |
| `error` | 4xx/5xx/timeout/JSON/sesión/tamaño      | Analizar (reintentar), Cancelar                   |

La imagen y el `filename` se conservan en todos los estados: el reintento no exige
volver a adjuntar (RF-12).

## 2. Archivos

### Crear

| Archivo | Contenido |
|---|---|
| `models/digitize_client.py` | `_get_session_id()`, `post_digitize(...)`, constantes de extensiones permitidas. Sin ORM. |
| `models/digitize_wizard.py` | `l10n.ve.digitize.wizard`: campos, `action_digitize`, `_parse_response`, `_map_extracted_to_invoice_defaults`, `action_apply_to_invoice`. |
| `models/digitize_line.py` | `l10n.ve.digitize.line` (TransientModel hijo): `wizard_id`, `description`, `quantity`, `unit_price`, `total` (solo lectura). |
| `views/digitize_wizard_views.xml` | Form del wizard + `ir.actions.act_window` (`target=new`) + acción "Reanalizar" si aplica. |
| `tests/test_digitize_wizard.py` | Tests T1–T5 (ver §5). |
| `tests/fixtures/digitize_response_200.json` | Respuesta canónica del contrato, usada por varios tests (fixture de contrato, sin red). |

### Modificar

| Archivo | Cambio |
|---|---|
| `data/ir_config_parameter_data.xml` | Nuevos parámetros (`noupdate="1"`): `l10n_ve_digitize.url` (vacío), `l10n_ve_digitize.timeout_seconds` (30), `l10n_ve_digitize.max_image_mb` (5). |
| `models/res_config_settings.py` | Campos `l10n_ve_digitize_url`, `l10n_ve_digitize_timeout_seconds` y `l10n_ve_digitize_max_image_mb` (`config_parameter`). |
| `views/res_config_settings_views.xml` | Bloque "Digitalización de facturas" en la app *ContaFis AI*. |
| `security/ir.model.access.csv` | ACL de `l10n.ve.digitize.wizard` y `l10n.ve.digitize.line` (patrón user + manager + contador). |
| `views/menu.xml` | Menú "Digitalizar Factura" bajo `menu_l10n_ve_compliance_taxes`, sequence 60. |
| `models/__init__.py` | Imports nuevos. |
| `views/physical_invoice_wizard_views.xml` | Campo `digitized_document_type` + `digitize_confidence` (invisibles cuando no aplican) y aviso de descuadre. |
| `models/physical_invoice_wizard.py` | Campos `digitized_document_type`, `digitize_confidence`; selección de `move_type` (nota de crédito) y narración de procedencia en `action_create_and_post`. Aditivo, sin cambiar el comportamiento actual cuando los campos están vacíos. |
| `__manifest__.py` | Registrar vista antes de `views/menu.xml`; versión `19.0.1.4.0`. |

## 3. Contrato técnico del método que llama a `/digitize`

```python
# models/digitize_client.py
DIGITIZE_ALLOWED_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp')


def _get_session_id():
    """Devuelve el sid de la sesión HTTP actual o '' si no hay contexto HTTP.

    Mismo blindaje que models/discuss_channel.py::_call_webhook:
    `request` puede no estar ligado (cron, shell, tests) y cualquier acceso
    a atributos lanzaría. Se captura y se devuelve ''.
    """


def post_digitize(url, session_id, payload, timeout):
    """POST JSON al endpoint /digitize.

    Sin ORM, sin logging de la imagen. Propaga requests.Timeout y
    requests.RequestException para que el modelo decida el mensaje i18n.
    Devuelve requests.Response (status_code + .json()).
    """
```

```python
# models/digitize_wizard.py
def action_digitize(self):
    """Orquesta: valida input → arma payload → llama al cliente → mapea respuesta.

    Efectos: escribe self.state ('done'|'error'), self.error_message,
    self.confidence, self.detected_document_type, los campos de vista previa,
    self.warnings_text y las líneas en digitize_line_ids.
    No crea account.move. No lanza excepción por fallos del servicio:
    los reporta en el estado del wizard (RF-12) salvo los errores de input
    (extensión/tamaño), que son ValidationError.
    """
```

Payload exacto construido (sin prefijo `data:`):

```python
payload = {
    'image_base64': self.image.decode() if isinstance(self.image, bytes) else self.image,
    'filename': self.filename,
    'document_type': self.document_type_hint,   # 'auto' por defecto
}
headers = {'Content-Type': 'application/json', 'X-Odoo-Session': session_id}
response = post_digitize(url, session_id, payload, timeout=self._get_timeout())
```

Tabla de mapeo de errores (mensajes accionables, `UserError`):

| Situación | Mensaje (español) |
|---|---|
| Sin URL configurada | "La digitalización no está configurada. Configure la URL en Ajustes → ContaFis AI." |
| Sin `sid` | "🔐 Sesión no detectada. Recargá Odoo e intentá de nuevo." |
| `requests.Timeout` | "⏱️ El servicio de digitalización tardó demasiado. Reintentá en unos minutos." |
| `requests.RequestException` | "❌ No se pudo conectar con el servicio de digitalización. Verifique la URL configurada." |
| `400` (y demás 4xx salvo 401/403) | "La imagen o el formato fue rechazado por el servicio. Verifique extensión y tamaño." |
| `401/403` | "🔐 Tu sesión de Odoo expiró o no es válida. Recargá Odoo e intentá de nuevo." |
| `503` | "🔄 El servicio de digitalización no está disponible ahora. Reintentá en unos minutos." |
| `>=500` | "🔧 Error del servidor de digitalización. Reintentá en unos minutos." |
| JSON inválido (`ValueError`) | "⚠️ El servicio devolvió una respuesta que no es JSON." |
| Faltan `document_type`/`confidence`/`extracted` | "⚠️ La respuesta del servicio está incompleta. Reintentá o cargue la factura a mano." |

Validación de la respuesta (tolerante al futuro, estricta con lo usado):

- Obligatorias: `document_type`, `confidence`, `extracted` (dict).
- `confidence` se acota a `[0.0, 1.0]`.
- `document_type` fuera del enum → se acepta como `factura_z` operativo y se agrega
  advertencia local `unknown_document_type`.
- Claves extra del JSON se ignoran (compatibilidad hacia adelante).
- `extracted.lines` ausente o `null` → lista vacía, sin error.

### Selección de `move_type` en el wizard destino (RF-13/RF-14)

| `digitized_document_type` | `type` | `move_type` |
|---|---|---|
| `factura_z` / vacío | purchase | `in_invoice` |
| `factura_z` / vacío | sale | `out_invoice` |
| `nota_credito` | purchase | `in_refund` |
| `nota_credito` | sale | `out_refund` |
| `nota_debito` | purchase / sale | `in_invoice` / `out_invoice` + `ref` = `debit_note_ref` |

La narración resultante antepone `[Digitalizado] tipo=<x> confianza=<y> advertencias=<n>` a
la narración/concepto existente.

## 4. Decisiones y alternativas descartadas

| Decisión | Alternativa descartada | Motivo |
|---|---|---|
| Wizard nuevo separado + prellenado del existente | Un solo wizard con botón "Digitalizar" dentro de Factura Física Rápida | Acopla la llamada IA al formulario manual, obliga a tocar la vista más usada (riesgo sobre 344 tests) y no permite reintentar sin perder lo tecleado |
| Prellenado vía `context={'default_*'}` | Crear un registro `l10n.ve.physical.invoice.wizard` y devolver `res_id` | Deja registros transitorios huérfanos y complica el estado al cancelar; con defaults el modal abre limpio y editable |
| Cliente HTTP en módulo propio sin ORM | Llamar `requests.post` dentro del método del modelo | Módulo propio = mock trivial, sin registry, y el modelo se queda con la orquestación y los mensajes i18n |
| Repetir el patrón `sid` + `try/except` de `discuss_channel.py` | Extraer helper compartido y refactorizar `discuss_channel.py` | Refactorizar el bot está fuera de alcance y arriesga specs 003-Bis/006; se replica el patrón (15 líneas) y se deja anotado para una spec de limpieza |
| Parámetro propio `l10n_ve_digitize.url` | Derivar la URL de `l10n_ve_chat.webhook_url` | El webhook del bot apunta a otro endpoint; acoplarlos rompe si el bot se desactiva. **Decidido con el usuario (spec §11.6)** |
| Validación de respuesta tolerante (solo claves usadas) | Validación estricta del esquema completo (pydantic-like) | El contrato pertenece a otro repo; una clave nueva no debe romper Odoo |
| Sin reintentos automáticos | `retry` con backoff | Un reintento silencioso puede duplicar costo y latencia; el contador reintenta a mano y no pierde la imagen |
| Líneas extraídas como `l10n.ve.digitize.line` (One2many readonly) | `Text` con la tabla formateada | Una lista real es legible y testeable; el `Text` se rompe en pantallas angostas |
| `move_type` de nota de crédito = refund | Rechazar notas de crédito en esta fase | El usuario pidió explícitamente cubrirlas; además `in_refund`/`out_refund` es el modelo correcto en Odoo |
| IGTF solo informativo | Campo nuevo de IGTF en wizard y `account.move` | Fuera de alcance de la spec; tocaría el Libro/planilla. **Decidido con el usuario (spec §11.1)** |

## 5. Estrategia de tests

Comando oficial (única fuente del conteo), igual que en las specs previas:

```
docker compose run --rm web odoo -d contea -u l10n_ve_compliance_manager \
  --test-enable --stop-after-init --workers 0 \
  --test-tags /l10n_ve_compliance_manager
```

Reglas:

- **Nunca red real**: `patch('requests.post')` (mismo estilo que
  `tests/test_discuss_bot.py`). Un test con URL real es un bug de test.
- Fixture `tests/fixtures/digitize_response_200.json` como respuesta canónica; los
  tests de error se construyen con `MagicMock(status_code=..., json=...)`.
- El fixture de sesión se simula con `MagicMock` + `PropertyMock` sobre
  `request.session.sid` (patrón de `test_discuss_bot.py`) o parcheando
  `digitize_client._get_session_id`.
- Clases nuevas en `tests/test_digitize_wizard.py`, tag
  `@tagged('post_install', '-at_install')`, heredando `TransactionCase` (y
  `TaxGroupMixin` de `tests/common.py` donde se cree el asiento).
- Contrato mínimo por tarea (nombres de test):

**T1 — `TestDigitizeClient` + `TestDigitizeWizardErrors`**
`test_post_digitize_sends_payload_and_session_header`,
`test_post_digitize_uses_configured_timeout`,
`test_post_digitize_returns_response_on_200`,
`test_post_digitize_propagates_timeout`,
`test_action_digitize_requires_url`,
`test_action_digitize_requires_session`,
`test_action_digitize_maps_401_to_session_error`,
`test_action_digitize_maps_503_to_unavailable`,
`test_action_digitize_maps_400_to_invalid_request`,
`test_action_digitize_maps_500_to_server_error`,
`test_action_digitize_handles_invalid_json`,
`test_action_digitize_rejects_oversized_image`,
`test_action_digitize_rejects_unsupported_extension`,
`test_action_digitize_does_not_log_image_or_session`,
`test_menu_and_action_exist`.

**T2 — `TestDigitizeMapping`**
`test_apply_returns_physical_wizard_action_with_defaults`,
`test_maps_general_rate_to_base_general`,
`test_maps_reduced_rate_to_base_reduced`,
`test_maps_zero_rate_to_base_not_taxed`,
`test_maps_usd_currency`,
`test_maps_dates_and_numbers`,
`test_maps_concept_from_lines`,
`test_matches_existing_partner_by_rif`,
`test_invalid_rif_is_warned_and_partner_left_empty`,
`test_missing_amounts_do_not_raise`.

**T3 — `TestDigitizeWarningsUi`**
`test_warnings_text_lists_every_code`,
`test_has_warnings_flag`,
`test_low_confidence_threshold_flag`,
`test_line_preview_rows_created`,
`test_total_mismatch_flag_true_when_difference`,
`test_warning_text_is_plain_text` (no contiene `<`/`>` sin escapar en el arch view).

**T4 — `TestDigitizeDocumentTypes`**
`test_credit_note_purchase_creates_refund`,
`test_credit_note_sale_creates_refund`,
`test_credit_note_uses_credit_note_ref`,
`test_debit_note_creates_invoice_with_ref_and_narration`,
`test_unknown_document_type_falls_back_to_invoice_with_warning`.

**T5 — `TestDigitizeEndToEnd`**
`test_digitized_flow_creates_posted_move`,
`test_digitized_move_uses_active_company`,
`test_digitized_move_narration_has_provenance`,
`test_digitized_move_generates_vat_book_line`,
`test_digitized_partner_not_reused_across_companies`,
`test_digitize_never_posts_without_confirmation`.

Cada tarea cierra con el conteo oficial de Odoo (`0 failed, 0 error(s) of N`) y
`N` estrictamente mayor al de la tarea anterior.

## 6. Seguridad

| Aspecto | Decisión |
|---|---|
| Transporte de la imagen | base64 en memoria durante la petición; el `Binary` del TransientModel se limpia con el autovacuum de transients. Nunca se copia al `account.move` ni a un adjunto del asiento. |
| Tamaño | validación local antes de codificar/enviar (`l10n_ve_digitize.max_image_mb`, 5 MB) + el backend mantiene su propio límite. |
| Formato | whitelist de extensiones; el MIME declarado por el navegador no se usa como prueba (se delega al backend). |
| Logs | `_logger.info` solo con `filename`, tamaño en MB, `status_code` y duración. Nunca base64, `sid`, ni el contenido de `extracted`. Un test verifica que el base64 no aparece en el log (`assertLogs`). |
| `sudo()` | Solo para leer `ir.config_parameter` (patrón existente: no es dato de negocio y el usuario final no debe necesitar ACL sobre el modelo de parámetros). Justificado en comentario. Cero `sudo()` para crear el asiento, el partner o las líneas: mandan las record rules del usuario. |
| Sesión | `X-Odoo-Session` se toma de `request.session.sid` en memoria; no se persiste ni se escribe en `ir.config_parameter`. |
| Datos del servicio | `warnings` y mensajes se muestran como texto plano; no se interpreta HTML del backend (XSS). |
| Record rules | El wizard no crea registros de negocio por su cuenta; el asiento hereda las reglas de `account.move` y la compañía activa. |
| Multi-cliente | `_map_extracted_to_invoice_defaults` no busca partners con `sudo()`; si el partner no es visible para el usuario de esa compañía, se propone crear uno nuevo (RF-17). |

## 7. Riesgos técnicos del plan

- **`Binary` + JSON**: en Odoo 19 el `Binary` llega como `bytes` en modo binario o
  como `str` base64 según el contexto; el cliente normaliza antes de enviar. Test
  explícito de ambos casos.
- **Campo `image` requerido en la vista**: recuerda la lección del wizard de
  importación (required en vista, no en modelo) para que "Cancelar" y los botones
  de error no bloqueen el diálogo.
- **Vista del wizard destino**: al pasar defaults por contexto hay que verificar que
  `currency_id` y las fechas lleguen tipadas (id de moneda, string ISO), no como
  texto del JSON.
- **Menu en overflow**: el menú "Digitalizar Factura" puede caer en
  `o_menu_sections_more` según cuántas secciones tenga la BD; la verificación
  visual debe scopear al modal (lección de la auditoría de Fase H).
- **Contenedor de larga duración**: tras `-u` puede requerir
  `docker compose restart web` para registrar modelos nuevos (lección de T9/spec 003).

## 8. Decisiones cerradas (2026-11-01)

Las seis preguntas de `spec.md` §11 quedaron resueltas antes de implementar. Ninguna
tarea necesita esperar:

| # | Pregunta | Decisión | Tarea |
|---|---|---|---|
| 1 | IGTF ¿se contabiliza? | Solo informativo, sin campo nuevo en `account.move` | T3 |
| 2 | `nota_debito` ¿crea asiento? | Sí, como factura normal + referencia del original | T4 |
| 3 | `iva_rate = 0` → ¿no gravada o no sujeta? | `base_not_taxed` | T2 |
| 4 | ¿Líneas por ítem o bases agregadas? | Bases agregadas; `lines[]` solo alimentan `concept` | T2/T5 |
| 5 | ¿`emission_type` viene del backend? | No; queda en el default del wizard | T2 (sin mapeo) |
| 6 | ¿URL dedicada o derivada del webhook? | Parámetro propio `l10n_ve_digitize.url` | T1 |
