# Retenciones

## ¿Qué es una retención?

En Venezuela, el comprador retiene un porcentaje del IVA o ISLR al proveedor y lo entera al SENIAT. El proveedor recibe un comprobante de retención.

<div class="note">

El módulo actual implementa un registro básico de retenciones (nombre, contacto, monto, factura, estado). El cálculo automático de IVA (75%/100%), ISLR e IGTF está en el roadmap.

</div>

## Registrar una retención

El modelo `l10n.retention` permite registrar retenciones manualmente:

- **Nombre:** identificador del comprobante (secuencia automática)
- **Contacto:** partner retenido
- **Monto:** monto retenido
- **Moneda:** por defecto VES
- **Fecha:** fecha de emisión
- **Factura:** account.move asociada (opcional)
- **Estado:** Borrador / Publicado / Cancelado

<!-- VERIFICAR: no existe action ni menú dedicado para l10n.retention en views/ -->

## Ver retenciones registradas

Actualmente no existe una vista lista dedicada para retenciones. Se accede desde Contabilidad → Retenciones cuando la funcionalidad esté completa.

## Cómo se relaciona con el libro

Los campos `retention_number`, `vat_retained` y `retention_direction` de `l10n.ve.vat.book.line` SÍ registran la retención que el comprador aplica. Ese es el uso principal hoy.

## Limitaciones actuales

- No hay cálculo automático de IVA retenido
- No hay distinción IVA/ISLR/IGTF en el modelo
- No hay reporte específico al SENIAT
- No hay action/menú dedicado

## Siguiente paso

> Continúa con [Calendario SENIAT](./08-calendario-seniat.md).
