# Spec 007 - Wizard de Digitalización de facturas venezolanas

Estado: propuesta (pendiente de aprobación). Baseline de tests: `0 failed, 0 error(s) of 344 tests`.

## 1. Problema

Hoy el contador carga una factura de compra o venta **a mano** en el wizard
"Factura Física Rápida" (`l10n.ve.physical.invoice.wizard`): transcribe RIF, razón
social, número de factura, número de control, fechas, bases por alícuota y total.
Cada factura son entre 8 y 12 campos tecleados desde una foto o un PDF impreso;
el error de transcripción (un dígito del RIF, un número de control) contamina el
Libro de Compras/Ventas y la planilla IVA.

El repo hermano `contafis-assistant` ya expone `POST /digitize`, que recibe una
imagen de factura venezolana y devuelve los campos extraídos más niveles de
confianza y advertencias. El backend **no se modifica en esta spec**: es un
contrato externo que se consume.

Objetivo: que el contador suba la foto en Odoo, vea lo que la IA extrajo con su
confianza y advertencias, y **prellene** el formulario de Factura Física Rápida
para revisar y confirmar. La IA propone; el contador decide.

## 2. Alcance

### Dentro del alcance

- Nuevo wizard `l10n.ve.digitize.wizard` (TransientModel) con carga de imagen,
  llamada a `/digitize` y presentación del resultado.
- Cliente HTTP aislado y mockeable hacia `/digitize`, con el mismo patrón de
  autenticación por sesión que ya usa el bot de Discuss (`X-Odoo-Session`).
- Prellenado del wizard existente de Factura Física Rápida (sin reimplementarlo).
- Presentación de `confidence`, `warnings` y líneas extraídas.
- Tratamiento de `nota_credito` / `nota_debito`.
- Trazabilidad de la procedencia en el asiento creado.
- Parámetros de configuración (URL, timeout, tamaño máximo) y ajustes en UI.

### Fuera del alcance (no-objetivos)

- Cambios al backend `contafis-assistant` (contrato, modelos, prompts, OCR).
- OCR/IA local en Odoo (Tesseract, modelos embebidos): se delega al servicio.
- Procesamiento de PDFs multipágina o de texto (solo imágenes y PDF-imagen ya
  rasterizado por el contador).
- Múltiples imágenes por factura o adjuntos adicionales.
- Contabilización de IGTF como línea o impuesto (ver RF y preguntas abiertas).
- Creación de asientos con una línea por ítem de la factura.
- Retenciones IVA/ISLR automáticas a partir de lo extraído.
- Historial persistente de digitalizaciones (el wizard es TransientModel).
- Procesamiento asíncrono / cola de trabajos.
- Reentrenamiento o métricas de calidad del proveedor de IA.

## 3. Actores

- **Contador** (`l10n_ve_compliance_accountant` / `account.group_account_manager`):
  sube la imagen, revisa el resultado y confirma la factura.
- **Administrador**: configura la URL del servicio y los límites en Ajustes.
- **Servicio de digitalización** (FastAPI, externo): autentica la sesión de Odoo,
  extrae los campos y responde JSON.

## 4. Historias de usuario

- HU-1: Como contador quiero subir la foto de una factura y ver los datos que el
  sistema reconoció, para no teclearlos.
- HU-2: Como contador quiero saber **qué tan confiable** es la extracción y qué
  campos revisar, antes de guardar nada.
- HU-3: Como contador quiero que los datos reconocidos lleguen al formulario que ya
  conozco (Factura Física Rápida) y poder corregirlos ahí.
- HU-4: Como administrador quiero que si el servicio está caído, la sesión expiró o
  la imagen no sirve, el contador reciba un mensaje claro y no pierda la imagen.

## 5. Flujo de usuario

1. Menú **Cumplimiento VE → Impuestos → Digitalizar Factura**.
2. El contador elige tipo de operación (Compra / Venta) y, si lo sabe, el tipo de
   documento (Automático por defecto).
3. Adjunta la imagen (`.jpg`, `.jpeg`, `.png`, `.webp`, ≤ 5 MB) con nombre de archivo.
4. Pulsa **Analizar**. El wizard muestra un indicador de espera; la llamada tiene
   timeout (30 s por defecto).
5. Con respuesta válida, el wizard muestra:
   - tipo de documento detectado y **confianza** (0–100 %),
   - **advertencias** del servicio, en texto legible,
   - resumen de datos extraídos (proveedor, RIF, números, fechas, moneda, bases,
     IVA, IGTF, total) y tabla de líneas,
   - aviso si el total extraído no coincide con el total calculado.
6. El contador pulsa **Usar datos en Factura Física Rápida**. Se abre el wizard de
   siempre, prellenado y editable.
7. El contador corrige lo que haga falta y pulsa **Crear y Postear**: el asiento se
   crea y postea con el flujo existente. La digitalización **nunca** postea sola.
8. Si algo falla (servicio, sesión, formato), el wizard queda en estado de error con
   un mensaje accionable y la imagen todavía adjunta para reintentar.

## 6. Contrato de API asumido

Servicio: `contafis-assistant` (repo hermano, no se modifica).

- Endpoint: `POST {base}/digitize`.
- Autenticación: header `X-Odoo-Session: <sid de la sesión web de Odoo>`.
  El backend también acepta `X-User-Token` legacy; **este módulo no lo envía**.
- Headers: `Content-Type: application/json`.
- Timeout backend: `digitize_timeout_seconds = 30.0`. Tamaño máximo backend:
  `digitize_max_image_mb = 5`.

### Request

```json
{
  "image_base64": "iVBORw0KGgoAAAANSUhEUg...",
  "filename": "factura-001.jpg",
  "document_type": "auto"
}
```

| Campo           | Tipo   | Obligatorio | Reglas                                                        |
|-----------------|--------|-------------|---------------------------------------------------------------|
| `image_base64`  | string | sí          | base64 **sin** prefijo `data:image/...;`                       |
| `filename`      | string | sí          | debe cumplir `.*\.(jpg\|jpeg\|png\|webp)$`                     |
| `document_type` | enum   | no          | `factura_z` \| `nota_credito` \| `nota_debito` \| `auto` (default `auto`) |

### Response 200

```json
{
  "document_type": "factura_z",
  "confidence": 0.87,
  "extracted": {
    "supplier_name": "Distribuidora Andina, C.A.",
    "supplier_rif": "J-31527189-4",
    "invoice_number": "00012345",
    "control_number": "00-123456",
    "invoice_date": "2026-10-15",
    "due_date": "2026-11-15",
    "currency": "VES",
    "subtotal": 1000.0,
    "iva_rate": 0.16,
    "iva_amount": 160.0,
    "igtf_rate": 0.03,
    "igtf_amount": 0.0,
    "total": 1160.0,
    "lines": [
      {"description": "Servicio de mantenimiento", "quantity": 1.0, "unit_price": 1000.0, "total": 1000.0}
    ],
    "credit_note_ref": null,
    "debit_note_ref": null
  },
  "warnings": [
    {"code": "low_confidence", "message": "Confianza baja en el número de control", "field": "control_number", "extracted_value": "00-123456"}
  ]
}
```

| Campo          | Tipo   | Notas                                                        |
|----------------|--------|--------------------------------------------------------------|
| `document_type`| enum   | `factura_z` \| `nota_credito` \| `nota_debito` (nunca `auto`) |
| `confidence`   | float  | 0.0–1.0                                                       |
| `currency`     | string | `VES` \| `USD`, default `VES`                                 |
| `iva_rate`     | float  | fracción, ej. `0.16` (16 %), `0.08` (8 %)                     |
| `igtf_rate`    | float  | fracción, ej. `0.03`                                          |
| `lines[]`      | array  | puede venir vacío                                             |
| `warnings[].code` | enum | `low_confidence`, `invalid_rif`, `amount_mismatch`, `missing_field`, `unknown_document_type`, `parsing_error` |

### Errores

| HTTP      | Significado                                   | Reacción en Odoo                                    |
|-----------|-----------------------------------------------|-----------------------------------------------------|
| `400`     | request inválido (base64/formato)              | Mensaje: imagen o formato no válido                 |
| `401/403` | sesión Odoo inválida o expirada                | Mensaje: recargar Odoo e intentar de nuevo          |
| `503`     | NIM no disponible / timeout / parsing          | Mensaje: servicio no disponible, reintentar         |
| `5xx`     | error del servidor                             | Mensaje: error del servidor, reintentar             |
| otro `4xx`| error de petición                              | Mensaje genérico de petición rechazada              |

## 7. Requisitos funcionales (EARS)

- **RF-01**: EL SISTEMA expone el menú **Digitalizar Factura** bajo *Impuestos* y
  abre el wizard `l10n.ve.digitize.wizard` en modal.
- **RF-02**: CUANDO el contador adjunta un archivo, EL SISTEMA acepta solo
  extensiones `.jpg`, `.jpeg`, `.png`, `.webp` (sin distinguir mayúsculas) y hasta
  el tamaño máximo configurado (5 MB por defecto); si no cumple, informa y no llama
  al servicio.
- **RF-03**: CUANDO el contador pulsa **Analizar**, EL SISTEMA envía a `/digitize`
  el JSON del contrato con `image_base64` sin prefijo `data:`, el `filename` y el
  `document_type` elegido (default `auto`), con header `X-Odoo-Session` y timeout
  configurable (30 s por defecto).
- **RF-04**: SI no hay URL de servicio configurada, ENTONCES EL SISTEMA no llama al
  servicio y muestra un mensaje que indica dónde configurarla.
- **RF-05**: SI no se puede obtener el `sid` de la sesión (contexto no HTTP, sesión
  vacía), ENTONCES EL SISTEMA no llama al servicio y muestra el mensaje de sesión no
  detectada, sin lanzar excepción de Python.
- **RF-06**: CUANDO el servicio responde `200` con JSON válido, EL SISTEMA guarda
  `confidence`, `document_type`, los campos extraídos y las advertencias, y deja el
  wizard en estado `done`.
- **RF-07**: EL SISTEMA muestra la confianza como porcentaje junto a un indicador
  visual (alta / media / baja) y lista las advertencias del servicio con código y
  mensaje, **como texto plano** (nunca como HTML proveniente del servicio).
- **RF-08**: EL SISTEMA muestra en solo lectura las líneas extraídas (descripción,
  cantidad, precio unitario, total) y un aviso **no bloqueante** cuando el total
  extraído difiere del total calculado con las bases.
- **RF-09**: EL SISTEMA ofrece el botón **Usar datos en Factura Física Rápida**
  únicamente en estado `done`, y al pulsarlo abre el wizard
  `l10n.ve.physical.invoice.wizard` prellenado con los datos del RF-10.
- **RF-10**: EL SISTEMA mapea los campos extraídos al wizard de factura física así:
  `supplier_rif → partner_vat`, `supplier_name → new_partner_name`,
  `invoice_number → invoice_number`, `control_number → control_number`,
  `invoice_date → invoice_date`, `due_date → invoice_date_due`,
  `currency → currency_id` (`VES` → moneda de la compañía; `USD` → dólar activo),
  `subtotal → base_*` según `iva_rate` (0.16 → `base_general`, 0.08 →
  `base_reduced`, > 0.16 → `base_additional`, 0 → `base_not_taxed`),
  `total → physical_total`, y `lines[].description` → `concept` (recortado).
- **RF-11**: SI un dato obligatorio del wizard destino no viene en la respuesta,
  ENTONCES EL SISTEMA lo deja vacío y lo señala en las advertencias; nunca inventa
  valores ni completa números por defecto.
- **RF-12**: SI el servicio responde `400`, `401`/`403`, `503`, `5xx`, hay timeout,
  la respuesta no es JSON o le faltan claves obligatorias, ENTONCES EL SISTEMA deja
  el wizard en estado `error`, muestra un mensaje específico y conserva la imagen
  adjunta para reintentar; no crea ni postea ningún asiento.
- **RF-13**: CUANDO el documento detectado es `nota_credito`, EL SISTEMA lo propaga
  al wizard destino y el asiento se crea como nota de crédito (`in_refund` en
  compras, `out_refund` en ventas) con la referencia `credit_note_ref` en `ref`.
- **RF-14**: CUANDO el documento detectado es `nota_debito`, EL SISTEMA lo propaga,
  crea el asiento como factura del tipo de operación elegido con `debit_note_ref` en
  `ref` y registra la naturaleza de nota de débito en la narración del asiento.
- **RF-15**: EL SISTEMA no crea ni postea asientos al digitalizar: la creación y el
  posteo ocurren únicamente al pulsar **Crear y Postear** en el wizard de factura
  física, con las validaciones que ese wizard ya aplica.
- **RF-16**: CUANDO se crea el asiento desde el flujo digitalizado, EL SISTEMA
  registra la procedencia en la narración (`document_type`, confianza, cantidad de
  advertencias) sin modificar importes, impuestos ni líneas del asiento.
- **RF-17**: EL SISTEMA registra el asiento con `company_id` igual a la compañía
  activa del usuario y busca partner, diario y cuentas con el filtro de esa
  compañía; un partner de otra compañía no se reutiliza por coincidencia de RIF.

## 8. Requisitos no funcionales

- **RNF-01 Tests como puerta**: cada RF con al menos un test; el conteo oficial es
  el de Odoo (`odoo.tests.result`). Base 344: ningún commit puede bajar ese número
  ni dejar `failed`/`error`.
- **RNF-02 Sin red en tests**: toda llamada HTTP se mockea (`requests.post`); la
  suite no puede abrir conexiones reales ni depender de que el servicio esté vivo.
- **RNF-03 Robustez**: el código no asume contexto HTTP (crons, shell, tests); si
  falta el `sid` degrada con mensaje, nunca con `AttributeError`.
- **RNF-04 Seguridad de datos**: la imagen viaja en memoria y no se envía a ningún
  otro destino; no se loguea el base64 ni el `sid`; los logs solo registran nombre,
  tamaño, código HTTP y duración. Las advertencias del servicio se renderizan como
  texto plano (sin `markup`/`t-raw`), evitando XSS.
- **RNF-05 Límites**: tamaño máximo de imagen y timeout configurables por
  `ir.config_parameter`; valores por defecto 5 MB y 30 s, alineados al backend.
- **RNF-06 Sin reintentos automáticos**: una sola llamada por pulsación, para no
  duplicar trabajo ni costos del proveedor.
- **RNF-07 Multi-cliente**: el asiento resultante pertenece a la compañía activa;
  no se comparte caché ni resultado entre compañías (el wizard es TransientModel y
  no persiste historial).
- **RNF-08 Convenciones Odoo 19**: `<list>` (no `<tree>`), `invisible="campo != 'x'"`
  (sin `states` ni `attrs`), `view_mode="list,form"`, `@api.depends` explícito,
  `inverse` solo si hay computed almacenado editable.
- **RNF-09 Idioma**: identificadores en inglés, etiquetas/`help`/docs en español.
- **RNF-10 Odoo como única fuente de verdad**: se extiende
  `l10n.ve.physical.invoice.wizard` con `_inherit`; no se duplica la lógica de
  creación/posteo de asientos.

## 9. Criterios de aceptación

- **CA-1**: desde el menú, el contador digitaliza una imagen y ve confianza,
  advertencias y datos extraídos sin salir del modal.
- **CA-2**: el botón de prellenado abre el wizard de Factura Física Rápida con RIF,
  razón social, número, control, fechas, moneda, bases y total ya cargados y
  editables.
- **CA-3**: con el servicio caído (mock `503`), la sesión inválida (mock `401`),
  imagen de 6 MB y archivo `.gif`, el wizard da mensajes distintos y accionables, y
  no se crea ningún `account.move`.
- **CA-4**: `0 failed, 0 error(s) of N` con `N ≥ 344 + tests nuevos`.
- **CA-5**: verificación visual en navegador (Chrome DevTools) del menú, del estado
  con resultado y del estado con error; sin errores JS en consola.
- **CA-6**: el `account.move` creado desde el flujo digitalizado queda `posted`, con
  la compañía activa, el `ref` correcto y la procedencia en la narración; el Libro
  de Compras/Ventas se genera como con cualquier factura física.
- **CA-7**: `git status` sin archivos inesperados y `pre-commit` verde.

## 10. Riesgos y mitigaciones

| Riesgo                                                        | Mitigación                                                                 |
|---------------------------------------------------------------|----------------------------------------------------------------------------|
| El backend cambia el contrato                                  | Validación tolerante: se exigen solo claves usadas, se ignoran las extra; test de contrato fijo con fixture JSON |
| Extracción errónea que el contador acepta sin revisar          | Mostrar confianza + advertencias + descuadre antes del prellenado; nada se postea solo (RF-15) |
| Imagen grande o escaneo de alta resolución                     | Límite local antes de enviar (RF-02) y límite del backend (503/400)         |
| Sesión expirada a mitad de la jornada del contador              | Mensaje específico 401/403 y conservación de la imagen (RF-12)              |
| Duplicar lógica de factura física y desincronizarla            | Prellenado por `default_*` sobre el wizard existente; cero lógica de asientos nueva |
| Fuga de datos fiscales en logs                                 | RNF-04: nunca se loguea base64, `sid` ni el contenido extraído completo      |
| Tests que dependan de red o del proveedor                      | RNF-02: mock obligatorio; ningún test con URL real                          |
| Regresión en el wizard existente (344 tests)                   | Cambios al wizard físico mínimos y aditivos (campos nuevos con default)     |

## 11. Decisiones cerradas (2026-11-01)

Resueltas con el usuario antes de iniciar la implementación:

1. **IGTF**: solo informativo. Se muestra el monto extraído, no se contabiliza ni se
   agrega campo a `account.move` ni al wizard físico.
2. **`nota_debito`**: crea asiento como factura normal (mismo flujo que la factura) y
   guarda la referencia del documento original en `ref`/narración.
3. **`iva_rate = 0`**: se mapea a `base_not_taxed` (no gravada). No se usa
   `base_not_subject` porque el contrato no distingue y no se debe adivinar.
4. **`lines[]`**: no generan líneas de asiento; solo alimentan el `concept` del wizard
   con las descripciones extraídas.
5. **`emission_type`**: no viene del backend; queda en el valor por defecto del wizard
   (`talonario`) y el contador lo ajusta.
6. **URL del servicio**: parámetro propio `l10n_ve_digitize.url`, independiente de
   `l10n_ve_chat.webhook_url`.
