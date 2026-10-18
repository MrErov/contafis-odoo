# Spec 004 - Tablas de ISLR (Estimadas/Anticipos y Retenciones) en el Calendario SENIAT 2026

Estado: aprobada (duda de días de referencia resuelta)

## Contexto y objetivo

La fase 003 dejó diferida la precarga de las tablas de ISLR del calendario SENIAT 2026 por no tener la Gaceta Oficial a mano, aunque la estructura del calendario ya las soporta (`est_islr` y `ret_islr`). Hoy el contador calcula a mano los 3 anticipos de estimadas y las retenciones mensuales de ISLR, con riesgo de multa por olvido. Esta fase carga ambas tablas —con fechas de referencia editables y documentadas como sujetas a verificación—, crea los tipos de obligación de ISLR y habilita su vencimiento por último dígito del RIF para todos los clientes (no solo SPE), para que la generación automática y las alertas existentes cubran este impuesto de punta a punta.

## Usuarios / actores

- **Contador de Cumplimiento VE** (grupo `l10n_ve_compliance_accountant`): revisa vencimientos ISLR de su cartera, declara y paga.
- **Administrador**: corrige las tablas de referencia cuando la Gaceta esté disponible.
- **Contacto del cliente**: recibe copia de alertas solo si el tipo lo configura.

## Historias de usuario

- HU-1: Como contador quiero que el sistema genere automáticamente las obligaciones de Estimadas de ISLR (3 anticipos al año) para no calcularlas a mano.
- HU-2: Como contador quiero que las Retenciones de ISLR se generen mes a mes con su vencimiento por RIF para declararlas a tiempo.
- HU-3: Como contador quiero que el vencimiento de ISLR se calcule por el calendario SENIAT según el último dígito del RIF aunque mi cliente no sea SPE.
- HU-4: Como administrador quiero corregir las fechas de referencia de las tablas ISLR desde la interfaz, sin que una actualización las pise.
- HU-5: Como contador quiero que, si el año no tiene tablas ISLR cargadas, el sistema me avise y no genere obligaciones con vencimientos sin respaldo.

## Requisitos funcionales (EARS)

- RF-1: EL SISTEMA mantiene las tablas est_islr (Estimadas) y ret_islr (Retenciones) con la estructura del calendario: día por mes y por último dígito del RIF, con corrimiento de mes configurable.
- RF-2: EL SISTEMA precarga las tablas 2026 con el patrón acordado: est_islr en junio, septiembre y diciembre sin corrimiento; ret_islr en los 12 meses con vencimiento el mes siguiente.
- RF-3: EL SISTEMA deja constancia en la precarga de que las fechas son de referencia sujetas a verificación con la Gaceta Oficial, y conserva las correcciones del contador ante actualizaciones del módulo.
- RF-4: EL SISTEMA precarga los tipos de obligación "Estimadas de ISLR" y "Retenciones de ISLR" (impuesto ISLR, categoría fiscal nacional, tabla SENIAT correspondiente), editables y no sobrescribibles por actualizaciones.
- RF-5: CUANDO la generación automática cubre junio, septiembre o diciembre, EL SISTEMA crea la obligación de Estimadas de ISLR de ese mes, sin duplicar.
- RF-6: CUANDO corre la generación automática y el cliente tiene el tipo de Retenciones, EL SISTEMA crea una obligación por cada mes de la ventana de generación, sin duplicar.
- RF-7: EL SISTEMA permite configurar en el tipo de obligación los meses del año en que se genera; sin configuración, usa la periodicidad del tipo.
- RF-8: CUANDO una obligación usa las tablas est_islr o ret_islr, EL SISTEMA calcula su vencimiento con el día de la tabla para el mes del período y el último dígito del RIF del cliente, aplicando el corrimiento de mes, sin depender de si el cliente es SPE.
- RF-9: EL SISTEMA aplica las tablas a.1/a.2 solo a clientes SPE; las tablas est_islr/ret_islr siguen siempre a su tipo de obligación asignado.
- RF-10: SI el año no tiene la tabla est_islr o ret_islr cargada, ENTONCES EL SISTEMA registra la alerta de calendario faltante y no genera las obligaciones de ese tipo.
- RF-11: SI la tabla existe pero no hay fila para el mes y dígito de RIF, ENTONCES EL SISTEMA deja el vencimiento vacío y la obligación visible para corrección.
- RF-12: CUANDO el vencimiento ISLR calculado cae en sábado, domingo o feriado bancario, EL SISTEMA lo corre al siguiente día hábil; la fecha fijada a mano no se corrige.
- RF-13: EL SISTEMA genera las alertas de vencimiento, vencida y falta de pago de las obligaciones ISLR con el flujo y canales ya configurados en el tipo.
- RF-14: CUANDO el administrador copia un año calendario, EL SISTEMA copia también las tablas est_islr y ret_islr del año origen.

## Requisitos no funcionales

- Tests como puerta: cada RF con test en verde; suite sin regresiones (≥193 tests, Odoo report `0 failed`).
- Trazabilidad del dato: las fechas de referencia quedan marcadas como pendientes de verificación con la Gaceta Oficial.
- Editabilidad: tablas y tipos editables por el contador/administrador; las precargas no pisan ediciones.
- Multi-cliente: las obligaciones siguen filtrando por empresa y por contador asignado (reglas de 003).
- Compatibilidad Odoo 19 y convenciones del repo.
- Rendimiento: la generación sigue dentro del tiempo estándar de cron con los dos tipos nuevos.

## Casos límite

- Año 2027 sin tablas ISLR: alerta de calendario faltante; no se generan esas obligaciones.
- Tabla presente con meses incompletos: la obligación de ese mes queda sin vencimiento hasta corregir la tabla.
- Cliente no-SPE con tipo ISLR: calcula por tabla (a diferencia del IVA quincenal, exclusivo SPE).
- Cliente sin tipos ISLR asignados: no se generan obligaciones ISLR.
- RIF sin dígitos: sin cálculo por tabla y aviso al contador (regla de 003 vigente).
- Re-ejecución del cron: no duplica (cliente + tipo + período + quincena).
- Edición manual del vencimiento: prevalece; no se corrige ni se corre a día hábil.
- Copia de calendario 2026→2027: replica est_islr y ret_islr; el destino no debe existir previamente (regla del wizard de 003).

## Fuera de alcance

- Verificación oficial contra la Gaceta: los valores cargados son de referencia; su reemplazo por los oficiales es posterior (editable por el contador).
- Montos, tasas, porcentajes de retención o cálculo de anticipos: esta fase solo vencimientos y alertas.
- Autoliquidación anual de ISLR, conciliación de estimadas y planilla de retenciones.
- Reglas por tipo de contribuyente distintas del calendario por RIF.
- Cambios estructurales al calendario o al wizard de copia.
- Calendarios de años distintos de 2026 y feriados bancarios futuros.

## Criterios de finalización

- Todos los RF con test en verde; suite completa sin regresiones (≥193, `0 failed`).
- Tablas 2026 visibles y editables en la interfaz: est_islr 30 filas (3 meses × 10 dígitos), ret_islr 120 filas (12 meses × 10 dígitos).
- Tipos "Estimadas de ISLR" y "Retenciones de ISLR" asignables a clientes.
- Demo manual: cliente con ambos tipos genera 3 estimadas y retenciones mensuales con vencimiento por RIF; re-ejecutar no duplica.
- Alerta de calendario faltante para un año sin tablas ISLR (test).
- Documentación actualizada: `docs/memory.md`, `docs/capacidades/01-calendario-seniat.md`, anexo de limitaciones.

## Dudas abiertas

- [RESUELTA] Patrón de días de referencia: día = último dígito del RIF + 10 (0 → día 10, 9 → día 19); estimadas en junio, septiembre y diciembre sin corrimiento; retenciones los 12 meses con corrimiento al mes siguiente. Marcado como referencia editable sujeta a verificación con la Gaceta Oficial.
