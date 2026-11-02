# Tasks 007 - Wizard de Digitalización

Spec: `specs/007-digitalizacion/spec.md` · Plan: `specs/007-digitalizacion/plan.md`

Reglas: una tarea a la vez, en orden de dependencia. Commit al terminar cada tarea solo
si los tests pasan. El conteo oficial es el de Odoo (`odoo.tests.result`), nunca
`grep -c`. Sin archivos temporales ni scripts de diagnóstico.

Comando oficial de tests:

```
docker compose run --rm web odoo -d contea -u l10n_ve_compliance_manager \
  --test-enable --stop-after-init --workers 0 \
  --test-tags /l10n_ve_compliance_manager
```

Baseline: `0 failed, 0 error(s) of 362 tests` (tras T1, commit `fd0d781`: 344 + 18 de T1).

---

- [x] **T1. Wizard base + cliente HTTP a `/digitize`.**
      RF-01, RF-02, RF-03, RF-04, RF-05, RF-12 · RNF-02, RNF-03, RNF-04, RNF-05

      Alcance:
      1. `l10n.ve.digitize.wizard` (TransientModel) con `type`, `document_type_hint`,
         `image` (Binary), `filename`, `state` (draft/done/error), `confidence`,
         `detected_document_type`, `error_message`.
      2. Vista form (`views/digitize_wizard_views.xml`) con `<list>` si aplica,
         `invisible="state != 'done'"` (sin `states`/`attrs`), `<header>` con
         Analizar / Cancelar, `ir.actions.act_window` `target="new"` y menú
         "Digitalizar Factura" bajo `menu_l10n_ve_compliance_taxes` (sequence 60).
      3. `models/digitize_client.py` con `_get_session_id()` (mismo blindaje
         `try/except` de `discuss_channel.py`) y `post_digitize(url, session_id,
         payload, timeout)` que hace `requests.post` con
         `Content-Type: application/json` + `X-Odoo-Session`.
      4. `action_digitize()`: valida extensión (`.jpg/.jpeg/.png/.webp`) y tamaño
         (`l10n_ve_digitize.max_image_mb`, default 5) → arma payload
         (`image_base64` sin prefijo `data:`, `filename`, `document_type`) → llama
         al cliente → mapea 200/4xx/5xx/timeout/JSON inválido al estado `error` con
         mensaje específico (tabla del plan §3). No crea `account.move`.
      5. Parámetros `l10n_ve_digitize.url`, `l10n_ve_digitize.timeout_seconds` (30) y
         `l10n_ve_digitize.max_image_mb` (5) en `data/ir_config_parameter_data.xml`
         (`noupdate="1"`), campos en `res.config.settings` + bloque en Ajustes.
      6. ACL de `l10n.ve.digitize.wizard` (base.group_user,
         account.group_account_manager, l10n_ve_compliance_accountant), registro en
         `models/__init__.py`, `__manifest__.py` (versión `19.0.1.4.0`), vista antes
         de `views/menu.xml`.

      Tests nuevos (`tests/test_digitize_wizard.py`, `TestDigitizeClient` y
      `TestDigitizeWizardErrors`): `test_post_digitize_sends_payload_and_session_header`,
      `test_post_digitize_uses_configured_timeout`,
      `test_post_digitize_returns_response_on_200`,
      `test_post_digitize_propagates_timeout`,
      `test_action_digitize_requires_url`, `test_action_digitize_requires_session`,
      `test_action_digitize_maps_401_to_session_error`,
      `test_action_digitize_maps_503_to_unavailable`,
      `test_action_digitize_maps_400_to_invalid_request`,
      `test_action_digitize_maps_500_to_server_error`,
      `test_action_digitize_handles_invalid_json`,
      `test_action_digitize_rejects_oversized_image`,
      `test_action_digitize_rejects_unsupported_extension`,
      `test_action_digitize_does_not_log_image_or_session`,
      `test_menu_and_action_exist`.
      Todos con `patch('requests.post')` (cero red real).

      Hecho cuando: el menú abre el modal; con mock 200 el wizard queda en `done` y
      guarda `confidence`/`document_type`; con URL ausente, sesión ausente, 400,
      401, 503, 500, timeout y JSON roto el wizard queda en `error` con mensajes
      distintos y sin excepción de Python sin controlar; una imagen de 6 MB y un
      `.gif` se rechazan antes de llamar al servicio; el log no contiene el base64
      ni el `sid`; `0 failed, 0 error(s) of N` con `N > 344`.

- [x] **T2. Mapeo `extracted` → defaults del wizard de Factura Física Rápida.**
      RF-09, RF-10, RF-11, RF-17

      Alcance:
      1. Campos de vista previa en el wizard de digitalización (`supplier_name`,
         `supplier_rif`, `invoice_number`, `control_number`, `invoice_date`,
         `due_date`, `currency_code`, `subtotal`, `iva_rate`, `iva_amount`,
         `igtf_amount`, `total`, `credit_note_ref`, `debit_note_ref`) y parseo
         tolerante de la respuesta (`_parse_response`).
      2. `_map_extracted_to_invoice_defaults()` puro (devuelve `dict` de
         `default_*`) con las reglas del RF-10: `iva_rate` 0.16 → `base_general`,
         0.08 → `base_reduced`, >0.16 → `base_additional`, 0 → `base_not_taxed`;
         `currency` `VES` → moneda de la compañía, `USD` → `res.currency` activa
         con nombre `USD` (sin `sudo`); `lines[].description` → `concept` recortado.
      3. `action_apply_to_invoice()`: devuelve `ir.actions.act_window` a
         `l10n.ve.physical.invoice.wizard` (`target="new"`, `context=defaults`).
      4. Datos ausentes → campo vacío + advertencia local `missing_field`; RIF
         inválido → `partner_vat` cargado igual (dato del contador) + advertencia, sin
         `partner_id`.

      Tests nuevos (`TestDigitizeMapping`): `test_apply_returns_physical_wizard_action_with_defaults`,
      `test_maps_general_rate_to_base_general`, `test_maps_reduced_rate_to_base_reduced`,
      `test_maps_zero_rate_to_base_not_taxed`, `test_maps_usd_currency`,
      `test_maps_dates_and_numbers`, `test_maps_concept_from_lines`,
      `test_matches_existing_partner_by_rif`,
      `test_invalid_rif_is_warned_and_partner_left_empty`,
      `test_missing_amounts_do_not_raise`.
      Fixture compartido: `tests/fixtures/digitize_response_200.json`.

      Tests añadidos al cerrar la revisión: `test_digitize_persists_local_warnings`,
      `test_apply_does_not_default_invoice_date_to_today`,
      `test_partner_from_other_company_is_not_reused`,
      `test_parse_response_tolerates_malformed_optional_parts`.
      Deuda de T1 pagada en T2: `test_timeout_is_floored_to_one_second` y
      `test_get_image_base64_encodes_raw_bytes` (+2 tests, no estaban en la lista
      original). Total T2: 16 tests nuevos → 362 + 16 = **378**.

      Hecho cuando: desde `done`, la acción `action_apply_to_invoice` devuelve el
      wizard de factura física con RIF, razón social, número, control, fechas,
      moneda, base, total y concepto cargados; el RIF válido resuelve el partner
      existente; un RIF inválido o un dato ausente quedan vacíos y advertidos sin
      bloquear; las advertencias locales se persisten en `warnings_json` (servicio
      primero, dedupe por código+campo); una `invoice_date` ausente **no** cae en la
      fecha de hoy del wizard destino; `0 failed, 0 error(s) of 378 tests`.

      Cierre: el botón "Usar datos…" de la vista es T3 (la vista sigue igual que
      T1); T2 entrega la acción y sus tests de modelo. El `onchange` del wizard
      destino **no** se dispara al abrirlo con `default_*` (verificado en
      `relational_model/record.js`: solo `_update(changes)` invoca `_onchange`).

- [ ] **T3. UI de confianza, advertencias y líneas extraídas.**
      RF-06, RF-07, RF-08 · RNF-04

      Alcance:
      1. Modelo hijo `l10n.ve.digitize.line` (`description`, `quantity`,
         `unit_price`, `total`) como `One2many` de solo lectura en el wizard; se
         recrea en cada análisis.
      2. `confidence_pct` (compute), `has_warnings` (compute), `warnings_text`
         (compute, texto plano con viñetas `código: mensaje`), `total_mismatch`
         (compute booleano: `total` extraído vs total calculado con las bases).
      3. Vista: indicador de confianza (alta ≥ 0.85 / media ≥ 0.6 / baja < 0.6) con
         decoración, bloque de advertencias solo si `has_warnings`, tabla de líneas y
         alerta de descuadre **no bloqueante** (`invisible="not total_mismatch"`).
      4. Sin HTML crudo del servicio: `warnings_text` es `Text`, nunca `markup`.

      Tests nuevos (`TestDigitizeWarningsUi`): `test_warnings_text_lists_every_code`,
      `test_has_warnings_flag`, `test_low_confidence_threshold_flag`,
      `test_line_preview_rows_created`, `test_total_mismatch_flag_true_when_difference`,
      `test_warning_text_is_plain_text`.

      Hecho cuando: los seis códigos de advertencia del contrato se listan legibles;
      `confidence` 0.87 sale como 87 % y como confianza alta; una respuesta con dos
      líneas crea dos registros de vista previa; el descuadre aparece cuando
      `total` ≠ suma de bases e IVA y no impide continuar; `0 failed of N`.

- [ ] **T4. Notas de crédito y débito.**
      RF-13, RF-14

      Alcance:
      1. Campos `digitized_document_type` (Selection `factura_z`/`nota_credito`/
         `nota_debito`), `digitize_confidence` y `digitized_document_ref` (Char) en
         `l10n.ve.physical.invoice.wizard` (aditivo, default `False`/`0.0`/`False`),
         pasados por `context` desde el wizard de digitalización. T4 extiende
         `_map_extracted_to_invoice_defaults` (creada en T2) con las claves
         `default_digitized_document_type`, `default_digitize_confidence` y
         `default_digitized_document_ref` (este último = `credit_note_ref` o
         `debit_note_ref` según el tipo detectado); T2 no emite claves `default_*`
         sin campo destino.
      2. En `action_create_and_post`: `move_type` según la tabla del plan §3
         (`in_refund`/`out_refund` para nota de crédito; factura normal para nota de
         débito). Comportamiento actual intacto cuando
         `digitized_document_type` está vacío (guardia de no regresión).
      3. `ref` = `digitized_document_ref` (alimentado desde `credit_note_ref` o
         `debit_note_ref` según el tipo detectado) cuando exista; si no, se mantiene
         `control_number` (comportamiento actual).
      4. Narración: prefijo `[Digitalizado] tipo=... confianza=... advertencias=...`
         antepuesto al concepto, solo en el flujo digitalizado.

      Tests nuevos (`TestDigitizeDocumentTypes`): `test_credit_note_purchase_creates_refund`,
      `test_credit_note_sale_creates_refund`,
      `test_credit_note_uses_credit_note_ref`,
      `test_debit_note_creates_invoice_with_ref_and_narration`,
      `test_unknown_document_type_falls_back_to_invoice_with_warning`.

      Hecho cuando: una nota de crédito de compra crea `in_refund` posteado y de
      venta `out_refund`; una nota de débito crea factura con `debit_note_ref` en
      `ref` y la marca en la narración; el flujo manual (sin digitalizar) sigue
      creando `in_invoice`/`out_invoice` exactamente igual que antes; `0 failed of N`.

- [ ] **T5. Creación/posteo del asiento desde el flujo digitalizado (E2E).**
      RF-15, RF-16, RF-17 · RNF-07, RNF-10

      Alcance:
      1. Test end-to-end con el wizard real: mock 200 → prellenado → `action_create_and_post`
         → `account.move.state == 'posted'`, `company_id` = compañía activa,
         `ref`/fechas/importes correctos.
      2. Verificar `vat.book.line` generado por el override existente de `_post`
         (sin tocar `account_move.py`).
      3. Verificar que el asiento no guarda la imagen ni referencia al servicio, y
         que la narración contiene la procedencia.
      4. Segunda compañía en el test: el partner de la compañía A no se reutiliza
         para el asiento de la compañía B; el wizard no necesita `sudo()`.
         Además, `_onchange_partner_vat` y `action_create_and_post` del wizard
         físico buscan el partner **sin** filtro de compañía; T2 solo filtra en
         `_map_extracted_to_invoice_defaults`. T5 debe agregar
         `('company_id', 'in', [False, self.env.company.id])` a ambas búsquedas para
         que RF-17 se cumpla de punta a punta (hoy una coincidencia de RIF de otra
         compañía podría reutilizarse al crear el asiento).
      5. Ajustes mínimos que aparezcan necesarios (sin cambiar el comportamiento
         manual); si el cambio supera 60 líneas, detenerse y reportar.

      Tests nuevos (`TestDigitizeEndToEnd`): `test_digitized_flow_creates_posted_move`,
      `test_digitized_move_uses_active_company`,
      `test_digitized_move_narration_has_provenance`,
      `test_digitized_move_generates_vat_book_line`,
      `test_digitized_partner_not_reused_across_companies`,
      `test_digitize_never_posts_without_confirmation`.

      Hecho cuando: el flujo completo deja un asiento `posted` con Libro de
      Compras/Ventas generado; digitalizar sin pulsar Crear y Postear no crea nada
      (`account.move` count sin cambios); `0 failed of N` y ningún test del wizard
      físico previo cambia de resultado.

- [ ] **T6. Verificación visual, documentación y cierre.**
      Todos los RF

      Alcance:
      1. Verificación en navegador (Chrome DevTools, `isolatedContext` si hay choque
         de cookies): menú visible, estado con resultado (confianza, advertencias,
         líneas), estado con error y apertura del wizard prellenado. Capturas en
         `C:\Users\hp\AppData\Local\Temp\opencode\spec007-*.png`.
      2. Docs: nueva sección de digitalización en `docs/capacidades/04-retenciones.md`
         o en la capacidad que corresponda, `SPEC.md` (roadmap + conteo de tests) y
         `docs/guia-usuario/anexo-limitaciones.md` (sin contabilización de IGTF, sin
         líneas por ítem, notas de débito como factura).
      3. `docs/memory.md`: decisión de arquitectura (wizard separado + defaults),
         patrón de cliente HTTP, parámetros y preguntas abiertas resueltas. No se
         commitea (está en `.gitignore`).
      4. `git status` solo con archivos esperados; `pre-commit run --all-files` verde.

      Tests: ninguno nuevo; se re-corre la suite completa.

      Hecho cuando: capturas de los tres estados y del prellenado; `0 failed,
      0 error(s) of N` con `N` = 362 + tests de T2–T5; docs actualizadas; un commit
      `docs(spec): close phase 007-digitalizacion` con los artefactos de la spec en
      verde.

---

## Orden y dependencias

```
T1 (wizard + cliente HTTP)
 ├── T2 (mapeo) ── T3 (UI de resultado)
 │                    └── T4 (notas) ── T5 (E2E de asiento)
 └──────────────────────────────────────────┴── T6 (visual + docs + cierre)
```

T1 es la única tarea que no se puede paralelizar. T2 y T3 comparten archivos
(`digitize_wizard.py` y su vista), así que van en serie. T4 toca el wizard físico:
conviene después de T2 para no reescribir el mapeo.
