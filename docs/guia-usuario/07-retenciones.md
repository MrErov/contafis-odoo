# Retenciones

## ¿Qué es una retención?

En Venezuela, el comprador retiene un porcentaje del IVA o ISLR al proveedor y lo entera al SENIAT. El proveedor recibe un comprobante de retención.

<div class="note">

El módulo genera las retenciones automáticamente desde la factura de proveedor con el botón [Generar Retención] (IVA 75% e ISLR 3% por defecto, configurables en los tipos de obligación). El cálculo de IGTF está pendiente.

</div>

## Registrar una retención

El modelo `l10n.retention` guarda las retenciones (creadas automáticamente desde la factura o registradas a mano):

- **Nombre:** identificador del comprobante (secuencia automática)
- **Contacto:** partner retenido
- **Monto:** monto retenido
- **Moneda:** por defecto VES
- **Fecha:** fecha de emisión
- **Factura:** account.move asociada (opcional)
- **Estado:** Borrador / Publicado / Cancelado

## Ver retenciones registradas

Las retenciones se consultan en la pestaña *Retenciones* de la factura de proveedor. El módulo no tiene un menú propio de retenciones.

## Cómo se relaciona con el libro

Los campos `retention_number`, `vat_retained` y `retention_direction` de `l10n.ve.vat.book.line` SÍ registran la retención que el comprador aplica. Ese es el uso principal hoy.

## Limitaciones actuales

- No hay cálculo de IGTF
- No hay distinción IVA/ISLR/IGTF en el modelo
- No hay reporte específico al SENIAT
- No hay action/menú dedicado

## Siguiente paso

> Continúa con [Calendario SENIAT](./08-calendario-seniat.md).
