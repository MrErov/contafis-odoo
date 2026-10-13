# calcular-retencion-venezuela

## Cuándo usar este skill
Cuando el agente necesite:
- Calcular retenciones de IVA, ISLR o IGTF sobre una factura
- Validar tasas de retención según normativa venezolana
- Generar comprobantes de retención vinculados a account.move

## Reglas de cálculo
- **IVA (75%)**: sobre el monto del impuesto (amount_tax)
  - Ejemplo: factura con IVA 16% sobre base 1000 → amount_tax = 160 → retención = 120
- **ISLR (3%)**: sobre el subtotal (amount_untaxed)
  - Ejemplo: base 1000 → retención = 30
- **IGTF (3%)**: sobre pagos en divisas (si aplica)

## Modelos involucrados
- `l10n.retention`: registra el comprobante
- `account.move`: factura origen (solo move_type = 'in_invoice')
- `l10n.ve.obligation.type`: catálogo con tasas configurables
- `l10n.ve.retention.service`: servicio AbstractModel con la lógica encapsulada

## API del servicio (l10n.ve.retention.service)

### get_rate(tax_type, company=None)
Devuelve la tasa configurada en l10n.ve.obligation.type o el fallback.
- `tax_type`: 'iva' | 'islr' | 'igtf'
- `company`: res.company opcional para filtrar por compañía
- Fallback: iva=75%, islr=3%, igtf=3%

### calculate_amounts(move)
Devuelve dict con {islr: X, iva: Y, igtf: Z} para una factura in_invoice.
- Retorna dict vacío si move_type != 'in_invoice'
- Usa move.amount_untaxed para ISLR, move.amount_tax para IVA

### generate_retentions(move)
Crea registros en l10n.retention para una factura in_invoice.
- Idempotente: no duplica si ya existen retenciones para el mismo move
- Retorna recordset de l10n.retention creado (o vacío)
- Delegado desde account.move.action_generate_retention()

## Ejemplos de uso

### Desde account.move
```python
move.action_generate_retention()  # delega al servicio
```

### Desde otro modelo / API externa
```python
service = self.env['l10n.ve.retention.service']
rates = {t: service.get_rate(t) for t in ('iva', 'islr', 'igtf')}
amounts = service.calculate_amounts(move)
retentions = service.generate_retentions(move)
```

### Solo consultar tasas
```python
service = self.env['l10n.ve.retention.service']
iva_rate = service.get_rate('iva', company=move.company_id)
```

## Tests asociados
- tests/test_obligation.py::test_generate_retention
- tests/test_retention_service.py (nuevo)
- Ver docs/capacidades/04-retenciones.md para criterios de aceptación

## Referencias
- Providencia SNAT/2025/000091 (calendario SENIAT)
- docs/capacidades/04-retenciones.md
