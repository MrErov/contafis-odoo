# ContaFis — Plan de Negocio y Estrategia SaaS

**Versión:** 1.0 · **Fecha:** Noviembre 2026 · **Autor:** Eurick Ospino (MrErov)

---

## 1. Resumen ejecutivo

ContaFis es una plataforma de cumplimiento fiscal y parafiscal para Venezuela,
construida como módulo de Odoo 19 y potenciada por un asistente de IA. El
producto resuelve un problema concreto: un contador que lleva varias empresas
hoy trabaja con hojas de cálculo dispersas, recordatorios manuales y
digitalización de facturas a mano.

La propuesta comercial es un **SaaS multi-tenant con cobro por cantidad de
empresas gestionadas**, no por usuario. Esto alinea el precio con el valor
real que recibe el cliente (más compañías administradas) y con el costo
variable real del servicio (consumo de API de IA y almacenamiento por
compañía).

| Elemento | Definición |
|---|---|
| Producto | ContaFis (Odoo 19 + ContaFis AI Assistant) |
| Cliente | Contadores independientes y pequeñas firmas en Venezuela |
| Precio de entrada | $19 / mes (hasta 3 empresas) |
| Diferenciador | Digitalización de facturas con IA + operación multi-compañía nativa |
| Modelo | Suscripción mensual + Setup Fee único |
| Infraestructura | AWS Lightsail (~$25 / mes) + NVIDIA NIM por consumo |

---

## 2. Propuesta de valor

### 2.1 Automatización con IA

La digitalización de facturas convierte una foto o un PDF en un registro
contable estructurado: RIF, fecha de emisión, base imponible, IVA, IGTF, líneas
de detalle y totales. El motor de visión procesa el documento en segundos y
devuelve datos normalizados listos para el libro de compras.

Impacto para el cliente:

- **Menos tiempo por factura.** La carga manual de una factura de 6 líneas
  ronda los 3–5 minutos; con digitalización asistida baja a menos de un minuto,
  incluyendo revisión humana.
- **Menos errores de transcripción.** El sistema normaliza moneda (`VEF` →
  `VES`), fechas y RIF, y emite advertencias cuando el RIF no valida.
- **Trazabilidad.** Cada documento conserva la evidencia y el resultado de la
  extracción, lo que facilita auditorías y reparos.

### 2.2 Gestión multi-compañía

ContaFis está diseñado desde el origen para un contador que administra varias
empresas en una sola instancia:

- Calendario SENIAT por compañía, con vencimientos diferenciados por terminación
  de RIF.
- Retenciones de ISLR, IVA e IGTF con numeración y comprobantes por empresa.
- Cartelera fiscal de documentos con evidencias fotográficas.
- Libro de compras y ventas con importación desde Excel.
- Roles y permisos separados: el contador ve todas sus empresas, el cliente ve
  solo la suya.

### 2.3 Cumplimiento local, no un ERP genérico

El producto no compite con Odoo como ERP: compite con el "Excel + carpetas +
recordatorios en el teléfono" del contador venezolano. Se apoya en Odoo para la
contabilidad y agrega la capa que Odoo no trae de fábrica para Venezuela:
calendario SENIAT, retenciones locales, cartelera y evidencias.

---

## 3. Público objetivo

### 3.1 Segmentos

| Segmento | Perfil | Empresas gestionadas | Plan natural |
|---|---|---|---|
| Contador independiente | Profesional solo, cartera pequeña, alta sensibilidad al precio | 1–3 | Independiente |
| Firma pequeña | 2–5 contadores, cartera en crecimiento | 4–10 | Profesional |
| Estudio mediano | Estructura con auxiliares y revisores | 10–30 | Estudio |
| Aliado / franquicia | Consultoras, gremios, distribuidores | 30+ | Personalizado |

### 3.2 Geografía y contexto

- **Mercado primario:** Venezuela (Caracas, Maracaibo, Valencia, Barquisimeto).
- **Idioma y normativa:** español, SENIAT, ISLR, IVA, IGTF, INCE, IVSS.
- **Realidad operativa:** inflación y dolarización parcial, por lo que el precio
  se expresa en USD y el pago se cobra en divisas o criptoestables.
- **Canal natural:** gremios de contadores públicos y colegios profesionales,
  donde la recomendación entre colegas tiene más peso que la publicidad.

### 3.3 Perfil del cliente ideal

Contador con 5 a 20 años de experiencia, entre 5 y 15 clientes PYMES activos,
que hoy factura honorarios mensuales por empresa y pierde horas en tareas
repetitivas. No busca "un software más": busca **reducir horas no facturables**
y **no incurrir en multas** por vencimientos olvidados.

---

## 4. Modelo de precios

### 4.1 Planes

| Plan | Precio | Empresas incluidas | Usuarios | Público |
|---|---|---|---|---|
| **Independiente** | $19 / mes | Hasta 3 empresas | 1 | Contador solo |
| **Profesional** | $39 / mes | Hasta 10 empresas | Hasta 3 | Firma pequeña |
| **Estudio** | $79 / mes | Hasta 30 empresas | Hasta 8 | Estudio mediano |
| **Personalizado** | A cotizar | 30+ empresas | A medida | Aliados y franquicias |

### 4.2 Qué incluye cada plan

Todos los planes incluyen el módulo completo (calendario SENIAT, alertas,
cartelera fiscal, retenciones, libro de compras y ventas, evidencias,
dashboard) y el asistente de IA. La diferencia entre planes es **cuántas
empresas** se gestionan, no qué funcionalidades se desbloquean: no se mutila el
producto, se escala el volumen.

### 4.3 Add-ons y servicios

| Concepto | Precio sugerido |
|---|---|
| Setup Fee (configuración inicial) | $49 – $149 único |
| Empresa adicional fuera de plan | $4 / mes |
| Digitalización extra (paquete de 500 facturas) | $9 |
| Migración de datos históricos | $99 – $299 único |
| Capacitación adicional (sesión de 1 h) | $29 |

### 4.4 Reglas comerciales

- **Prueba gratuita:** 14 días, 1 empresa, hasta 50 facturas digitalizadas.
- **Facturación:** mensual adelantada; descuento del 15 % en pago anual.
- **Moneda:** USD como referencia; cobro en USD, transferencia o criptoestable.
- **Sin contrato de permanencia:** cancelación en cualquier momento; los datos
  se exportan en formatos estándar (Excel/CSV).

---

## 5. Justificación del precio

### 5.1 Por qué cobrar por empresa y no por usuario

Cobrar por usuario castiga la adopción: si la firma suma un auxiliar, paga más
sin recibir más valor, y termina compartiendo credenciales. Cobrar por empresa
gestionada tiene tres ventajas:

1. **Alineación con el valor.** El contador cobra honorarios por empresa. Si
   ContaFis le ahorra horas en cada una, el precio por empresa es una fracción
   de lo que factura por esa empresa.
2. **Alineación con el costo.** Cada empresa implica registros contables,
   documentos, evidencias y facturas digitalizadas: el costo variable crece con
   la cantidad de empresas, no con la cantidad de personas mirando la pantalla.
3. **Crecimiento natural.** Cuando el cliente suma una empresa, el ingreso
   sube solo. El plan Estudio existe para que ese crecimiento no lo empuje a
   buscar un competidor.

### 5.2 Componentes del costo variable

| Componente | Naturaleza | Por qué escala con las empresas |
|---|---|---|
| API de IA (NVIDIA NIM) | Por token / por documento | Cada empresa aporta facturas a digitalizar |
| Almacenamiento en base de datos | Por volumen | Asientos, socios, documentos y adjuntos por compañía |
| Evidencias fotográficas | Por archivo | Cada documento cargado guarda imagen |
| Procesamiento y respaldo | Por uso de CPU/IO | Reportes, importaciones y conciliaciones por empresa |

### 5.3 Economía unitaria estimada

Estimaciones conservadoras; el costo de IA se calcula sobre un supuesto de
100 facturas digitalizadas por empresa al mes.

| Métrica | Independiente | Profesional | Estudio |
|---|---|---|---|
| Precio mensual | $19 | $39 | $79 |
| Empresas incluidas | 3 | 10 | 30 |
| Ingreso por empresa / mes | $6.33 | $3.90 | $2.63 |
| Costo variable estimado / mes | $2 | $6 | $14 |
| Margen bruto | **$17 (89 %)** | **$33 (85 %)** | **$65 (82 %)** |

El plan Independiente tiene el mayor margen porcentual, pero el Estudio aporta
el mayor margen absoluto y menor costo de adquisición por empresa. La mezcla
objetivo es 60 % Independiente, 30 % Profesional, 10 % Estudio durante el
primer año.

### 5.4 Anclaje de precio

El cliente compara contra dos alternativas:

- **Hora del contador:** una hora facturada ronda $10–$25. Si ContaFis ahorra
  tres horas al mes, el plan Independiente ya se paga solo.
- **Costo de una multa:** una sanción por declaración tardía o por libro mal
  llevado supera varias veces la suscripción anual.

---

## 6. Costos operativos

### 6.1 Estructura de costos

| Rubro | Tipo | Estimado mensual | Notas |
|---|---|---|---|
| AWS Lightsail (instancia + disco) | Fijo | ~$25 | Un servidor para los primeros 30–50 clientes |
| Dominio, DNS y certificados | Fijo | ~$2 | Certificados gratuitos (Let's Encrypt) |
| Respaldos y monitoreo | Fijo | ~$5 | Snapshots + uptime |
| Consumo API de IA (NVIDIA NIM) | Variable | $0.50 – $1.50 por empresa | Depende del volumen de facturas |
| Correo transaccional | Variable | ~$1 por cada 100 clientes | Alertas y notificaciones |
| Pasarela de pago | Variable | 3–5 % del ingreso | Según proveedor |

**Costo fijo base: ~$32 / mes** con la infraestructura actual, sin contar
personal. La arquitectura es deliberadamente monolítica y multi-tenant para
mantener el costo fijo bajo mientras la base de clientes es pequeña.

### 6.2 Punto de equilibrio

Con un costo fijo de $32 / mes y un margen bruto promedio de ~85 %:

| Escenario | Clientes | Ingreso mensual | Margen bruto | Resultado |
|---|---|---|---|---|
| Break-even | 2 | $38 | ~$32 | Equilibrio |
| Tracción inicial | 10 | $250 | ~$212 | Cubre infraestructura y dominio |
| Operación rentable | 30 | $790 | ~$670 | Cubre infraestructura + soporte parcial |
| Escala | 100 | ~$2,600 | ~$2,210 | Permite dedicación full-time |

### 6.3 Cuándo escalar la infraestructura

- **Hasta 50 clientes:** un solo servidor, respaldos diarios, monitoreo básico.
- **50–150 clientes:** separar base de datos de aplicación, réplicas de lectura
  y cola para digitalización.
- **150+ clientes:** contenedores por tenant o sharding por región, y
  presupuesto dedicado de IA con límites por plan.

---

## 7. Estrategia de crecimiento

### 7.1 Prueba gratuita como motor de adquisición

- 14 días con acceso completo a una empresa.
- Límite de 50 facturas digitalizadas para acotar el costo de IA.
- Onboarding guiado: cargar empresa, importar catálogo de clientes, digitalizar
  las primeras cinco facturas en la misma sesión.
- Al vencer, la cuenta pasa a solo lectura: los datos quedan visibles, pero no
  se pueden cargar documentos nuevos. La conversión se negocia con el trabajo
  ya hecho dentro de la herramienta.

### 7.2 Setup Fee por configuración inicial

El Setup Fee cumple tres funciones:

1. **Filtra curiosos.** Quien paga la configuración va a usar el producto.
2. **Financia el onboarding.** Cubre las horas de carga de plan de cuentas,
   importación de catálogos y capacitación.
3. **Mejora el margen del primer mes**, que es el más caro en soporte.

Rango: $49 (autoservicio asistido) a $149 (migración con datos históricos).

### 7.3 Canales

| Canal | Acción | Costo | Plazo |
|---|---|---|---|
| Gremios y colegios de contadores | Charlas y demo en vivo | Bajo | 1–3 meses |
| Referidos | 1 mes gratis por cliente referido que paga | Variable | Continuo |
| Contenido técnico | Guías de SENIAT, retenciones e IGTF en GitHub y LinkedIn | Bajo | Continuo |
| Alianza con firmas | Plan Personalizado + marca blanca | Medio | 3–6 meses |
| GitHub / portafolio | Repos públicos como prueba de capacidad técnica | Bajo | Continuo |

### 7.4 Retención

- Alertas por correo y en el dashboard antes de cada vencimiento.
- Reporte mensual automático de cumplimiento por empresa.
- Historial y evidencias como "lock-in positivo": mientras más documentos
  carga el cliente, más valioso es el archivo.
- Soporte por WhatsApp en horario laboral para planes Profesional y Estudio.

### 7.5 Métricas a seguir

| Métrica | Objetivo año 1 |
|---|---|
| Conversión de prueba a pago | ≥ 25 % |
| Churn mensual | ≤ 3 % |
| Empresas por cliente (promedio) | ≥ 6 |
| Ingreso recurrente mensual (MRR) | $1,000 al mes 12 |
| Costo de adquisición (CAC) | ≤ $30 |
| Relación LTV / CAC | ≥ 6x |

---

## 8. Riesgos y mitigación

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Costo de IA fuera de control | Margen | Límites por plan, caché de resultados, modelo pequeño para clasificación |
| Dependencia de un proveedor de IA | Continuidad | Capa de abstracción de modelo; fallback a otro proveedor |
| Cambios normativos del SENIAT | Producto obsoleto | Calendario y reglas parametrizables, actualización por release |
| Cliente que abusa del multi-tenant | Costo | Límite de empresas por plan y monitoreo de consumo |
| Competencia de ERPs grandes | Adopción | Foco en la capa venezolana y en el flujo del contador, no en el ERP |
| Concentración en un solo servidor | Disponibilidad | Respaldos diarios, restauración probada y plan de migración |

---

## 9. Hoja de ruta

| Fase | Alcance | Objetivo comercial |
|---|---|---|
| Fase 1 (actual) | Producto funcional, digitalización con IA, deploy automatizado | 5 clientes piloto |
| Fase 2 | Autoservicio de registro, facturación y límites por plan | 20 clientes, MRR $500 |
| Fase 3 | Portal del cliente, reportes automáticos, marca blanca | 50 clientes, MRR $1,500 |
| Fase 4 | Alianzas con estudios, API pública | 100 clientes, MRR $2,600 |

---

## 10. Conclusión

ContaFis no necesita ganar el mercado de ERPs: necesita ser la herramienta
obvia para un contador venezolano que gestiona varias PYMES. El cobro por
empresa mantiene el precio comprensible, el margen sano y el crecimiento
alineado con el uso real. Con un costo fijo cercano a los $32 mensuales y un
margen bruto superior al 80 %, el negocio alcanza el punto de equilibrio con
dos clientes y puede sostener una operación de tiempo completo con cien.

El activo más valioso no es el código, sino el archivo fiscal que el cliente
acumula dentro de la plataforma. Ese archivo es lo que hace que quedarse sea
más barato que irse.

---

*Las cifras de costos, conversión y márgenes de este documento son estimaciones
de planificación, no proyecciones auditadas.*
