# Plan 007-D — "Usar datos" por fila del lote

Spec: `specs/007-digitalizacion/007-d-spec.md` (RF-D-01…RF-D-11).
Baseline: `0 failed, 0 error(s) of 433 tests` (post 007-C, `TestDigitizeBatch` 22/22).
Objetivo: `0 failed, 0 error(s) of 437 tests` (433 + 4).

Solo plan. No se escribe código acá.

---

## 1. Archivos a tocar

| Archivo | Acción | Detalle |
|---|---|---|
| `addons/l10n_ve_compliance_manager/tests/test_digitize_batch.py` | Modificar | +4 tests al final de `TestDigitizeBatch`; `_load_fixture` en el import. |
| `addons/l10n_ve_compliance_manager/models/digitize_wizard.py` | Modificar | +`_build_apply_to_invoice_action`; `action_apply_to_invoice` delega; 2 kwargs opcionales en `_map_extracted_to_invoice_defaults`. |
| `addons/l10n_ve_compliance_manager/models/digitize_batch_line.py` | Modificar | +`import json`, +`UserError`, +`action_apply_line_to_invoice`. |
| `addons/l10n_ve_compliance_manager/views/digitize_wizard_views.xml` | Modificar | +1 `<button>` en la `<list>` de `line_ids`. |
| `docs/guia-usuario/14-digitalizacion-facturas.md` + PDF | **Fuera del implementer** | Lo hace el agente principal (sección *Qué hacer con los resultados*, línea 152, FAQ línea 196; `npm run build:guide`). |

Sin cambios: `security/ir.model.access.csv`, `models/__init__.py`, `tests/__init__.py`,
`__manifest__.py` (versión sigue `19.0.1.4.0`), `static/src/**` (runner OWL intacto).

---

## 2. Cambios de modelo

### 2.1 `models/digitize_wizard.py`

**a) `_map_extracted_to_invoice_defaults` — dos parámetros opcionales**

Firma nueva:

```python
def _map_extracted_to_invoice_defaults(
    self, extracted, document_type=None, confidence=None
):
```

Único bloque que cambia (hoy líneas 639-643):

```python
# antes
doc_type = (self.detected_document_type or '').strip()
if doc_type in ('factura_z', 'nota_credito', 'nota_debito'):
    defaults['default_digitized_document_type'] = doc_type
    defaults['default_digitize_confidence'] = float(self.confidence or 0.0)

# después
raw_doc_type = (
    document_type if document_type is not None else self.detected_document_type
)
doc_type = str(raw_doc_type or '').strip()
if doc_type in ('factura_z', 'nota_credito', 'nota_debito'):
    defaults['default_digitized_document_type'] = doc_type
    raw_confidence = confidence if confidence is not None else self.confidence
    defaults['default_digitize_confidence'] = float(raw_confidence or 0.0)
    # ... resto igual (credit_note_ref / debit_note_ref)
```

Todo lo demás del método queda **idéntico** (RF-10, RF-11, RF-17). Las 11 llamadas
existentes en tests siguen funcionando sin cambios.

**b) Helper compartido**

```python
def _build_apply_to_invoice_action(
    self, extracted, document_type=None, confidence=None
):
    """Contrato único de prellenado del wizard de Factura Física Rápida.

    Compartido por el flujo de imagen única y por el lote (spec 007-D).
    No valida: cada flujo valida su propia entrada.
    """
    defaults = self._map_extracted_to_invoice_defaults(
        extracted, document_type=document_type, confidence=confidence
    )
    return {
        'type': 'ir.actions.act_window',
        'name': _('Factura Física Rápida'),   # conservar el literal actual del archivo
        'res_model': 'l10n.ve.physical.invoice.wizard',
        'view_mode': 'form',
        'target': 'new',
        'context': defaults,
    }
```

**c) `action_apply_to_invoice` — solo delega**

```python
def action_apply_to_invoice(self):
    """Open the physical invoice wizard pre-filled with the extracted data."""
    self.ensure_one()
    if self.state != 'done':
        raise UserError(_("Analice la imagen antes de usar los datos."))

    try:
        extracted = json.loads(self.extracted_json or '{}')
    except (TypeError, ValueError):
        extracted = {}

    return self._build_apply_to_invoice_action(extracted)
```

Comportamiento byte-a-byte igual al actual (la tolerancia a JSON inválido **se
mantiene**, D-2). El test `test_apply_returns_physical_wizard_action_with_defaults`
debe seguir verde sin tocarlo.

### 2.2 `models/digitize_batch_line.py`

Imports: `import json` y `from odoo.exceptions import UserError` (hoy solo
`base64`, `_`, `fields`, `models`).

```python
def action_apply_line_to_invoice(self):
    """Abre Factura Física Rápida con los datos de esta fila (spec 007-D)."""
    self.ensure_one()

    if self.status == 'pending':
        raise UserError(_("Analice el recibo antes de usar los datos."))
    if self.status != 'done':
        raise UserError(
            _(
                "El recibo tiene un error de análisis. "
                "Corríjalo o reanalícelo antes de usar los datos."
            )
        )

    try:
        data = json.loads(self.result_json or '')
    except (TypeError, ValueError):
        data = None

    extracted = data.get('extracted') if isinstance(data, dict) else None
    if not isinstance(extracted, dict) or not extracted:
        raise UserError(
            _("El recibo no tiene datos analizados. Vuelva a analizarlo.")
        )

    return self.wizard_id._build_apply_to_invoice_action(
        extracted,
        document_type=data.get('document_type'),
        confidence=data.get('confidence'),
    )
```

Notas:

- Orden de validación: estado → JSON → `extracted`. Un `pending` con `result_json`
  basura da el mensaje de estado, no el de datos.
- `json.loads('')` lanza `ValueError` → cubierto por el `except`.
- Solo lectura: no hay `write`, `create`, `unlink` ni `sudo`.
- `self.wizard_id` es `required=True`; no se agrega guard extra (ver R-6).

---

## 3. Cambio de vista (`views/digitize_wizard_views.xml`)

Dentro de la `<list>` de `line_ids` (hoy líneas 42-52), agregar la columna del botón
después de `status` y antes de `error_message`:

```xml
<list>
    <field name="image" widget="image" filename="filename"
           options="{'size': [0, 80]}"/>
    <field name="filename"/>
    <field name="status" widget="badge"
           decoration-success="status == 'done'"
           decoration-info="status == 'pending'"
           decoration-danger="status == 'error'"/>
    <button name="action_apply_line_to_invoice" string="Usar datos"
            type="object" class="btn-link"
            invisible="status != 'done'"/>
    <field name="error_message" optional="show"/>
    <field name="result_json" column_invisible="True"/>
</list>
```

- Odoo 19: `<list>` (no `<tree>`), `invisible="status != 'done'"`, sin `attrs`/`states`.
- `class="btn-link"` para que no compita visualmente con el badge de estado.
- No se toca el `<header>` ni el botón single (`invisible="state != 'done' or line_ids"`).
- `status` ya está declarado en la lista: la expresión `invisible` resuelve sin campos
  extra.

---

## 4. Los 4 tests (TDD: se escriben antes del código)

Archivo `tests/test_digitize_batch.py`. Import a ampliar:

```python
from .test_digitize_wizard import (
    DIGITIZE_URL,
    VALID_RESPONSE,
    DigitizeTestMixin,
    _load_fixture,
    _make_response,
)
```

Nuevo helper local (junto a `_run_batch`, reutiliza los existentes):

```python
def _analyzed_batch(self, rows=1, payload=None):
    """Lote ya analizado con la respuesta realista del fixture (cero red)."""
    wizard = self._batch_wizard(rows=rows)
    self._run_batch(
        wizard, return_value=_make_response(200, payload or _load_fixture())
    )
    return wizard
```

| # | Test | Escenario | Aserciones |
|---|---|---|---|
| 23 | `test_batch_line_apply_to_invoice_done` | 1 fila analizada con `_load_fixture()` | `action['type'|'name'|'res_model'|'target'|'view_mode']` idénticos al single; `context['default_type'] == 'purchase'`, `default_partner_vat == 'J-31527189-4'`, `default_invoice_number == 'FAC-000123'`, `default_control_number == '00-000456'`, `default_base_general == 1000.0`, `default_physical_total == 1160.0`; **si D-4 se aprueba**: `default_digitized_document_type == 'factura_z'` y `default_digitize_confidence == 0.87`; la fila queda `done` y `wizard.state == 'draft'`. |
| 24 | `test_batch_line_apply_to_invoice_pending` | lote recién creado, sin analizar | `assertRaises(UserError)`; mensaje contiene `'Analice el recibo'`; `line.status == 'pending'` y `result_json` falsy (no se escribe nada). |
| 25 | `test_batch_line_apply_to_invoice_error` | lote con `_make_response(503)` | línea `error`; `assertRaises(UserError)`; mensaje contiene `'error de análisis'`. |
| 26 | `test_batch_line_apply_to_invoice_without_result_json` | 1 fila forzada a `done` con `result_json` en 5 variantes vía `subTest`: `False`, `'no-json'`, `'{}'`, `'{"extracted": {}}'`, `'{"extracted": null}'` | `assertRaises(UserError)` en las 5; mensaje contiene `'no tiene datos analizados'`; ningún caso lanza `KeyError`/`JSONDecodeError`. |

Reglas:

- Todo dentro de `TestDigitizeBatch` (usa `_batch_wizard`, `_run_batch`, `_lines`,
  `_patch_session`). Cero red: `_run_batch` ya mockea `requests.post`.
- No se toca `account.move` ni el wizard físico: solo se inspecciona el dict devuelto.
- Para el caso 26: `wizard = self._batch_wizard(rows=1)`; `line = self._lines(wizard)[0]`;
  `line.write({'status': 'done', 'result_json': value})` dentro de cada `subTest`.
- Nombres exactos = los de la tabla (el reviewer verifica RF por RF contra ellos).

---

## 5. Orden TDD y verificación

### T1 — RED: tests primero

Escribir los 4 tests + helper + import. No tocar modelos ni vista todavía.

```bash
docker compose run --rm web odoo -d contea -u l10n_ve_compliance_manager \
  --test-enable --stop-after-init --workers 0 \
  --test-tags /l10n_ve_compliance_manager:TestDigitizeBatch
```

**Hecho cuando:** el módulo actualiza sin error y los 4 tests nuevos fallan por
`AttributeError` (`action_apply_line_to_invoice` no existe), no por error de import ni
de sintaxis. Este estado **no se commitea**.

### T2 — GREEN del helper compartido (sin romper el single)

Implementar §2.1 (kwargs opcionales + `_build_apply_to_invoice_action` + delegación en
`action_apply_to_invoice`).

**Hecho cuando:** `--test-tags …:TestDigitizeBatch` sigue con los 22 anteriores verdes
y los 4 nuevos siguen rojos, y no hay regresión en
`TestDigitizeMapping::test_apply_returns_physical_wizard_action_with_defaults`.

### T3 — GREEN de la fila

Implementar §2.2 (`import json`, `UserError`, `action_apply_line_to_invoice`).

**Hecho cuando:** `0 failed, 0 error(s) of 26 tests` en `TestDigitizeBatch`.

### T4 — Botón en la vista + verificación visual

Aplicar §3, hacer `docker compose restart web` y `-u l10n_ve_compliance_manager`.

**Hecho cuando:** en el navegador (incógnito, Ctrl+Shift+R) una fila *Analizado*
muestra **Usar datos**, las filas *Pendiente*/*Error* no lo muestran, y al pulsarlo se
abre el diálogo *Factura Física Rápida* prellenado. Consola sin errores JS. Si el botón
no renderiza con `section_and_note_one2many`, aplicar el plan B de R-2.

### T5 — Suite completa, lint y commit

```bash
docker compose run --rm web odoo -d contea -u l10n_ve_compliance_manager \
  --test-enable --stop-after-init --workers 0 \
  --test-tags /l10n_ve_compliance_manager

pre-commit run --all-files
git status
git diff --stat
```

**Hecho cuando:** `0 failed, 0 error(s) of 437 tests` (ni un número menor),
`pre-commit` verde, `git status` con solo los 4 archivos esperados y commit:
`feat(digitize): add per-line apply to invoice in batch wizard` (sin push).

---

## 6. Riesgos y mitigaciones

| # | Riesgo | Mitigación |
|---|---|---|
| R-1 | **Forma de `result_json`**: contrato del backend puede traer `extracted` ausente, `null`, lista o vacío (ya pasó con `currency="Bs"` en 007-B). | Validación estricta (`isinstance(dict)` + no vacío) → `UserError`; test 26 con 5 variantes. Nunca se indexa a ciegas. |
| R-2 | **Botón en x2many editable**: `widget="section_and_note_one2many"` está pensado para `account.move.line`; un `<button>` podría no renderizar o no disparar en filas no persistidas. | Las filas del lote se persisten antes de analizar (el runner hace `record.save()`/`load()`), así que al mostrarse `done` tienen `id`. **Plan B** si falla la verificación visual: cambiar solo `widget="section_and_note_one2many"` por `<field name="line_ids" nolabel="1">` (one2many plano), sin tocar modelo ni tests. |
| R-3 | **Registros transitorios**: el cron de vacuum puede borrar el wizard y sus líneas mientras el diálogo está abierto (ya ocurrió con los wizards 7024/7025 de la guía). | Fuera de control del módulo. Si la fila desaparece, el diálogo falla al recargar; se documenta como limitación, sin código. |
| R-4 | **Diálogo anidado**: `target='new'` desde un modal abierto por un botón de una fila. | Odoo apila diálogos (el flujo single ya lanza `target='new'` desde un modal). Se valida en T4; si el cliente lo rechazara, no se cambia el contrato (CA-D-1 exige el mismo `ir.actions.act_window`). |
| R-5 | **Procedencia (`document_type`/`confidence`)**: el lote **no** escribe `state`, `detected_document_type` ni `confidence` del wizard (decisión 007-B). Sin propagación, una `nota_credito` del lote se crearía como factura normal (RF-13/14). | D-4: kwargs opcionales `document_type`/`confidence` en el helper y en el mapeo; `None` = comportamiento actual. Cero cambio para el single. **Pendiente de confirmación del orquestador.** |
| R-6 | `self.wizard_id` vacío (dato inconsistente). | `wizard_id` es `required=True` y `ondelete='cascade'`. Se acepta sin guard: preferible el error visible a inventar contexto. |
| R-7 | **Doble factura** por pulsar dos veces. | Mismo comportamiento que el modo individual: cada pulsación abre un wizard nuevo; la creación sigue requiriendo confirmación humana (RF-15). |
| R-8 | **Regresión en 433 tests** al tocar `_map_extracted_to_invoice_defaults` (11 tests lo usan). | Cambio aditivo con `None` por defecto; T2 corre el targeted antes y después. Si algún test cambia, revertir y reportar (no "arreglar" el test). |
| R-9 | Nombre/`string` del botón distinto del que espera la guía. | El plan fija **"Usar datos"**; el agente principal usa ese literal en `14-digitalizacion-facturas.md`. |

---

## 7. Checklist de aceptación

- [ ] `action_apply_line_to_invoice` existe en `l10n.ve.digitize.batch.line` y no escribe en la fila.
- [ ] Los 3 estados y los 5 casos de `result_json` inválido lanzan `UserError` en español.
- [ ] `_build_apply_to_invoice_action` es el **único** constructor del `ir.actions.act_window`; `action_apply_to_invoice` delega.
- [ ] Cero claves `default_*` duplicadas entre wizard y línea (`git diff` lo muestra).
- [ ] La vista usa `<list>`, `invisible="status != 'done'"`, sin `attrs`/`states`.
- [ ] `TestDigitizeBatch` = 26 tests verdes; suite = 437, 0 failed.
- [ ] `TestDigitizeMapping::test_apply_returns_physical_wizard_action_with_defaults` verde **sin haberlo editado**.
- [ ] Verificación visual del botón y del diálogo anidado, consola limpia.
- [ ] `pre-commit` verde, `git status` con 4 archivos, commit en inglés sin push.
- [ ] `docs/memory.md`, la guía y el PDF los actualiza el agente principal (no el implementer).
