# Spec 011 - Conciliación ISLR

Estado: aprobada (dudas resueltas el 2026-10-19)

## Contexto y objetivo
Cada año el contador arma la conciliación fiscal de rentas (ISLR) de cada cliente en Excel: parte de los datos de contabilidad, aplica ajustes fiscales (no gravables / no deducibles) citando su precepto legal (LISLR), limita sueldos directivos al 10% de los ingresos brutos y obtiene renta bruta, utilidad neta y monto a pagar. Hoy ese trabajo queda fuera del sistema. Esta iteración incorpora la conciliación anual al módulo: se importa la hoja del archivo del contador, el sistema recalcula los totales y advierte descuadres, y la conciliación queda consultable, editable y exportable por cliente y año.

## Usuarios / actores
Contador (gestiona varios clientes desde una sola instancia), asistente/revisor contable.

## Historias de usuario
- HU-1: Como contador quiero importar la hoja "Conciliación Fiscal" del Excel del cliente para no retipear la conciliación del año.
- HU-2: Como contador quiero revisar y editar cualquier rubro dentro del sistema (con trazabilidad) para corregir sin volver al Excel.
- HU-3: Como contador quiero que el sistema recalcule los totales y me advierta descuadres para detectar errores de la plantilla.
- HU-4: Como contador quiero generar el PDF de la conciliación validada para el expediente del cliente.

## Requisitos funcionales (EARS)
- RF-1: CUANDO el contador importa un Excel, EL SISTEMA busca la hoja "Conciliación Fiscal" (sin distinguir mayúsculas/minúsculas) y crea la conciliación del cliente y del año fiscal detectados en la hoja; SI la hoja no existe o el archivo está corrupto, ENTONCES EL SISTEMA aborta con un error claro.
- RF-2: SI ya existe una conciliación del mismo cliente y año, ENTONCES EL SISTEMA pide confirmación explícita y, al confirmar, reemplaza los rubros existentes por los de la hoja; SI el RIF de la hoja no coincide con el del registro existente, ENTONCES la confirmación lo advierte.
- RF-3: EL SISTEMA identifica al cliente por RIF sanitizado (sin guiones ni puntos, en mayúsculas) tanto en la hoja como en los clientes registrados; SI el RIF no corresponde a ningún cliente, ENTONCES EL SISTEMA aborta la importación (modo estricto: el contador debe crear el cliente primero); SI el RIF coincide con clientes de más de una compañía, ENTONCES EL SISTEMA pide seleccionar la compañía antes de importar.
- RF-4: EL SISTEMA importa únicamente el bloque principal de la hoja (filas 12 a 46, columnas B a F): rubros de INGRESOS (ventas), COSTOS DE VENTA (inventario inicial, compras de mercancías, inventario final) y DEDUCCIONES (sueldos directivos, tributos pagados, arrendamientos de inmuebles, otros gastos, gastos de representación, gastos generales, gastos de transporte y demás rubros etiquetados), cada uno con importe de contabilidad, importe fiscal, importe no gravable/no deducible y precepto legal; las filas de totales (TOTAL INGRESOS GLOBALES, MERCANCIA DISPONIBLE, TOTAL COSTO VTA., RENTA BRUTA, TOTAL DEDUCCIONES, UTILIDAD NETA) no se importan como líneas.
- RF-5: CUANDO una etiqueta de rubro no se reconoce, EL SISTEMA la importa como rubro adicional y la reporta en las advertencias (no se pierde información).
- RF-6: CUANDO el contador edita cualquier importe o etiqueta, EL SISTEMA registra quién y cuándo (trazabilidad) y guarda sin bloquear.
- RF-7: EL SISTEMA recalcula, para la columna contabilidad y para la columna fiscal: mercancía disponible = inventario inicial + compras; total costo de venta = mercancía disponible − inventario final; renta bruta = total ingresos − costo de venta; total deducciones = suma de deducciones; utilidad neta = renta bruta − total deducciones.
- RF-8: SI un total importado de la hoja difiere del recalculado, ENTONCES EL SISTEMA lo muestra como advertencia de descuadre sin bloquear.
- RF-9: MIENTRAS un rubro no cumpla contabilidad = fiscal + no gravable/no deducible (con tolerancia de redondeo), EL SISTEMA lo advierte sin bloquear.
- RF-10: SI la suma de los importes fiscales de los rubros de INGRESOS es mayor que cero y el importe fiscal de sueldos directivos supera el 10% de esa suma, ENTONCES EL SISTEMA lo advierte como tope excedido sin bloquear; SI la suma es cero, ENTONCES EL SISTEMA omite la validación del tope y lo advierte.
- RF-11: EL SISTEMA calcula el monto a pagar aplicando la tarifa del 34% (personas jurídicas, Art. 52 LISLR) sobre la utilidad neta fiscal y lo compara con el monto informado en la hoja (celda F45); SI difieren, ENTONCES EL SISTEMA lo advierte sin bloquear y conserva el valor informado como dato editable.
- RF-12: CUANDO el contador valida la conciliación, EL SISTEMA genera y adjunta el PDF con el layout del bloque principal (rubros con sus tres columnas, preceptos legales, totales y advertencias); CUANDO se edita una conciliación validada, EL SISTEMA la devuelve a borrador y elimina el PDF adjunto (debe revalidarse para regenerarlo).
- RF-13: EL SISTEMA registra y muestra las conciliaciones por cliente y año fiscal, con vistas de lista y formulario filtrables por año y estado.
- RF-14: MIENTRAS la conciliación está en borrador, EL SISTEMA permite edición libre; validar no bloquea ediciones posteriores (toda edición queda trazada y revierte a borrador según RF-12).
- RF-15: SI un rubro aparece duplicado en la hoja (misma etiqueta), EL SISTEMA suma sus importes en una sola línea y lo advierte.
- RF-16: SI una celda de importe del bloque principal contiene texto (p. ej. "SIN ACTIVIDAD"), ENTONCES EL SISTEMA importa 0 y lo advierte.
- RF-17: EL SISTEMA muestra las advertencias en el formulario (bloque HTML de alertas), las guarda en el registro y las recalcula en cada guardado o edición.

## Requisitos no funcionales
- Fixture real versionado (`CONCILIACION_FINANCIERA_Y_FISCAL_DEMO_2026.xlsx`) con test de integración que importa la hoja demo y verifica rubros, totales recalculados y advertencias (los descuadres del fixture son esperados).
- Solo se leen valores: sin dependencia de macros ni fórmulas del Excel.
- Multi-cliente: todo registro y consulta filtrado por compañía (constitución #3).
- Concurrencia: se usa el bloqueo transaccional estándar de Odoo (SELECT FOR UPDATE / lock de transacción), sin mecanismos propios.
- UI y textos en español; campos y métodos en inglés (constitución #6).
- Suite backend completa en verde y CI 3/3 antes de commitear (constitución #4/#5).

## Casos límite
- Archivo corrupto o sin la hoja "Conciliación Fiscal" → UserError con mensaje claro (RF-1).
- Cliente sin RIF registrado o RIF inexistente → abortar; el contador crea el cliente primero (RF-3).
- RIF presente en clientes de dos compañías → el sistema pide seleccionar la compañía, no adivina (RF-3).
- Rubros deducibles sin importes (ley de trabajo, reparaciones, internet, depreciación) → quedan en cero y editables.
- Filas sin etiqueta o vacías → se ignoran sin error.
- Totales del Excel descuadrados (el fixture suma parcialmente el total de deducciones de contabilidad) → advertencia, no bloqueo (RF-8).
- Reimportación del mismo archivo → reemplaza, no duplica (RF-2).
- RIF distinto al reimportar sobre un registro existente → advertencia y confirmación explícita para sobrescribir (RF-2).
- Bloques laterales con datos de años anteriores (2023) → ignorados; solo se lee el bloque principal (RF-4).
- Importes negativos o vacíos → se importan tal cual y quedan editables.
- Sueldos con base de ingresos fiscales = 0 → se omite el tope 10% y se advierte (RF-10).

## Fuera de alcance
- Hojas de trabajo mensuales y resumen IVA de la hoja (bloques laterales, columnas H en adelante).
- Cálculo automático de la conciliación desde movimientos contables de Odoo.
- Sugerir el ajuste del tope 10% (solo se advierte; el ajuste lo decide el contador).
- Tarifa progresiva por unidades tributarias; se usa la tarifa plana del 34% (RF-11).
- Vínculo con la obligación anual "Declaración de Rentas" del calendario y descuento de retenciones ISLR.
- Envío al SENIAT.
- Versionado/historial: un único registro por cliente y año.
- Modo laxo o creación automática de clientes al importar (esta iteración es estricta).

## Criterios de finalización
- Todos los RF con test en verde, incluida la importación del fixture real.
- Suite completa verde (258 + nuevos) y CI 3/3.
- Demo manual: importar el fixture real, revisar rubros/totales/advertencias, validar y generar el PDF.

## Dudas abiertas
Sin dudas abiertas (resueltas el 2026-10-19).
