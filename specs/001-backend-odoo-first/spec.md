# Spec 001 - Backend Odoo-First: Cargar facturas, generar libro y asientos

Estado: borrador

## Contexto y objetivo

El contador gestiona ~100 facturas/mes y necesita un flujo **Odoo-first**: crear facturas reales en `account.move` (con líneas, impuestos y socios) → generar automáticamente líneas del libro fiscal (`vat.book.line`) → exportar planilla 99030 SENIAT y declaración IVA. Esto reemplaza la dependencia de Excel como fuente primaria y aprovecha el motor contable de Odoo (cuadre, conciliación bancaria, reportes estándar). La arquitectura es **dual-track**: capa contable (`account.move` + `account.tax`) y capa fiscal (`vat.book.line`) paralelas, alimentadas del mismo asiento.

## Usuarios / actores

- **Contador**: crea facturas de compra/venta vía wizard rápido, revisa libro, exporta.
- **Sistema**: deriva `vat.book.line` desde `account.move` posteado, sincroniza al postear o bajo demanda.

## Historias de usuario

- HU-1: Como contador, quiero crear una factura de compra ingresando RIF, bases de IVA y número de control en un wizard, para que Odoo genere el asiento contable y la línea del libro fiscal automáticamente.
- HU-2: Como contador, quiero que al postear la factura se genere/actualice la `vat.book.line` vinculada, para que el libro fiscal refleje siempre la contabilidad.
- HU-3: Como contador, quiero un botón "Regenerar libro" en la factura posteada, para corregir la línea fiscal si edité impuestos o bases tras postear.
- HU-4: Como contador, quiero que si el RIF no existe, el wizard cree el `res.partner` inline validando el dígito de control (módulo 11), sin salir del formulario.
- HU-5: Como contador, quiero exportar el libro (XLSX) y la declaración IVA (XLSX+PDF) reusando los exports existentes, incluyendo líneas de todos los orígenes (Odoo, Excel, manual).

## Requisitos funcionales (EARS)

- RF-1: CUANDO el usuario completa el wizard de factura física y pulsa "Crear y Postear", EL SISTEMA crea un `account.move` (`in_invoice` o `out_invoice`) con líneas de base por tasa (general 16%, reducida 8%, no sujeta, no gravada, sin derecho a crédito), cada una con su `tax_id` correspondiente, y lo postea. El wizard requiere al menos una base > 0 (validación bloqueante). El wizard opera en self.env.company y filtra journal_id, tax_id y partner_id por esa company. Los campos de base rechazan valores negativos (validación inline).
- RF-2: CUANDO se postea un account.move de tipo factura (in_invoice/out_invoice), EL SISTEMA llama a _generate_vat_book_line() que:
(a) Si existen vat.book.line con account_move_id=self.id, source='odoo_invoice' e is_manually_modified=True, ENTONCES muestra diálogo de confirmación (ver RF-14).
(b) Borra las vat.book.line con account_move_id=self.id y source='odoo_invoice' (sin tocar otras sources).
(c) Deriva nuevas líneas desde account.move.line con tax_ids, asignando base_general, vat_general, base_reduced, vat_reduced, base_no_credit según el tax_id, marcando source='odoo_invoice' y calculando operation_code vía _get_operation_code() (ver RF-12).

La sincronización se hace vía override de _post() en account.move (extensión con _inherit, NO reimplementación). button_draft() también se sobrescribe para borrar las líneas vat.book.line asociadas (ver RF-8).
- RF-3: SI el usuario pulsa "Regenerar libro" en una factura posteada, ENTONCES EL SISTEMA ejecuta `_generate_vat_book_line()` de nuevo y muestra toast estándar de Odoo (notification type='success') con el número de líneas generadas. El botón está visible y habilitado solo si state='posted'.
- RF-4: CUANDO el usuario escribe un RIF en el wizard, EL SISTEMA valida el dígito de control (módulo 11). SI falla, ENTONCES muestra error inline y bloquea la creación.
- RF-5: SI el RIF validado no existe en `res.partner`, ENTONCES EL SISTEMA expande inline una sección "Nuevo partner" con razón social (requerida), tipo (proveedor/cliente/ambos), dirección, email, teléfono; al guardar crea el partner con `vat=RIF` y `company_type` según tipo.
- RF-6: SI el RIF validado existe, ENTONCES EL SISTEMA autocompleta `partner_id` y muestra la razón social editable.
- RF-7: El wizard tiene campo type = fields.Selection([('purchase', 'Compra'), ('sale', 'Venta')], required=True, default='purchase'). EL SISTEMA provee un selector "Tipo: Compra / Venta" en el wizard que cambia los defaults: `journal_id` (diario compras/ventas), `account_id` (gasto/ingreso), `tax_id` (crédito/débito fiscal), `company_type` default del partner.
- RF-8: CUANDO se pone a borrador una factura posteada (`button_draft`), EL SISTEMA borra las `vat.book.line` asociadas con `source='odoo_invoice'` y `account_move_id` de esa factura.
- RF-9: EL SISTEMA añade campo `source` (Selection: 'odoo_invoice', 'excel_import', 'manual', 'adjustment') y `account_move_id` (Many2one, opcional, readonly, ondelete='set null') en `vat.book.line`. Además agrega 3 campos de auditoría en vat.book.line:
- modified_by (Many2one res.users, readonly): usuario de la última edición manual.
- modified_at (Datetime, readonly): timestamp de la última edición manual.
- is_manually_modified (Boolean, computed, stored): True si modified_by != create_uid.
Estos campos se actualizan vía override de write() cuando el usuario es distinto del create_uid. Migración: líneas existentes quedan con `source='excel_import'`.
- RF-10: EL SISTEMA permite que una factura con múltiples bases (ej. general + reducida) genere múltiples `vat.book.line` vinculadas al mismo `account_move_id` (una por tasa), coherente con el canal Excel.
- RF-11: LOS EXPORTS existentes (vat.book.line XLSX, vat.return XLSX+PDF) funcionan sin cambios incluyendo líneas `source='odoo_invoice'`. No se filtran por source.
- RF-12: EL SISTEMA mueve la función `_get_vat_book_operation_code(rate_type, book_type)` de `import_wizard.py` a `vat_book_line.py` como método `_get_operation_code()` a nivel modelo. Actualiza las llamadas existentes en `import_wizard.py`. El helper es @api.model (no depende de un record).
- RF-13: EL SISTEMA incluye campo opcional "Total según factura física (Bs)" en el wizard de factura. SI el total físico ≠ sum(bases) + sum(IVAs calculadas), ENTONCES muestra warning informativo (no bloquea). El usuario edita las BASES si no cuadran; el campo 'Total según factura física' es solo informativo (readonly).
- RF-14: SI el usuario pulsa "Regenerar libro" en una factura con líneas vat.book.line previamente editadas manualmente, ENTONCES diálogo estándar de Odoo (self.env.user.notify_warning con confirmación) avisa "Regenerar borrará ediciones manuales. ¿Continuar?". El usuario puede cancelar.
- RF-15: EL SISTEMA agrega campo l10n_ve_tax_type (Selection) a account.tax vía _inherit, con valores: 'general', 'reduced', 'additional', 'no_credit', 'exempt', 'not_subject', 'import', 'non_contrib'. Este campo permite mapear cada tax a su rate_type para el derivador _generate_vat_book_line().
- RF-16: EL SISTEMA agrega campo l10n_ve_control_number (Char) a account.move vía _inherit, para almacenar el número de control SENIAT. El wizard lo completa y el derivador lo copia a vat.book.line.control_number.

## Requisitos no funcionales

- Rendimiento: `_generate_vat_book_line()` ejecuta en <200ms para factura típica (5 líneas base).
- Trazabilidad: `vat.book.line` registra `account_move_id` para auditoría bidireccional.
- Multi-cliente: todo filtra por `company_id` (heredado de `account.move`).
- Tests: 15 tests nuevos (4 mínimos + 5 adicionales + 3 por RF-12/13/14 + 2 por RF-15/16 + 1 test_multi_base_field) + 107 existentes = 122 total pasando.

## Casos límite

- RIF con dígito de control inválido → error inmediato en wizard.
- Factura con base 0 en alguna tasa → no genera `vat.book.line` para esa tasa.
- Edición de factura posteada sin regenerar → libro desactualizado (avisar en UI).
- Partner creado por wizard con RIF persona natural (V/E) vs jurídica (J/G) → `company_type` correcto.
- Impuestos no configurados (falta IVA General 16%, etc.) → validación al instalar módulo (post_init hook), no en wizard.
- Wizard con todas las bases en 0 → error bloqueante.
- Valores negativos en bases → validación inline rechaza.
- Impuesto borrado por admin post-instalación → wizard error claro apuntando a Configuración.
- Factura ya en state='draft' intenta button_draft → no-op.

## Fuera de alcance

- Multi-moneda.
- Notas de crédito / débito.
- Retenciones ISLR (trabajo futuro).
- IGTF u otros impuestos múltiples por línea.
- Export diferenciado por `source`.
- Reportes adicionales específicos Odoo-first.
- Wizard de carga en lote (grid Excel) — solo factura a factura en v1.
- Conciliación bancaria automática (Odoo la provee nativamente con account.move).
- Concurrencia: race conditions entre usuarios que postean o regeneran simultáneamente. No cubierto en v1.
- Duplicados de factura: no hay constraint UNIQUE en (partner_id, invoice_number, invoice_date). El wizard muestra warning si detecta duplicado, sin bloquear.
- Race condition en creación de partner desde wizard: la constraint existente en res.partner.vat mitiga el caso.

## Criterios de finalización

- 122 tests pasando (107 base + 15 nuevos).
- Ruff limpio.
- Verificación manual end-to-end: crear factura compra por wizard → verificar `account.move` posteado + `vat.book.line` con `source='odoo_invoice'` y bases/IVAs correctos → export XLSX válido con totales cuadrados.

## Dudas abiertas

- [NECESITA ACLARACIÓN] Ninguna — todas las decisiones técnicas cerradas en la entrevista.
