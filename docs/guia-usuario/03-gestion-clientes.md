# Gestión de clientes

## ¿Qué es un "cliente de cumplimiento"?

En este sistema, un **cliente de cumplimiento** es la empresa cuyo RIF usted administra como contador. Es distinto del *partner comercial* (contacto de Odoo base): el cliente de cumplimiento vincula ese partner con obligaciones fiscales, documentos y alertas. En el escenario del piloto, un contador gestiona 7 o más clientes desde la misma instancia.

## Crear un cliente nuevo

Ruta: *Cumplimiento VE → Clientes → [Nuevo]*

![Formulario de creación de un cliente de cumplimiento](./assets/screenshots/03-01-client-form.png)

Complete los campos del formulario:

- **Nombre:** nombre comercial del cliente (ej. *Distribuidora Los Andes, C.A.*)
- **Contacto:** seleccione el partner existente o cree uno nuevo
- **Compañía:** empresa (compañía de Odoo) a la que pertenece el cliente. Viene preseleccionada con la **compañía activa** en la barra superior; verifique que sea la correcta
- **Contador:** usuario responsable (opcional)
- **RIF:** ingrese el valor con formato J-XXXXXXXX-X
- **Tipo de actividad:** Comercio, Servicios, Industria o Mixto
- **Municipio:** municipio de la dirección fiscal

Los campos **Estado de cumplimiento**, **Puntuación de cumplimiento** y **Última alerta** se calculan automáticamente y no se editan manualmente.

<div class="note">

El campo **Contador** controla quién más puede ver al cliente: un contador solo accede a los clientes que tenga asignados. Si deja el campo vacío, el cliente queda visible únicamente para el administrador.

</div>

## Validación del RIF

El RIF debe ser válido según el algoritmo de módulo 11. Si ingresa un RIF inválido, el sistema muestra un error al guardar. Para verificar, revise el último dígito del documento:

- Correcto: `J-31527189-4`
- Incorrecto: `J-12345678-0`

El campo **Último dígito RIF** se calcula automáticamente a partir del valor ingresado.

## Lista de clientes

Ruta: *Cumplimiento VE → Clientes*

![Lista de clientes con columnas principales](./assets/screenshots/03-02-client-list.png)

La lista muestra las columnas: **Nombre**, **RIF**, **Último dígito**, **Contacto**, **Compañía**, **Tipo de actividad**, **Municipio**, **Estado de cumplimiento** y **Puntuación**.

La columna **Compañía** indica a qué empresa pertenece cada cliente. Si ve varios clientes juntos en la lista, es porque tiene varias empresas activas en el selector de la barra superior (ver más abajo).

Puede filtrar por **RIF**, **Nombre**, **Contacto**, **Contador**, **Tipo de actividad** o **Municipio** usando el campo de búsqueda.

## Vista kanban

Ruta: *Cumplimiento VE → Clientes → [icono Kanban]*

![Vista kanban de clientes](./assets/screenshots/03-03-client-kanban.png)

Cada tarjeta muestra: logo del partner, nombre del cliente, RIF, estado de cumplimiento (color del borde y badge), puntuación y una **barra de progreso de la cartelera documental** del mes actual con los documentos al día sobre el total. Si hay documentos pendientes o alertas sin resolver, aparecen como badges junto a la barra. Las tarjetas se agrupan por **Tipo de actividad** por defecto.

## Editar un cliente

Haga clic en el cliente desde la lista o el kanban. Modifique los campos necesarios y presione [Guardar].

## Archivar un cliente

Archivar oculta el cliente sin eliminar sus datos. Borrar elimina el registro permanentemente. Se recomienda **archivar** clientes que dejan de estar activos.

Para archivar: abra el cliente → menú [Acción] → [Archivar].

## Cambiar entre clientes (multi-cliente)

Cada cliente vive en su propia empresa de Odoo (sección 02). El selector de la barra superior controla **qué empresas ve** en cada momento:

![Selector de empresas con los clientes activos](./assets/screenshots/03-04-company-switcher.png)

- **Ver varios clientes a la vez:** abra el selector, marque con un clic las casillas de las empresas que quiera ver juntas y pulse **[Confirmar]**. Las listas, el kanban y la bandeja mostrarán los datos de todas las marcadas.
- **Trabajar con un solo cliente:** deje marcada únicamente la empresa correspondiente y pulse **[Confirmar]**.
- **Volver a ver todo:** reabra el selector y marque de nuevo las empresas que había desmarcado.

<div class="warning">

Si un cliente "desaparece" de las listas, casi siempre es porque su empresa quedó **desmarcada** en el selector. Reábralo y verifique las casillas antes de buscar otra causa (ver también la FAQ, sección 13).

</div>

## Siguiente paso

> Con los clientes registrados, el siguiente paso es cargar sus facturas físicas. Continúa con [Cargar facturas físicas](./04-cargar-facturas.md).
