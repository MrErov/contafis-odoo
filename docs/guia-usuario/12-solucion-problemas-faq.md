# Solución de problemas y FAQ

## Problemas comunes

### No puedo iniciar sesión

- Verificar URL y credenciales
- Si olvidó contraseña: contactar al administrador

### El RIF es rechazado como inválido

- Verificar el último dígito según el algoritmo módulo 11
- Ejemplo: `J-31527189-4` es válido; `J-12345678-0` no
- Si el RIF es correcto pero Odoo lo rechaza, revisar si hay espacios o guiones mal colocados

### No aparece el módulo en Aplicaciones

- Verificar que el addons path incluya la carpeta del módulo
- Contactar al administrador del servidor

### El botón "Regenerar Libro" no aparece

- Solo aparece en facturas posteadas
- Verificar que la factura esté en estado *Publicado*

### Error al exportar el libro

- Verificar que existan líneas en el período seleccionado
- Verificar que el usuario tenga permisos de exportación

### No se envían las alertas por email

- Verificar que el servidor SMTP esté configurado (sección 02, punto 5)
- Probar con el botón [Probar conexión]

## Preguntas frecuentes

**¿Puedo usar el sistema con varios clientes a la vez?**
Sí. Es el escenario principal del módulo. Ver sección 03.

**¿Qué pasa si cargo una factura con datos incorrectos?**
Se puede revertir el asiento desde Contabilidad y volver a cargar. Ver sección 04.

**¿El sistema calcula automáticamente las retenciones?**
Sí, en facturas de proveedor con el botón [Generar Retención]: IVA 75% e ISLR 3% (el IGTF todavía no se calcula). Ver [Limitaciones conocidas](./anexo-limitaciones.md).

**¿El sistema calcula el calendario SENIAT por RIF?**
Sí. El vencimiento se calcula con las tablas del calendario según el último dígito del RIF. Ver [Calendario SENIAT](./08-calendario-seniat.md).

**¿Puedo exportar los datos a otro sistema?**
Sí. El libro y la planilla se exportan a Excel. Ver sección 11.

**¿Dónde se guardan los adjuntos?**
En el filestore de Odoo. Ver sección 11.

## Cómo pedir soporte

Datos a recolectar antes de reportar:

- Captura de pantalla del error
- Ruta exacta donde ocurrió
- Cliente afectado
- Últimas acciones realizadas

## Siguiente paso

> Ver [Glosario](./anexo-glosario.md) y [Limitaciones conocidas](./anexo-limitaciones.md).
