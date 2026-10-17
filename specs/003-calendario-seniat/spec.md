# Spec 003 - Calendario SENIAT: vencimientos automáticos por último dígito del RIF

Estado: aprobada (dudas resueltas el 2026-10-17)

## Contexto y objetivo

El contador gestiona el cumplimiento fiscal de varias empresas y hoy debe crear a mano cada obligación y calcular mentalmente (o con tablas externas) la fecha límite del IVA, IGTF, retenciones y demás impuestos SENIAT según el último dígito del RIF. La Providencia Administrativa SNAT/2025/000091 (Gaceta Oficial N° 43.283 del 23/12/2025) fija el calendario 2026 para Sujetos Pasivos Especiales (SPE): el IVA pasa a ser quincenal (2 períodos por mes) y cada dígito de RIF tiene su día de declaración por impuesto. Olvidar una fecha = multa. El objetivo es que el sistema calcule y genere todas las obligaciones automáticamente, avise al contador asignado antes del vencimiento y corra al día hábil bancario siguiente cualquier fecha que caiga en fin de semana o feriado bancario, eliminando la carga manual y el riesgo de multas.

## Usuarios / actores

- **Contador de Cumplimiento VE** (grupo `l10n_ve_compliance_accountant`): usuario principal; revisa la bandeja de vencimientos de sus clientes asignados y declara/paga a tiempo.
- **Administrador**: carga o corrige el calendario y los feriados bancarios de años futuros (ej. 2027) desde Odoo sin tocar código.
- **Contacto del cliente** (`partner_id`): recibe copia de la alerta solo si se configura.

## Historias de usuario

- HU-1: Como contador quiero que el sistema genere automáticamente las obligaciones de cada período para cada cliente, para no crearlas a mano ni olvidar ninguna.
- HU-2: Como contador quiero ver en mi bandeja solo los vencimientos de los clientes que tengo asignados, para enfocarme en mi cartera.
- HU-3: Como contador quiero recibir un aviso por email/WhatsApp días antes del vencimiento, para declarar y pagar a tiempo.
- HU-4: Como administrador quiero cargar o corregir el calendario de un año nuevo desde Odoo sin tocar código, para operar cuando SENIAT publique la próxima providencia.
- HU-5: Como contador quiero marcar si un cliente es SPE, para que el sistema aplique el calendario por RIF solo a quien corresponde.
- HU-6: Como contador quiero que, si un vencimiento cae en fin de semana o feriado bancario, el sistema lo corra al siguiente día hábil bancario, para no arriesgar una multa por pagar en día inhábil.

## Requisitos funcionales (EARS)

- RF-1: EL SISTEMA mantiene un calendario oficial por año con las fechas de vencimiento de cada impuesto según el último dígito del RIF (0–9).
- RF-2: EL SISTEMA precarga el calendario 2026 de la Providencia SNAT/2025/000091: tablas a.1 y a.2 (IVA, anticipos de ISLR, IGTF y retenciones de IVA). Las tablas por dígito de estimadas y retenciones de ISLR quedan diferidas a una fase posterior; la estructura del calendario (`code` + `month_offset`) ya las soporta.
- RF-3: CUANDO el administrador o contador edita los datos del calendario, EL SISTEMA conserva el cambio sin que una actualización del módulo lo sobrescriba.
- RF-4: SI un cliente SPE tiene obligaciones que requieren calendario y el año no está cargado, ENTONCES EL SISTEMA registra una alerta de calendario faltante para su contador y no genera esas obligaciones.
- RF-5: EL SISTEMA permite marcar por cliente si es Sujeto Pasivo Especial (`is_spe`).
- RF-6: SI el cliente es SPE, ENTONCES EL SISTEMA calcula el vencimiento de sus obligaciones SENIAT según el calendario y el último dígito de su RIF.
- RF-7: SI el cliente no es SPE, ENTONCES EL SISTEMA no aplica el calendario por RIF y calcula el vencimiento con la regla general del día 15 del mes siguiente al período, o usa la fecha manual si el contador la fija.
- RF-8: SI el RIF del cliente no contiene dígitos, ENTONCES EL SISTEMA no calcula vencimiento por calendario y avisa al contador.
- RF-9: CUANDO el cliente es SPE y el impuesto es IVA, EL SISTEMA crea una obligación por cada quincena del mes; cada obligación identifica su quincena (`quincena` = `q1`/`q2`) y conserva el período en formato `MM/YYYY`.
- RF-10: CUANDO se calcula el vencimiento de la primera quincena de IVA, EL SISTEMA usa el día de la tabla a.1 del mes del período, dentro del mismo mes.
- RF-11: CUANDO se calcula el vencimiento de la segunda quincena de IVA, EL SISTEMA usa el día de la tabla a.2 del mes del período y lo fija en el mes siguiente.
- RF-12: CUANDO corre la generación automática, EL SISTEMA crea las obligaciones del período para cada cliente según los tipos de obligación que tenga configurados; las obligaciones no quincenales usan `quincena` = `monthly`.
- RF-13: SI ya existe una obligación del mismo cliente, tipo, período y quincena, ENTONCES EL SISTEMA no la duplica.
- RF-14: CUANDO faltan `alert_days_before` días para el vencimiento de una obligación pendiente, EL SISTEMA envía la alerta al contador asignado del cliente (`accountant_id`).
- RF-15: SI se activa la copia al cliente en el tipo de obligación, ENTONCES EL SISTEMA agrega al contacto del cliente como destinatario adicional.
- RF-16: EL SISTEMA envía el email de alerta usando la plantilla existente (hoy definida pero no conectada) y mantiene el link de WhatsApp.
- RF-17: MIENTRAS un usuario pertenece al grupo Contador de Cumplimiento VE, EL SISTEMA le muestra solo los clientes, obligaciones, documentos y alertas de los clientes donde figura como contador asignado; los clientes sin contador asignado solo son visibles para administradores.
- RF-18: EL SISTEMA ofrece una bandeja de próximos vencimientos por cliente, ordenada por fecha, con filtro por defecto de los próximos 30 días.
- RF-19: EL SISTEMA mantiene un catálogo de días feriados bancarios por año, editable en la interfaz, con precarga de los feriados bancarios 2026.
- RF-20: CUANDO la fecha de vencimiento calculada (calendario por RIF o regla del día 15 no-SPE) cae en sábado, domingo o feriado bancario cargado, EL SISTEMA corre la fecha al siguiente día hábil bancario; las fechas fijadas manualmente por el contador no se corrigen.

## Requisitos no funcionales

- Tests como puerta: cada RF con test en verde; la suite completa no baja de 121 tests ni deja regresiones (Odoo report `0 failed`).
- Rendimiento: la generación automática procesa todos los clientes y tipos en lotes sin exceder el tiempo estándar de un cron.
- Seguridad: los permisos usan el grupo existente y reglas de registro por `accountant_id`; el administrador ve todo.
- Compatibilidad Odoo 19: vistas y campos siguen las convenciones del repo (`<list>`, `invisible=`, `@api.depends` explícito).
- Formato de período estable: el período de obligaciones conserva `MM/YYYY`; lo consumen el libro de compras/ventas y la Planilla 99030. La quincena se identifica en un campo aparte.
- Trazabilidad: las obligaciones generadas y las fechas editadas quedan auditables (campos de creación/modificación de Odoo).
- Upgrades seguros: los datos precargados (calendario y feriados bancarios) usan `noupdate` para no pisar ediciones del contador.

## Casos límite

- Año sin calendario cargado (ej. 2027 antes de publicar providencia): se registra alerta de calendario faltante y no se generan esas obligaciones.
- RIF vacío o sin dígitos: sin cálculo por calendario.
- Fecha calculada que cae en sábado, domingo o feriado bancario: se corre al siguiente día hábil bancario.
- Año sin feriados bancarios cargados: el corrimiento solo evita fines de semana (degradación segura, sin error).
- Fecha fijada manualmente por el contador: no se corrige automáticamente.
- Re-ejecución de la generación automática: no debe duplicar obligaciones.
- Cliente SPE sin contador asignado: la alerta queda sin destinatario y visible solo para administradores.
- Cliente que deja de ser SPE: las obligaciones ya generadas se conservan; las nuevas usan el nuevo valor.
- Actualización del módulo tras edición manual del calendario: los cambios del contador se conservan.
- Cliente nuevo a mitad de año: la generación de respaldo cubre el período en curso.

## Fuera de alcance

- Parafiscales (IVSS, INCES, BANAVIH) y municipales: siguen con sus reglas actuales.
- Reglas específicas de no-SPE por impuesto (agentes de retención no-SPE); esta fase define solo la regla general del día 15.
- Tablas por dígito de estimadas y retenciones de ISLR (diferidas a una fase posterior; la estructura del calendario ya las soporta).
- WhatsApp Business API: sigue el link manual `wa.me`.
- Flujo de aprobación/confirmación de obligaciones generadas: el contador revisa, no aprueba.
- Importación del calendario o de feriados desde Excel: esta fase edita registros en la interfaz de Odoo.
- Autoliquidación anual de ISLR, juegos de envite y azar, grandes patrimonios.

## Criterios de finalización

- Todos los RF con test en verde (suite completa sin regresiones, ≥121 tests).
- Calendario 2026 cargado y verificable en la interfaz (tablas a.1/a.2).
- Feriados bancarios 2026 cargados; un vencimiento en fin de semana o feriado se corre a día hábil (test).
- Generación automática crea las 2 quincenas de IVA de un cliente SPE y el resto de sus tipos; re-ejecutar no duplica.
- Alerta de email enviada al contador asignado; contacto del cliente solo si se configura.
- Bandeja de próximos vencimientos filtrada por contador (regla de registro activa); clientes sin contador visibles solo para administradores.
- Demo manual: administrador carga el año 2027 copiando/creando la tabla; contador ve su bandeja.
- Documentación actualizada: `docs/capacidades/01-calendario-seniat.md`, `docs/guia-usuario/anexo-limitaciones.md`, `docs/memory.md`.

## Decisiones resueltas (2026-10-17)

- Tablas ISLR: solo a.1/a.2 se cargan en esta fase; las tablas por dígito de estimadas/retenciones de ISLR se difieren y se cargarán cuando se verifique la fuente oficial (Gaceta 43.283). La arquitectura ya las soporta.
- Feriados bancarios: el vencimiento se corre al siguiente día hábil bancario, con catálogo editable por año y precarga 2026 (fuente oficial a verificar al cargar los datos, incluyendo los 8 cruces detectados).
- Formato quincenal: campo Selection `quincena` (`monthly`, `q1`, `q2`) en columna separada; el período permanece `MM/YYYY` porque el libro de compras/ventas y la Planilla 99030 dependen de ese formato.
- Cliente sin `accountant_id`: visible y gestionable solo por administradores; esto fuerza el flujo "el administrador recibe al cliente y lo asigna a un contador".
