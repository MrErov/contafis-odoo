# Limitaciones conocidas

Esta sección lista las funcionalidades que el módulo **todavía no implementa** o que funcionan parcialmente.

## Calendario SENIAT e ISLR

**Estado:** implementado (specs 003 y 004). Ver [Calendario SENIAT](./08-calendario-seniat.md) para el uso paso a paso.

**Datos de referencia precargados:**
- Tablas 2026: a.1 y a.2 (quincenas de SPE), est_islr (estimadas de ISLR, jun/sep/dic) y ret_islr (retenciones de ISLR, vence el mes siguiente)
- Feriados bancarios 2026 (corrimiento automático al siguiente día hábil)

**Para años posteriores a 2026:** use el botón [Copiar a otro año] del Calendario SENIAT y revise los días y los feriados contra la providencia vigente.

**Corrección manual:** el contador puede editar la fecha en Obligaciones por cliente (queda marcada como override y no se corrige sola).

**Referencia:** Providencia SNAT/2025/000091 (Gaceta Oficial N° 43.283 del 23-dic-2025).

## Cálculo automático de retenciones

**Estado:** implementado para IVA e ISLR (por defecto 75% y 3%).

**Lo que funciona:** el botón [Generar Retención] de las facturas de proveedor (`in_invoice`) crea las retenciones de IVA e ISLR con las tasas configuradas en los tipos de obligación (respaldo: 75% y 3%). La pestaña *Retenciones* de la factura las lista y el libro de compras registra `retention_number`, `vat_retained` y `retention_direction`.

**Qué falta:**
- Cálculo de IGTF (hoy no se genera)
- Reporte/archivo mensual de retenciones al SENIAT
- Menú dedicado de retenciones (hoy se consultan desde la factura)

## Aislamiento por empresa (multi-cliente)

**Estado:** implementado para clientes, obligaciones, documentos y alertas.

**Lo que funciona:** los datos de cada cliente (obligaciones, documentos, alertas) se aíslan automáticamente por su empresa; un contador solo ve los clientes que tiene asignados en el campo *Contador*.

**Qué falta:** las **Planillas de IVA** y las líneas del **Libro de Compras/Ventas** aún no cuentan con esta regla de aislamiento. Mientras se completa, revise esas pantallas con una sola empresa activa si atiende clientes en paralelo.

## API de WhatsApp

**Estado:** envío manual mediante `wa.me`.

**Qué falta:**
- Integración con WhatsApp Business API (Meta) o Twilio
- Envío automático de alertas sin intervención del usuario

**Lo que sí funciona:** generación de enlaces `wa.me` con mensaje pre-armado.

## Respaldo automático de base de datos

**Estado:** NO implementado (fuera del scope del módulo).

**Qué falta:**
- Programación de `pg_dump` desde Odoo
- Rotación de respaldos
- Almacenamiento externo (S3, etc.)

**Alternativa:** usar el módulo de respaldos de Odoo o un cron externo con `pg_dump`.

## Otros pendientes

- Extensión de tests para verificar permisos de admin (los tests actuales corren como root)
- Asignación automática de contador: los clientes nuevos no se asignan solos; defina el campo **Contador** (si no, solo el administrador los ve)

## Cómo reportar una limitación nueva

Si al usar el sistema encuentra una funcionalidad faltante o un comportamiento inesperado, documentarlo con:

- Descripción del problema
- Captura de pantalla
- Pasos para reproducirlo
- Impacto en el trabajo diario
