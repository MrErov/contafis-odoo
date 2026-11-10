# Plan 007-B — Batch de 20 recibos en el wizard de digitalización

Spec base: `specs/007-digitalizacion/spec.md` (RF-01…RF-17).
Baseline verificado: `0 failed, 0 error(s) of 411 tests` (rama `19.0`, HEAD `58bf3e6`, working tree limpio).
Objetivo de tests: `0 failed, 0 error(s) of 426 tests` (411 + 15 nuevos).

Este documento es solo plan. No se escribe código acá.

---

## 1. Objetivo y alcance exacto

**Objetivo.** Permitir que el contador cargue hasta 20 fotos de recibos en el wizard
`l10n.ve.digitize.wizard`, las mande a analizar en una sola pulsación y vea, por cada
recibo, el resultado normalizado o el error concreto, **sin que un fallo aborte el lote**.

**Dentro del alcance**

- Modelo nuevo `l10n.ve.digitize.batch.line` (TransientModel hijo del wizard).
- Campo `line_ids` en `l10n.ve.digitize.wizard` y método `action_digitize_batch()`.
- Helpers puros de imagen (base64, extensión por nombre y magic bytes, tamaño) en el
  archivo del modelo nuevo.
- Vista: botón "Analizar lote", grupo de lote con `<list>` editable, ocultamiento del
  bloque single-image cuando hay líneas.
- 3 ACL para el modelo nuevo, imports en `models/__init__.py` y `tests/__init__.py`.
- 15 tests nuevos en `tests/test_digitize_batch.py`, con `requests.post` y la sesión
  mockeados (cero red real).

**Fuera del alcance (no-objetivos explícitos)**

- Mapear cada resultado a un asiento/`account.move` o al wizard de Factura Física Rápida.
  El batch **solo analiza y guarda JSON por línea**; el prellenado masivo es otra spec.
- Procesamiento asíncrono, cola, cron, concurrencia o reintentos automáticos.
- Persistencia histórica del lote (sigue siendo TransientModel).
- Cambios a `models/digitize_line.py`, `models/digitize_client.py`, `models/__init__.py`
  más allá del import, y a `action_digitize` (flujo single intacto).
- Nuevos `data` en `__manifest__.py` (la vista y el CSV ya están declarados).
- Cambios al contrato del backend `contafis-assistant`.

---

## 2. Modelo nuevo y campos

Archivo nuevo: `addons/l10n_ve_compliance_manager/models/digitize_batch_line.py`.

```python
BATCH_MAX_LINES = 20

class DigitizeBatchLine(models.TransientModel):
    _name = 'l10n.ve.digitize.batch.line'
    _description = 'Recibo del lote de digitalización'
    _order = 'id'
    _rec_name = 'filename'
```

| Campo           | Tipo                                | Atributos                                              | Motivo |
|-----------------|-------------------------------------|--------------------------------------------------------|--------|
| `wizard_id`     | `Many2one('l10n.ve.digitize.wizard')` | `required=True`, `ondelete='cascade'`                 | Pertenencia al lote; se borra con el transient padre. |
| `image`         | `Binary`                            | `attachment=True`                                      | Imagen del recibo; mismo patrón que el wizard single (no infla la fila). |
| `filename`      | `Char`                              | —                                                      | Nombre visible y `filename=` del widget imagen. |
| `status`        | `Selection`                         | `[('pending','Pendiente'),('done','Analizado'),('error','Error')]`, `default='pending'`, `readonly=True` | Estado por ítem, visible en la lista. |
| `error_message` | `Char`                              | `readonly=True`                                        | Timeout, JSON ilegible, 4xx/5xx, imagen inválida **por ítem**. |
| `result_json`   | `Text`                              | `readonly=True`                                        | Resultado normalizado (`document_type`, `confidence`, `extracted`, `warnings` fusionadas). |

Decisiones del modelo:

- `_order = 'id'` da orden estable de procesamiento (el mismo que ve el usuario).
- `_rec_name = 'filename'` evita `display_name` tipo `l10n.ve.digitize.batch.line,3`.
- `image` **no** es `required=True`: la ausencia de imagen es un error por ítem, no un
  bloqueo global (necesario para aislar el fallo y para el test 8).
- Sin `company_id`: es un transient de sesión, no un registro de negocio; la compañía
  se resuelve en el flujo de factura física, que está fuera de este alcance.

### 2.1 Helpers puros (mismo archivo, a nivel de módulo)

Sin ORM en las firmas, para poder testearlos y para no duplicar lógica dentro del modelo:

| Función | Contrato |
|---|---|
| `image_bytes(value) -> bytes` | Bytes crudos del binario; `b''` si no hay imagen o el base64 es inválido. |
| `image_base64(value) -> str` | Base64 plano **sin** prefijo `data:`; si el valor son bytes no-ASCII, los codifica. Réplica exacta de `DigitizeWizard._get_image_base64`. |
| `extension_from_filename(filename) -> str` | `'.jpg'` en minúsculas o `''` si no hay punto. |
| `extension_from_bytes(value) -> str` | `.jpg` (`ffd8ff`), `.png` (`89504e47…`), `.webp` (`RIFF….WEBP`), `''` si no reconoce. |
| `resolve_extension(filename, value) -> str` | Nombre si trae extensión; si no, magic bytes. |
| `image_size_mb(value) -> float` | `len(image_bytes(value)) / (1024*1024)`. |
| `payload_filename(filename, value) -> str` | `filename` no vacío, o `'invoice' + resolve_extension(...)`, o `'invoice.jpg'`. Nunca `False`. |
| `validate_image(value, filename, max_mb, allowed=DIGITIZE_ALLOWED_EXTENSIONS) -> None` | Lanza `ValueError` con el mensaje en español (imagen ausente / formato no soportado / tamaño excedido). |

Métodos del modelo que solo delegan en los helpers:

```python
def _build_payload(self, document_type, max_mb):
    validate_image(self.image, self.filename, max_mb)
    return {
        'image_base64': image_base64(self.image),
        'filename': payload_filename(self.filename, self.image),
        'document_type': document_type or 'auto',
    }
```

`DIGITIZE_ALLOWED_EXTENSIONS` se importa de `digitize_client` (no se redefine).
`validate_image` reutiliza los **textos** del wizard single para que el usuario vea el
mismo mensaje en ambos flujos ("Adjunte una imagen…", "Formato no soportado…",
"…supera el límite de X MB…").

---

## 3. Contrato de `action_digitize_batch`

Se añade en `models/digitize_wizard.py`, sin tocar `action_digitize` ni sus helpers.

### 3.1 Firmas nuevas

```python
line_ids = fields.One2many(
    'l10n.ve.digitize.batch.line', 'wizard_id', string='Recibos del lote'
)

def action_digitize_batch(self):        # orquesta el lote completo
def _process_batch_line(self, line, url, session_id, timeout, max_mb):  # procesa 1 ítem
def _batch_message_for_status(self, status):  # str|None, mensajes HTTP del lote
```

### 3.2 Pasos, en orden

1. `self.ensure_one()`.
2. **Validación de lote (aborta todo, antes de cualquier POST):**
   - `lines = self.line_ids` (orden `id`).
   - `if not lines: raise ValidationError(_("Agregue al menos un recibo al lote antes de analizar."))`
   - `if len(lines) > BATCH_MAX_LINES:` → `ValidationError`
     `"El lote admite como máximo 20 recibos (cargados: N)."`
3. **Configuración (aborta todo):**
   - `url = self._get_url()`; si vacía → `UserError` con el mismo texto accionable del
     flujo single ("La digitalización no está configurada. Configure la URL en Ajustes →
     ContaFis AI.").
   - `session_id = _get_session_id()` (import ya existente); si vacía → `UserError`
     "🔐 Sesión no detectada. Recargá Odoo e intentá de nuevo.".
   - Justificación: son precondiciones **del lote**, no del ítem; repetir 20 veces el
     mismo error de configuración no aporta y multiplica logs.
4. **Reset antes de reprocesar** (idempotencia del botón):
   `lines.write({'status': 'pending', 'error_message': False, 'result_json': False})`.
5. `timeout = self._get_timeout()`, `max_mb = self._get_max_image_mb()` (una sola lectura
   de parámetros para todo el lote).
6. **Loop aislado:**
   ```python
   for line in lines:
       try:
           self._process_batch_line(line, url, session_id, timeout, max_mb)
       except Exception:                      # última red de seguridad
           _logger.exception("Batch line %s failed unexpectedly", line.id)
           line.write({'status': 'error',
                       'error_message': _("Error inesperado al procesar el recibo.")})
   ```
7. `return self._reload_action()` (mismo modal, resultados visibles).

### 3.3 `_process_batch_line` (todo el error vive en la línea)

```
payload = line._build_payload(document_type_hint or 'auto', max_mb)
        ↳ ValueError (sin imagen / extensión / tamaño)
          → line.write(status='error', error_message=str(error)); return
tim = time.time(); post_digitize(url, session_id, payload, timeout=timeout)
        ↳ requests.Timeout            → error "⏱️ …tardó demasiado…"; return
        ↳ requests.RequestException   → error "❌ No se pudo conectar…"; return
mensaje = self._batch_message_for_status(response.status_code)
        ↳ 401/403  → "🔐 Tu sesión de Odoo expiró…"
        ↳ 503      → "🔄 El servicio … no está disponible ahora…"
        ↳ ≥500     → "🔧 Error del servidor de digitalización…"
        ↳ ≥400     → "La imagen o el formato fue rechazado…"
          → line.write(status='error', error_message=mensaje); return
data = response.json()      ↳ ValueError → error "⚠️ …no es JSON."; return
parsed = self._parse_response(data)   (helper EXISTENTE)
        ↳ None → error "⚠️ …respuesta … incompleta…"; return
merged = self._merge_warnings(parsed['warnings'],
                             self._build_local_warnings(extracted))   (EXISTENTES)
line.write(status='done', error_message=False,
           result_json=json.dumps({'document_type', 'confidence',
                                   'extracted', 'warnings': merged},
                                  ensure_ascii=False, default=str))
```

Detalles obligatorios:

- **Un solo tipo de cambio por ítem**: cada rama termina en `return`; nunca `raise`
  hacia el loop (salvo los `ValidationError`/`UserError` de §3.2).
- **Log por ítem** solo con metadatos: `filename`, MB, código HTTP, segundos. Nunca
  base64, `sid` ni el contenido extraído (RNF-04).
- `_batch_message_for_status` es **nueva** y la usa **solo** el batch. No se refactoriza
  `action_digitize` para compartirla (ver riesgo R-5).
- `result_json` incluye siempre las `warnings` **fusionadas** (servicio + locales), que
  es lo que el test 14 verifica.
- El batch **no** escribe `state`, `confidence`, `extracted_json` ni `digitize_line_ids`
  del wizard: el estado single queda intacto.

---

## 4. Cambios de vista (`views/digitize_wizard_views.xml`)

Solo se edita `view_l10n_ve_digitize_wizard_form`. Odoo 19: `<list>`, `invisible="…"`,
sin `attrs`/`states`.

### 4.1 Header

```xml
<header>
    <!-- single: se oculta en cuanto hay lote -->
    <button name="action_digitize" string="Analizar"
            type="object" class="btn-primary"
            invisible="state == 'done' or line_ids"/>
    <button name="action_digitize_batch" string="Analizar lote"
            type="object" class="btn-primary"
            invisible="not line_ids"/>
    <button name="action_apply_to_invoice" string="Usar datos en Factura Física Rápida"
            type="object" class="btn-success"
            invisible="state != 'done' or line_ids"/>
    <button name="action_digitize" string="Reanalizar"
            type="object" class="btn-secondary"
            invisible="state != 'done' or line_ids"/>
    <button string="Cancelar" class="btn-secondary" special="cancel"/>
</header>
```

### 4.2 Grupo single-image oculto cuando hay lote

```xml
<group string="Imagen de la factura" invisible="line_ids">
    <group>
        <field name="image" filename="filename" required="true"
               help="Formatos aceptados: JPG, JPEG, PNG y WEBP."/>
    </group>
    <group>
        <field name="filename" readonly="1" invisible="not filename"/>
    </group>
</group>
```

El `required="true"` es una restricción **de vista**: al ocultar el grupo desaparece la
validación de cliente. El campo Python no es `required`, así que un guardado con lote no
falla.

### 4.3 Grupo del lote (siempre visible)

```xml
<group string="Recibos del lote (máx. 20)">
    <field name="line_ids" nolabel="1" widget="section_and_note_one2many">
        <list>
            <field name="image" widget="image" filename="filename"
                   options="{'size': [0, 80]}"/>
            <field name="filename"/>
            <field name="status" widget="badge"
                   decoration-success="status == 'done'"
                   decoration-info="status == 'pending'"
                   decoration-danger="status == 'error'"/>
            <field name="error_message" optional="show"/>
            <field name="result_json" column_invisible="True"/>
        </list>
    </field>
</group>
```

Puntos finos:

- El grupo **no** se condiciona a `line_ids`: si estuviera invisible con la lista vacía,
  el usuario no podría añadir la primera fila (huevo y gallina en registro nuevo).
- `widget="image"` es seguro acá porque `image` es un `Binary` real y almacenado (no un
  related non-stored: anti-pattern #8 del AGENTS).
- `result_json` se oculta con `column_invisible="True"` (columna existe en el modelo,
  no se muestra). El detalle se puede inspeccionar vía ORM/JSON si hiciera falta.
- `status` como `badge` da lectura inmediata del lote (verde/azul/rojo).

---

## 5. ACL, imports y archivos

### 5.1 `security/ir.model.access.csv` (3 líneas al final)

```csv
access_l10n_ve_digitize_batch_line_user,l10n.ve.digitize.batch.line.user,model_l10n_ve_digitize_batch_line,base.group_user,1,1,1,1
access_l10n_ve_digitize_batch_line_manager,l10n.ve.digitize.batch.line.manager,model_l10n_ve_digitize_batch_line,account.group_account_manager,1,1,1,1
access_l10n_ve_digitize_batch_line_accountant,l10n.ve.digitize.batch.line.accountant,model_l10n_ve_digitize_batch_line,l10n_ve_compliance_accountant,1,1,1,1
```

Mismo patrón que `l10n.ve.digitize.line` (líneas 83-85 del CSV actual).

### 5.2 `models/__init__.py`

Insertar `digitize_batch_line,` en orden alfabético, antes de `digitize_client,`.

### 5.3 `tests/__init__.py`

Insertar `test_digitize_batch,` antes de `test_digitize_wizard,`.

### 5.4 `__manifest__.py`

**Sin cambios**: `views/digitize_wizard_views.xml` y `security/ir.model.access.csv` ya
están en `data`.

### 5.5 Resumen de archivos

| Archivo | Acción |
|---|---|
| `models/digitize_batch_line.py` | Crear (modelo + helpers puros + `BATCH_MAX_LINES`). |
| `models/digitize_wizard.py` | Modificar (campo `line_ids`, 3 métodos nuevos; resto intacto). |
| `models/__init__.py` | Modificar (1 import). |
| `views/digitize_wizard_views.xml` | Modificar (header + 2 grupos + lista). |
| `security/ir.model.access.csv` | Modificar (3 filas). |
| `tests/test_digitize_batch.py` | Crear (15 tests). |
| `tests/__init__.py` | Modificar (1 import). |

---

## 6. Los 15 tests (TDD: se escriben antes del código)

Archivo: `tests/test_digitize_batch.py`.

```python
from .test_digitize_wizard import (
    DIGITIZE_URL, VALID_RESPONSE, DigitizeTestMixin, _make_response,
)

@tagged('post_install', '-at_install')
class TestDigitizeBatch(DigitizeTestMixin, TransactionCase):
```

Reutiliza `DigitizeTestMixin` (`_patch_session`, `_create_wizard`), `_make_response`,
`DIGITIZE_URL` y `VALID_RESPONSE` del test module existente: cero red real y cero
duplicación de mocks. Helpers locales nuevos:

```python
def _batch_wizard(self, rows=2, **vals):
    """Wizard con N líneas; fila i -> filename 'recibo-0i.jpg' e imagen propia."""
def _lines(self, wizard): return wizard.line_ids.sorted('id')
```

| # | Test | Escenario | Aserciones clave |
|---|---|---|---|
| 1 | `test_batch_processes_three_lines` | 3 líneas válidas, `_make_response(200, VALID_RESPONSE)` | `mock_post.call_count == 3`; las 3 `status == 'done'`; `error_message` vacío; `json.loads(result_json)['document_type'] == 'factura_z'` y `confidence == 0.87`; `wizard.state` sigue `'draft'`. |
| 2 | `test_batch_rejects_more_than_twenty_lines` | 21 líneas | `assertRaises(ValidationError)`; `mock_post.assert_not_called()`; las líneas siguen `pending`. |
| 3 | `test_batch_rejects_empty_batch` | wizard sin líneas | `assertRaises(ValidationError)`; `mock_post.assert_not_called()`. |
| 4 | `test_batch_isolates_line_timeout` | `side_effect=[requests.Timeout('t'), _make_response(200, VALID_RESPONSE)]` | línea 1 `error` + `'tardó demasiado'`; línea 2 `done`; `call_count == 2`. |
| 5 | `test_batch_isolates_line_invalid_json` | `side_effect=[_make_response(200, None), _make_response(200, VALID_RESPONSE)]` | línea 1 `error` + `'no es JSON'`; línea 2 `done`; `call_count == 2`. |
| 6 | `test_batch_isolates_line_http_503` | `side_effect=[503, 200]` | línea 1 `error` + `'no está disponible'`; línea 2 `done`. |
| 7 | `test_batch_isolates_line_http_401` | `side_effect=[401, 200]` | línea 1 `error` + `'sesión de Odoo expiró'`; línea 2 `done`; **no** se lanza excepción de lote. |
| 8 | `test_batch_line_without_image_sets_error` | línea 1 `image=False`; línea 2 válida | línea 1 `error` + `'Adjunte una imagen'`; `call_count == 1`; línea 2 `done`. |
| 9 | `test_batch_line_invalid_extension_sets_error` | línea 1 `filename='recibo.gif'`; línea 2 válida | línea 1 `error` + `'Formato no soportado'`; `call_count == 1`; línea 2 `done`. |
| 10 | `test_batch_line_oversized_image_sets_error` | línea 1 con 6 MB (`b'x' * 6*1024*1024` en base64), `max_image_mb='5'` | línea 1 `error` + `'supera el límite'`; `call_count == 1`; línea 2 `done`. |
| 11 | `test_batch_requires_configured_url` | `l10n_ve_digitize.url=''`, 2 líneas | `assertRaises(UserError)`; `mock_post.assert_not_called()`; las 2 siguen `pending`. |
| 12 | `test_batch_requires_session` | `patch.object(digitize_client_module, 'request', None)` | `assertRaises(UserError)`; `mock_post.assert_not_called()`; mensaje `'Sesión no detectada'`. |
| 13 | `test_batch_builds_payload_per_line` | 2 líneas con imágenes y nombres distintos, `document_type_hint='nota_credito'` | `len(call_args_list) == 2`; `payloads[0]['filename'] == 'recibo-01.jpg'`, `payloads[1]['filename'] == 'recibo-02.PNG'`; `image_base64` corresponde a cada imagen (sin `data:`); `document_type == 'nota_credito'` en ambos; `headers['X-Odoo-Session'] == 'sid-batch'`. |
| 14 | `test_batch_merges_local_warnings_in_result_json` | 200 con `extracted={'supplier_name': ...}` y 1 warning del servicio (`missing_field`/`supplier_rif`) | `json.loads(result_json)['warnings']` contiene `('missing_field','supplier_rif')` **una vez** con el mensaje del servicio y `('missing_field','subtotal')` local; `status == 'done'`. |
| 15 | `test_batch_resets_previous_results_on_reprocess` | 1ª corrida OK (2 líneas `done`); 2ª corrida con `side_effect` que, al invocarse, verifica el estado previo y devuelve 200 | dentro del `side_effect`: todas las líneas `status == 'pending'` y `result_json` falsy; al final `done` y `result_json` poblado. |

Reglas de test:

- Mockear **siempre** `patch('requests.post', ...)`; jamás URL real (RNF-02).
- Sesión vía `self._patch_session('sid-batch')`; ausencia vía `patch.object(..., 'request', None)`.
- Ningún test toca `account.move` ni el wizard físico: el batch no postea.
- Los 15 viven en una sola clase para que `--test-tags …:TestDigitizeBatch` sea exacto.

---

## 7. Orden de implementación y verificación

### T0 — Lectura y baseline (5 min)

Leer `docs/constitution.md`, este plan y `tests/test_digitize_wizard.py`. No tocar nada.

**Hecho cuando:** baseline confirmado en 411 tests (si difiere, detenerse y reportar).

### T1 — RED: tests + esqueleto mínimo

1. Crear `tests/test_digitize_batch.py` con los 15 tests y registrarlo en `tests/__init__.py`.
2. Crear `models/digitize_batch_line.py` **solo con** campos + `BATCH_MAX_LINES` +
   helpers puros firmados (pueden devolver valores triviales) y `_build_payload`.
3. Añadir `line_ids`, `action_digitize_batch` que haga `raise NotImplementedError()`,
   `_process_batch_line` y `_batch_message_for_status` (stubs).
4. Import en `models/__init__.py`, 3 ACL, y la vista de §4 (necesaria para que la
   upgrade no falle).

```bash
docker compose run --rm web odoo -d contea -u l10n_ve_compliance_manager \
  --test-enable --stop-after-init --workers 0 \
  --test-tags /l10n_ve_compliance_manager:TestDigitizeBatch
```

**Hecho cuando:** el módulo actualiza sin error de vista/CSV y los 15 tests salen en
**rojo** (errores, no 0 tests). Este estado **no se commitea**.

### T2 — GREEN parcial: helpers de imagen + payload

Implementar `image_bytes`, `image_base64`, `extension_from_filename`,
`extension_from_bytes`, `resolve_extension`, `image_size_mb`, `payload_filename`,
`validate_image` y `_build_payload`.

**Hecho cuando:** los tests 8, 9, 10 y 13 pasan (validación por ítem y payload por línea).

### T3 — GREEN: `action_digitize_batch`

Validaciones de lote, URL/sesión con `UserError`, reset, loop aislado, parseo con los
helpers existentes, `result_json` y `_batch_message_for_status`.

```bash
docker compose run --rm web odoo -d contea -u l10n_ve_compliance_manager \
  --test-enable --stop-after-init --workers 0 \
  --test-tags /l10n_ve_compliance_manager:TestDigitizeBatch
```

**Hecho cuando:** `0 failed, 0 error(s) of 15 tests`.

### T4 — Suite completa (no regresión)

```bash
docker compose run --rm web odoo -d contea -u l10n_ve_compliance_manager \
  --test-enable --stop-after-init --workers 0 \
  --test-tags /l10n_ve_compliance_manager
```

**Hecho cuando:** `0 failed, 0 error(s) of 426 tests` (ni un número menor).

### T5 — Verificación visual y cierre

1. `docker compose restart web` y `-u l10n_ve_compliance_manager`.
2. Navegador en incógnito: menú **Impuestos → Digitalizar Factura**.
3. Añadir 2 filas al lote → confirmar que el grupo single-image desaparece y el botón
   single "Analizar" se oculta; "Analizar lote" aparece.
4. Sin URL configurada, pulsar "Analizar lote" → mensaje de configuración (no traza).
5. Con 2 filas y sin imagen en una → una fila en `error` con "Adjunte una imagen" y la
   otra procesada (si hay servicio) o en error propio.
6. Consola del navegador sin errores JS.
7. `git status` + `git diff --stat` → solo los 7 archivos esperados.
8. `pre-commit run --all-files` verde (ruff, check-xml, whitespace, mixed-line-ending).
9. Commit (lo hace el implementer): `feat(digitize): implement batch processing for up to 20 receipts`.
   **Sin push.**

---

## 8. Riesgos y decisiones

| # | Riesgo / decisión | Resolución en este plan |
|---|---|---|
| R-1 | `widget="section_and_note_one2many"` está pensado para `account.move.line` (con `display_type`). | El widget está registrado por `account` (dependencia del módulo) y tolera modelos sin `display_type`. **Plan B** si la lista no renderiza: cambiar solo a `<field name="line_ids" nolabel="1">` (one2many plano), sin tocar el modelo. Se valida en T5.3. |
| R-2 | `image` tiene `required="true"` en la vista y bloquearía el guardado del lote. | El grupo single se oculta con `invisible="line_ids"`; el web client no valida campos invisibles y el campo no es `required` a nivel Python. |
| R-3 | Fallo de una línea que aborta las 20. | Errores de ítem siempre se escriben en la línea (`status='error'`, `error_message`) y `return`; el loop además tiene una red `except Exception` con log. |
| R-4 | En cambio, URL y sesión abortan todo el lote (`UserError`). | Son precondiciones globales: 20 errores idénticos no aportan nada y multiplican logs/latencia. |
| R-5 | Duplicación de los 4 textos de error HTTP del flujo single. | Aceptada y acotada a `_batch_message_for_status`; **no** se refactoriza `action_digitize` para no arriesgar los 411 tests. Deuda anotada para una spec de limpieza. |
| R-6 | 20 llamadas secuenciales × timeout 30 s = hasta ~10 min de request web. | Fuera de alcance la cola/asincronía. Mitigación: máximo 20, timeout por parámetro, log por ítem, y esta limitación documentada para el usuario. Si el uso real crece, spec aparte de procesamiento asíncrono. |
| R-7 | El batch no crea facturas ni prellena el wizard físico. | Decisión de alcance: 20 asientos automáticos requieren control de duplicados, compañía y tipo de operación por ítem; eso es otra spec. Acá el batch solo **analiza** y guarda JSON por recibo. |
| R-8 | Imágenes 20 × 5 MB en transient + attachments. | Odoo limpia transients por cron; `attachment=True` evita filas gigantes. Sin acción extra. |
| R-9 | Tests importan helpers de `test_digitize_wizard.py`. | Aceptado (una sola fuente de mocks, evita duplicar el patrón de sesión). `conftest` no aplica en Odoo; la importación relativa es segura. |
| R-10 | Un `write` fallido dentro de `_process_batch_line` rompería el lote. | La red `except Exception` del loop intenta marcar la línea; si el ORM está caído, el lote aborta igual. Aceptado (no hay requisito de resiliencia a fallos de BD). |

---

## 9. Checklist de aceptación

- [ ] `models/digitize_batch_line.py` existe con los 6 campos de §2, `_order='id'`, `_rec_name='filename'` y los helpers puros.
- [ ] `l10n.ve.digitize.wizard.line_ids` existe (`One2many`, `ondelete='cascade'` en el hijo).
- [ ] `action_digitize_batch` valida 0 líneas → `ValidationError`, 21 → `ValidationError`, URL vacía → `UserError`, sin `sid` → `UserError`, todo **antes** de cualquier POST.
- [ ] El reset (`pending`/`False`/`False`) ocurre antes del loop y es verificable en la 2ª corrida.
- [ ] Cada `status='error'` guarda `error_message`; cada `status='done'` guarda `result_json` con `document_type`, `confidence`, `extracted` y `warnings` fusionadas.
- [ ] `action_digitize`, `_parse_response`, `_merge_warnings` y `_build_local_warnings` **sin cambios** (`git diff -U0` lo confirma).
- [ ] `models/digitize_line.py`, `digitize_client.py` y `__manifest__.py` sin cambios.
- [ ] 3 ACL nuevas en `ir.model.access.csv` con `1,1,1,1` y los 3 grupos indicados.
- [ ] Vista: `<list>` (no `<tree>`), sin `attrs`/`states`, botón single oculto con `line_ids`, grupo single oculto con `line_ids`, lista del lote con `image`/`filename`/`status`/`error_message`/`result_json` oculto.
- [ ] `tests/test_digitize_batch.py` con **exactamente** 15 tests y `@tagged('post_install', '-at_install')`.
- [ ] `--test-tags …:TestDigitizeBatch` → `0 failed, 0 error(s) of 15 tests`.
- [ ] Suite completa → `0 failed, 0 error(s) of 426 tests`.
- [ ] Verificación visual en navegador con toggle single↔lote; consola sin errores JS.
- [ ] `git status` solo con los 7 archivos esperados; `pre-commit` verde.
- [ ] Commit `feat(digitize): implement batch processing for up to 20 receipts`; **sin push**.
