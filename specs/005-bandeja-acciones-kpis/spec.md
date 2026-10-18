# Spec 005 - Bandeja de vencimientos accionable y análisis (KPIs)

Estado: propuesta (pendiente de revisión del usuario)

## Contexto y objetivo

La bandeja **"Próximos vencimientos"** (`action_l10n_ve_obligation_due_soon`, dominio
`state in (pending, overdue)` + 30 días) es hoy solo de lectura: para marcar una
obligación como pagada hay que abrir el formulario y cambiar el estado, sin que se
registre automáticamente la fecha de pago, y no existe forma de disparar una alerta
a demanda (el link `wa.me` solo se genera cuando el cron crea la alerta). Tampoco
existe un menú de análisis: solo el kanban por cliente, sin gráficos ni pivotes.
Esta fase convierte la bandeja en el punto de trabajo del contador (marcar pago,
reabrir, alertar) y agrega vistas de análisis nativas de obligaciones y alertas.

## Usuarios / actores

- **Contador** (`l10n_ve_compliance_accountant`): opera la bandeja diaria de su cartera.
- **Administrador**: supervisa mediante las vistas de análisis.
- **Contacto del cliente**: sigue recibiendo copia de alertas según configuración del tipo.

## Historias de usuario

- HU-1: Como contador quiero **marcar una obligación como pagada** desde la bandeja,
  registrando fecha, referencia y comprobante, sin abrir el formulario completo.
- HU-2: Como contador quiero **reabrir** una obligación marcada por error.
- HU-3: Como contador quiero **crear/enviar la alerta** (correo o WhatsApp) de una
  obligación a demanda desde la bandeja y el formulario.
- HU-4: Como contador/administrador quiero un menú **"Análisis"** con gráficos y
  tablas dinámicas de obligaciones y alertas.

## Requisitos funcionales (EARS)

- RF-1: CUANDO el contador pulsa "Registrar pago" en una obligación pendiente o
  vencida, EL SISTEMA abre un wizard con fecha (hoy por defecto), referencia y
  comprobante; al confirmar la obligación queda `paid` con `payment_date`,
  `payment_reference` y `payment_attachment` registrados.
- RF-2: EL SISTEMA ofrece acción masiva "Marcar pagadas (hoy)" sobre la selección de
  la bandeja, aplicando solo a pendientes/vencidas y reportando cuántas quedaron fuera.
- RF-3: CUANDO el contador reabre una obligación pagada, EL SISTEMA la deja `pending`,
  o `overdue` si su vencimiento ya pasó, limpia fecha y referencia de pago y conserva
  el comprobante adjunto.
- RF-4: CUANDO el contador pulsa "Crear alerta", EL SISTEMA crea la alerta por el flujo
  del tipo de obligación (destinatario contador asignado, canal configurado, copia al
  cliente si aplica) e inyecta el link `wa.me` cuando el canal lo amerita.
- RF-5: SI ya existe una alerta `pending`/`sent` del mismo tipo para esa obligación,
  ENTONCES EL SISTEMA no duplica y avisa al usuario que ya fue enviada.
- RF-6: EL SISTEMA registra el origen manual de las alertas creadas a demanda con el
  valor `manual` en `alert_type`, visible en el formulario de la alerta.
- RF-7: EL SISTEMA expone menú "Análisis" con vista gráfica y pivote de obligaciones
  (medidas: cantidad y suma de `amount`; agrupaciones: estado, tipo, cliente, período,
  mes de vencimiento) y de alertas (estado, canal, tipo).
- RF-8: los botones respetan estado y permisos: ocultos en `cancelled` y sin acciones
  de escritura para usuarios de solo lectura; el backend valida igualmente.

## Requisitos no funcionales

- Tests como puerta: cada RF con test en verde; suite sin regresiones (≥222, `0 failed`).
- Convenciones Odoo 19: `<list>`, `invisible=`, sin `attrs`/`states`.
- Multi-cliente: las acciones respetan las record rules existentes por contador.
- Rendimiento: las acciones son de modelo (sin SQL nuevo); las vistas de análisis usan
  `read_group` nativo con `_client_type_period_idx` existente.

## Casos límite

- Obligación `cancelled`: sin botones de pago/reabrir.
- Pago tardío (vencida → pagada): permitido; `due_date` se conserva.
- Reabrir con vencimiento pasado: pasa directo a `overdue`.
- Alerta manual sin contador asignado: destinatario fallback del flujo existente;
  sin teléfono → alerta sin link (comportamiento documentado de `alert.py`).
- Selección mixta en acción masiva: solo procesa elegibles y reporta el resto.
- Registro de pago no crea ni modifica `account.move` (no hay asiento contable).

## Fuera de alcance

- Pagos reales (`account.payment`), conciliación bancaria o asientos contables.
- WhatsApp Business API (se mantiene `wa.me` click-to-chat).
- Dashboard OWL a medida o tarjetas KPI personalizadas (se usan vistas nativas).
- Cambios al cron de generación o a la lógica automática de alertas.
- Notificaciones push o recordatorios adicionales a los del cron.

## Criterios de finalización

- `0 failed, 0 error(s) of N` con N = 222 + tests nuevos (T1–T4).
- Verificación visual en navegador: bandeja con botones por fila y menú "Análisis"
  con gráfico y pivote (capturas en el reporte de la sub-tarea).
- Docs actualizadas: `docs/capacidades/02-gestion-alertas.md`,
  `docs/capacidades/05-dashboard-reportes.md`, `SPEC.md`.
- Un commit por tarea de `tasks.md`, verificado contra `docs/constitution.md`.
