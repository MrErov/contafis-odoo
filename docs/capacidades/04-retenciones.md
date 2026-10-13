# 04 - Retenciones

## Propósito
Calcular y generar comprobantes de retención (IVA 75%, ISLR 3%, IGTF 3%) sobre facturas de proveedores (`in_invoice`) para cumplimiento SENIAT. Vincula retención a factura y obligación.

## Alcance
**Incluye:**
- Modelo `l10n.retention`: secuencia `RET-YYYY-NNNN`, `partner_id`, `amount`, `currency_id` (default company currency), `date`, `invoice_id` (cascade), `state` (`draft`/`posted`/`cancel`)
- Extensión `account.move`: `retention_ids` (O2m), `retention_amount` (computed), `action_generate_retention()` (solo `in_invoice`)
- Cálculo automático por tipo impuesto en líneas de factura
- `l10n.ve.obligation`: `retention_id` (M2o) para vincular obligación pagada con retención

**No incluye:**
- Retenciones en facturas de venta (`out_invoice`) — no aplica en Venezuela
- Retenciones municipales (álcaldia) — reglas distintas por municipio
- Generación de TXT/archivo SENIAT (futuro)

## Modelos involucrados
- `l10n.retention`: campos monetarios, estados, secuencia
- `account.move`: `retention_ids`, `retention_amount`, `obligation_ids`, `action_generate_retention()`
- `l10n.ve.obligation`: `retention_id`, `payment_reference`, `payment_date`

## Reglas de negocio
1. **Aplicable solo a `in_invoice`** (facturas proveedor). `out_invoice`/`out_refund` ignorados.
2. **Porcentajes base** (configurables por tipo impuesto en líneas):
   - IVA: 75% del impuesto (base: `tax_group_id` = IVA)
   - ISLR: 3% del monto base (sujeto a retención según tabla SENIAT)
   - IGTF: 3% del monto total en divisas (operaciones en $)
3. **Acción**: `action_generate_retention()` crea `l10n.retention` en `draft`, suma líneas por impuesto, vincula a `invoice_id`.
4. **Moneda**: `currency_id` default = `company.currency_id` (VES). Conversión si factura en USD.
5. **Vinculación obligación**: Al pagar obligación con retención, `payment_reference` = nombre retención, `retention_id` = M2o.

## Criterios de aceptación (tests)
- `test_generate_retention`: factura `in_invoice` con IVA 16% → retención IVA 75% del impuesto; verifica monto, estado `draft`, vínculo `invoice_id`.

## Referencias
- Providencia SNAT/2019/000009 (retenciones IVA/ISLR)
- Gaceta Oficial 41.758 (IGTF 3%)
- docs/specs/01-calendario-seniat.md (vencimiento obligación pago retención)
- docs/specs/05-dashboard-reportes.md (compliance_score incluye obligaciones con retención)
