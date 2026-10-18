# Limitaciones conocidas

Esta sección lista las funcionalidades que el módulo **todavía no implementa** o que funcionan parcialmente.

## Calendario SENIAT automático

**Estado:** implementado (spec 003, calendario 2026).

**Lo que funciona:**
- Cálculo del vencimiento por último dígito del RIF con las tablas oficiales 2026 (quincenas SPE y mensual no-SPE)
- Corrimiento automático a día hábil (fines de semana y feriados bancarios 2026)
- Generación automática mensual por cliente + botón manual "Generar obligaciones"
- Estimadas de ISLR (jun/sep/dic) y Retenciones de ISLR mensuales con vencimiento por último dígito del RIF (tablas de referencia editables)
- Bandeja "Próximos vencimientos" (30 días), alertas al contador y visibilidad por contador

**Limitaciones actuales:**
- Solo viene precargado el calendario 2026. Para años siguientes usar "Copiar a otro año" y revisar los días según la providencia vigente
- Los feriados bancarios 2026 vienen precargados; los de años futuros se cargan/editan a mano

**Alternativa manual:** el contador puede editar la fecha en Obligaciones por cliente (queda marcada como override y no se corrige sola).

**Referencia:** Providencia SNAT/2025/000091 (Gaceta Oficial N° 43.283 del 23-dic-2025).

## Cálculo automático de retenciones

**Estado:** registro manual únicamente.

**Qué falta:**
- Campos específicos para IVA / ISLR / IGTF en el modelo de retención
- Cálculo automático de 75%/100% del IVA según tipo de contribuyente
- Cálculo de ISLR según tabla del SENIAT
- Reporte mensual de retenciones al SENIAT

**Lo que sí funciona:** registro básico de la retención (nombre, partner, monto, fecha) y asociación al libro de compras (`retention_number`, `vat_retained`, `retention_direction`).

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

- Guard `country_id` en `_post()` para uso multi-país (actual: asume Venezuela)
- Migración de `_sql_constraints` a `models.Constraint` en modelos antiguos (Odoo 19 deprecó el primero; hecho en los modelos nuevos de spec 003)
- Extensión de tests para verificar permisos de admin (los tests actuales corren como root)
- Sub-fase 5 E2E: Planilla IVA + líneas del libro
- Sub-fase 6 E2E: Multi-company

## Cómo reportar una limitación nueva

Si al usar el sistema encuentra una funcionalidad faltante o un comportamiento inesperado, documentarlo con:

- Descripción del problema
- Captura de pantalla
- Pasos para reproducirlo
- Impacto en el trabajo diario
