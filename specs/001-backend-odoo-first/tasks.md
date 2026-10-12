# Tasks 001 - Backend Odoo-First: Cargar facturas, generar libro y asientos

Estado: pendiente

## Tareas

- [x] **T1. `account.tax`: campo `l10n_ve_tax_type`.**
  RF-15.
  Test primero: `test_account_tax_l10n_ve_type_field` (en rojo).
  Hecho cuando: test pasa + grep muestra Selection con 8 valores.

- [x] **T2. `vat.book.line`: campos source, account_move_id, auditoría.**
  RF-9, RF-10.
  Tests: `test_source_and_audit_fields`, `test_multi_base_field`.
  Hecho cuando: 2 tests pasan + campos existen con tipos correctos.

- [x] **T3. Refactor `_get_operation_code()` (import_wizard → vat_book_line).**
  RF-12.
  Test primero: `test_get_operation_code_helper`.
  Hecho cuando: test pasa + llamadas existentes en import_wizard actualizadas + 107 tests siguen verdes.

- [x] **T4. `account.move`: campo `l10n_ve_control_number` + `_generate_vat_book_line()`.**
  RF-2, RF-16.
  Test primero: `test_account_move_control_number_field` + `test_post_invoice_generates_vat_book_line`.
  Hecho cuando: 2 tests pasan + método deriva línea con source='odoo_invoice' + operation_code correcto.

- [x] **T5. `account.move`: overrides `_post()` y `button_draft()`.**
  RF-2, RF-8.
  Tests: `test_post_regenerates_safely`, `test_button_draft_deletes_odoo_lines`.
  Hecho cuando: 2 tests pasan + reversión borra solo source='odoo_invoice'.

- [x] **T6. Botón regenerar + wizard confirm.**
  RF-3, RF-14.
  Modelo: `l10n.ve.regenerate.confirm.wizard`.
  Test: `test_regenerate_confirm_wizard_flow`.
  Hecho cuando: test pasa + acción abre wizard si hay is_manually_modified=True + toast si no.

- [x] **T7. Wizard factura física: modelo completo.**
  RF-1, RF-4, RF-5, RF-6, RF-7, RF-13.
  Modelo: `l10n.ve.physical.invoice.wizard`.
  Tests: `test_wizard_create_purchase_invoice`, `test_wizard_create_sale_invoice`, `test_wizard_validates_rif_module_11`, `test_wizard_creates_partner_inline`, `test_wizard_physical_total_warning`.
  Hecho cuando: 5 tests pasan.

- [x] **T8. Vistas XML: wizard, account.move, vat.book.line.**
  RF-1, RF-3, RF-9, RF-10, RF-13, RF-14.
  Verificación: pre-commit run check-xml + visual manual.
  Hecho cuando: 3 archivos XML cargan sin error + 107 tests verdes + sin attrs= + sin confirm= en botones.

- [x] **T9. ACLs, manifest, post_init_hook, export regression.**
  RF-9, RF-11.
  Test primero: `test_export_xlsx_includes_odoo_lines`.
  Hecho cuando: test pasa + hook ejecuta UPDATE source en líneas existentes + módulo instala limpio.

- [ ] **T10. Regresión completa + verificación visual.**
  Todos los RFs.
  Comando: `docker compose run --rm web odoo -d contea -u l10n_ve_compliance_manager --test-enable --stop-after-init --workers 0 --test-tags /l10n_ve_compliance_manager`
  Hecho cuando: 0 failed, 0 error(s) of 122 tests + Ruff limpio + creación manual de factura por wizard end-to-end verificada.
