# Spec 007-D — "Usar datos" por fila del lote

Spec base: `specs/007-digitalizacion/spec.md` (RF-09, RF-10, RF-13, RF-14).
Antecedentes: `batch_plan.md` (007-B) y `docs/memory.md` § *Spec 007-C*.
Baseline: `0 failed, 0 error(s) of 433 tests` (2026-11-10).
Objetivo: `0 failed, 0 error(s) of 437 tests` (433 + 4).

Estado: propuesta, pendiente de aprobación del orquestador.

---

## 1. Problema

El lote (`l10n.ve.digitize.batch.line`) ya analiza hasta 20 recibos y guarda el
resultado completo en `result_json` (`document_type`, `confidence`, `extracted`,
`warnings`). Pero el contador **no puede usar ese resultado**: el botón *Usar datos
en Factura Física Rápida* (`action_apply_to_invoice`) vive en el header del wizard y
está oculto cuando hay lote (`invisible="state != 'done' or line_ids"`), y
`self.state` del wizard **nunca** pasa a `done` en el flujo de lote.

Resultado hoy: el contador ve que un recibo está *Analizado*, abre el detalle, lee el
JSON y **teclea todo a mano** en Factura Física Rápida. Exactamente el trabajo que la
digitalización debía eliminar.

La guía de usuario lo documenta como limitación (`14-digitalizacion-facturas.md`,
línea 152: *"El lote no crea facturas ni tiene un botón 'Usar datos' por fila"*).

Objetivo: que cada fila analizada tenga su propio **Usar datos** y abra el wizard de
Factura Física Rápida prellenado con **el mismo mapeo** del modo individual.

---

## 2. Alcance

### Dentro del alcance

- Método `action_apply_line_to_invoice()` en `l10n.ve.digitize.batch.line`.
- Helper compartido `_build_apply_to_invoice_action(self, extracted, document_type=None,
  confidence=None)` en `l10n.ve.digitize.wizard`; `action_apply_to_invoice()` pasa a
  delegar en él (cero duplicación del mapeo).
- Botón **Usar datos** en la lista del lote, visible solo con `status == 'done'`.
- 4 tests nuevos en `tests/test_digitize_batch.py` (TDD, sin red).
- Actualización de `docs/guia-usuario/14-digitalizacion-facturas.md` y rebuild del PDF
  (lo ejecuta el agente principal, no el implementer).

### Fuera del alcance (no-objetivos)

- Crear, postear o duplicar `account.move` desde la fila: solo se **abre el wizard**,
  igual que el flujo individual (RF-15).
- Prellenado masivo (20 facturas de un clic) ni cola/asincronía.
- Nuevos campos, modelos, ACL, permisos, `__manifest__.py` ni bump de versión
  (007-B y 007-C tampoco lo hicieron: sigue `19.0.1.4.0`).
- Cambios a `action_digitize`, `action_digitize_line`, `_process_batch_line`,
  `_parse_response`, `_merge_warnings`, `_build_local_warnings` ni al widget OWL
  `l10n_ve_batch_runner`.
- Cambios al backend `contafis-assistant` ni a su contrato JSON.
- Deduplicación de facturas repetidas al pulsar dos veces el botón (mismo
  comportamiento que el modo individual).

---

## 3. Flujo de usuario

1. El contador carga N recibos, pulsa **[Analizar lote]** (runner OWL de 007-C) y
   espera a que las filas queden *Analizado* o *Error*.
2. En una fila *Analizado* aparece el botón **Usar datos**.
3. Al pulsarlo se abre el wizard *Factura Física Rápida*, prellenado y editable, con
   los datos de **esa** fila (no del wizard, que sigue en `draft`).
4. El contador corrige y crea la factura con el flujo existente.
5. Las filas *Pendiente* y *Error* no muestran el botón; si se invoca el método por
   RPC, responde `UserError` en español y no abre nada.

---

## 4. Requisitos funcionales (EARS)

- **RF-D-01**: CUANDO el contador pulsa **Usar datos** en una fila con
  `status == 'done'` y `result_json` válido con `extracted` no vacío, EL SISTEMA
  devuelve una acción `ir.actions.act_window` sobre `l10n.ve.physical.invoice.wizard`
  con `target='new'`, `view_mode='form'`, `name='Factura Física Rápida'` y
  `context` con las claves `default_*` del mapeo (RF-10).
- **RF-D-02**: SI `status == 'pending'`, ENTONCES EL SISTEMA lanza `UserError`
  ("Analice el recibo antes de usar los datos."), no escribe en la fila ni en el
  wizard y no devuelve acción.
- **RF-D-03**: SI `status == 'error'`, ENTONCES EL SISTEMA lanza `UserError`
  ("El recibo tiene un error de análisis. Corríjalo o reanalícelo antes de usar los
  datos.") y no devuelve acción.
- **RF-D-04**: SI `status == 'done'` pero `result_json` está vacío, no es JSON válido,
  no es un objeto, o su `extracted` falta, no es dict o está vacío, ENTONCES EL
  SISTEMA lanza `UserError` ("El recibo no tiene datos analizados. Vuelva a
  analizarlo.") y no abre el wizard.
- **RF-D-05**: EL SISTEMA construye el contexto con **un único** mapeo compartido:
  `action_apply_to_invoice()` y `action_apply_line_to_invoice()` llaman ambos a
  `_build_apply_to_invoice_action(...)`, que a su vez delega en
  `_map_extracted_to_invoice_defaults(...)`. Prohibido duplicar claves `default_*`.
- **RF-D-06**: CUANDO la fila viene del lote, EL SISTEMA propaga el `document_type` y
  la `confidence` de `result_json` a `default_digitized_document_type` y
  `default_digitize_confidence` (RF-13/RF-14), sin depender de
  `wizard.detected_document_type`/`wizard.confidence`, que en lote quedan vacíos.
- **RF-D-07**: EL SISTEMA no crea ni modifica `account.move`, no postea, no altera
  `status`, `result_json` ni `error_message` de la fila: el método es de solo lectura
  más la acción devuelta (RF-15).
- **RF-D-08**: EL SISTEMA muestra el botón **Usar datos** en la lista del lote
  únicamente con `invisible="status != 'done'"`; usa `<list>` (no `<tree>`) y no usa
  `attrs` ni `states`.
- **RF-D-09**: SI el partner, la moneda o el RIF no se resuelven, ENTONCES EL SISTEMA
  deja esos `default_*` vacíos como ya hace el flujo individual (RF-11): no inventa
  valores.
- **RF-D-10**: EL SISTEMA resuelve moneda y partner con la compañía activa del usuario,
  reutilizando el mapeo existente; no se agrega lógica multi-compañía nueva.
- **RF-D-11**: EL SISTEMA no ejecuta HTTP al aplicar una fila: `result_json` ya está
  persistido. Ningún test abre conexiones.

---

## 5. Contrato del método

```python
# models/digitize_batch_line.py
def action_apply_line_to_invoice(self):
    """Abre Factura Física Rápida con los datos de esta fila analizada."""
```

Devuelve, o lanza `UserError`:

```python
{
    'type': 'ir.actions.act_window',
    'name': 'Factura Física Rápida',
    'res_model': 'l10n.ve.physical.invoice.wizard',
    'view_mode': 'form',
    'target': 'new',
    'context': {
        'default_type': 'purchase',              # self.wizard_id.type
        'default_partner_vat': 'J-31527189-4',
        'default_invoice_number': 'FAC-000123',
        'default_control_number': '00-000456',
        'default_base_general': 1000.0,
        'default_physical_total': 1160.0,
        'default_digitized_document_type': 'factura_z',
        'default_digitize_confidence': 0.87,
        # ... resto del mapeo RF-10
    },
}
```

```python
# models/digitize_wizard.py
def _build_apply_to_invoice_action(
    self, extracted, document_type=None, confidence=None
):
    """Contrato único de prellenado; usado por single y por lote."""
```

`document_type`/`confidence` son **opcionales**: `None` significa "usar los campos del
wizard" (comportamiento actual del modo individual, sin cambios). El lote pasa los
valores de `result_json`. Ver riesgo R-5 y decisión D-4 del plan.

---

## 6. Criterios de aceptación

- **CA-D-1**: desde una fila *Analizado*, **Usar datos** abre Factura Física Rápida
  con RIF, razón social, número, control, fechas, moneda, base y total precargados y
  editables.
- **CA-D-2**: filas *Pendiente* y *Error* no muestran el botón; invocadas por RPC
  lanzan `UserError` con mensaje distinto y en español.
- **CA-D-3**: una fila *Analizado* con `result_json` corrupto o sin `extracted`
  lanza `UserError`, nunca `KeyError`/`TypeError`/`JSONDecodeError`.
- **CA-D-4**: `TestDigitizeBatch` → `0 failed, 0 error(s) of 26 tests`.
- **CA-D-5**: suite completa → `0 failed, 0 error(s) of 437 tests`; ningún test
  existente cambia de resultado (en particular
  `test_apply_returns_physical_wizard_action_with_defaults`).
- **CA-D-6**: `pre-commit run --all-files` verde y `git status` con solo los 4
  archivos de código/test esperados.
- **CA-D-7**: verificación visual: botón visible solo en filas *Analizado*, abre el
  diálogo anidado y la consola no muestra errores JS.

---

## 7. Decisiones cerradas

1. **D-1 — Reutilizar, no copiar**: un helper en el wizard; la línea solo valida y
   delega. Cumple el principio 1 de la constitución (no reimplementar).
2. **D-2 — La validación vive en la línea**: el helper del wizard no valida; el modo
   individual conserva su tolerancia actual (`extracted_json` inválido → `{}`) para no
   romper los 433 tests.
3. **D-3 — Sin cambios de modelo**: `result_json` ya contiene todo lo necesario; no se
   agregan campos derivados (`document_type`/`confidence` como columnas) en 007-D.
4. **D-4 — Procedencia explícita**: `document_type`/`confidence` se pasan como
   argumentos opcionales. Sin esto, una `nota_credito` analizada en lote se crearía
   como factura normal (regresión de RF-13/RF-14). *Requiere confirmación del
   orquestador* (única desviación respecto de la firma `(self, extracted)`).
5. **D-5 — Sin permiso nuevo**: el botón usa las ACL ya existentes de
   `l10n.ve.digitize.batch.line` (1,1,1,1 en 3 grupos).
6. **D-6 — Mensajes en español, código en inglés** (constitución, principio 6).
