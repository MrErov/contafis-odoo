import re

from odoo import fields, models


class ImportLine(models.TransientModel):
    _name = 'l10n.ve.import.line'
    _description = 'Línea de Importación (Preview + Resultado)'
    _order = 'row_index'

    wizard_id = fields.Many2one(
        'l10n.ve.import.wizard', string='Wizard', required=True,
        ondelete='cascade'
    )
    row_index = fields.Integer(string='Nº Fila', required=True)
    data = fields.Json(string='Datos Parseados')
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('validated', 'Validado'),
        ('imported', 'Creado'),
        ('updated', 'Actualizado'),
        ('error', 'Error'),
        ('skipped', 'Omitido'),
    ], string='Estado', default='draft', required=True)
    record_id = fields.Reference(
        selection='_get_reference_models',
        string='Registro Creado/Actualizado'
    )
    record_name = fields.Char(string='Nombre Registro')
    model_name = fields.Char(string='Modelo Destino')
    error_msg = fields.Text(string='Errores')

    def _get_reference_models(self):
        """Modelos que pueden ser referenciados por record_id."""
        return [
            ('l10n.ve.obligation', 'Obligación'),
            ('l10n.ve.document', 'Documento'),
            ('l10n.ve.compliance.client', 'Cliente Cumplimiento'),
            ('l10n.retention', 'Retención'),
            ('l10n.ve.cartelera.status', 'Cartelera Status'),
            ('l10n.ve.vat.book.line', 'Libro IVA Línea'),
        ]

    def _validate_syntax(self):
        """
        Valida tipos de datos según el mapping del wizard.
        Actualiza self.error_msg si falla.
        Retorna True si válido, False si no.
        """
        self.ensure_one()
        wizard = self.wizard_id
        if not wizard or not self.data:
            self.write({'state': 'error', 'error_msg': 'Sin wizard o datos'})
            return False

        errors = []

        # Obtener mapeos del wizard
        mappings = wizard.mapping_ids.filtered(lambda m: m.field_name)
        for m in mappings:
            value = self.data.get(m.field_name) if self.data else None
            required = m.required
            field_type = m.field_type

            # Validar required
            if required and (value is None or value == ''):
                errors.append(f"Campo '{m.col_name}' ({m.field_name}) es obligatorio")
                continue

            if value is None or value == '':
                continue  # No validar tipo si vacío y no required

            # Validar según tipo
            try:
                if field_type == 'date':
                    fields.Date.to_date(value)
                elif field_type in ('float', 'monetary'):
                    wizard._parse_number(value)
                elif field_type == 'integer':
                    int(value)
                elif field_type == 'many2one':
                    # Validar RIF para res.partner
                    if m.relation_model == 'res.partner' and m.field_name in ('rif', 'client_id'):
                        if not wizard._validate_rif(value):
                            errors.append(f"RIF inválido: '{value}'")
                # char, selection, boolean, text: no validación extra de formato
            except Exception as e:
                errors.append(f"Campo '{m.col_name}' ({m.field_name}): {e}")

        if errors:
            self.write({
                'state': 'error',
                'error_msg': '; '.join(errors)
            })
            return False
        else:
            self.write({'state': 'validated', 'error_msg': False})
            return True

    def _validate_reference(self):
        """
        Valida nivel 2 (referencial): que los registros Many2one referenciados
        existan en la BD. Se ejecuta después de _validate_syntax().

        Por cada mapping_id del wizard delega en el resolver del wizard
        (ImportWizard._resolve_many2one), que busca por nombre/RIF/VAT dentro
        de la compañía del wizard (o del ámbito global del modelo). Así la
        validación acepta exactamente las mismas referencias que el import.

        Si no encuentra el registro, añade a self.error_msg:
          "Referencia no encontrada: {field_name}={valor}"

        Cambia self.state a 'error' si hay errores.
        Retorna True si no hay errores, False si hay alguno.

        NO resuelve los IDs (eso lo hace el importador). Solo valida existencia.
        """
        self.ensure_one()
        wizard = self.wizard_id
        if not wizard or not self.data:
            self.write({'state': 'error', 'error_msg': 'Sin wizard o datos'})
            return False

        errors = []
        mappings = wizard.mapping_ids.filtered(lambda m: m.field_name and m.field_type == 'many2one')

        for m in mappings:
            value = self.data.get(m.field_name) if self.data else None
            if value is None or value == '':
                continue

            field_name = m.field_name

            model_name, _domain = wizard._get_import_target(self, {})
            target_field = self.env[model_name]._fields.get(field_name)
            relation_model = (
                target_field.comodel_name
                if target_field is not None and target_field.type == 'many2one'
                else m.relation_model
            )

            if relation_model:
                resolved = wizard._resolve_many2one(
                    relation_model, field_name, value,
                )
                if resolved is False:
                    errors.append(
                        f"Referencia no encontrada: {m.col_name} "
                        f"({field_name}) = '{value}' en {relation_model}"
                    )
                # resolved is None -> relación no soportada: no se inventa error

        if errors:
            self.write({'state': 'error', 'error_msg': '; '.join(errors)})
            return False
        return True

    def _validate_business(self):
        """
        Valida nivel 3 (negocio): reglas específicas del dominio venezolano.
        Se ejecuta después de _validate_syntax() y _validate_reference().

        Reglas por modelo destino (wizard.import_type):

        1. l10n.ve.obligation:
           - period debe tener formato MM/YYYY
           - due_date >= hoy (si el período es futuro) o puede ser pasada
           - amount > 0
           - Si obligation_type_id.periodicity == 'anual', period debe ser YYYY

        2. l10n.ve.document:
           - expiry_date >= issue_date (si ambos existen)
           - expiry_date > hoy (si el documento está 'valid')
           - number no debe estar vacío

        3. l10n.ve.compliance.client:
           - rif debe pasar _validate_rif()
           - activity_type debe ser uno de: comercio, servicios, industria, mixto

        4. l10n.retention:
           - amount > 0
           - invoice_id.move_type == 'in_invoice'
           - date <= hoy

        Si alguna regla falla, añade a self.error_msg:
          "Regla de negocio: {descripción del error}"

        Cambia self.state a 'error' si hay errores.
        Retorna True si no hay errores, False si hay alguno.
        """
        self.ensure_one()
        wizard = self.wizard_id
        if not wizard or not self.data:
            self.write({'state': 'error', 'error_msg': 'Sin wizard o datos'})
            return False

        errors = []
        data = self.data or {}

        # Obtener el tipo de importación del wizard
        import_type = wizard.import_type if wizard else False

        if import_type == 'obligation':
            # Validar period formato MM/YYYY
            period = data.get('period')
            if period:
                if not re.match(r'^\d{2}/\d{4}$', period):
                    errors.append("Regla de negocio: period debe tener formato MM/YYYY")
                else:
                    # Validar due_date >= hoy si período es futuro
                    due_date = data.get('due_date')
                    if due_date:
                        today = fields.Date.today()
                        due = fields.Date.to_date(due_date)
                        if due < today:
                            errors.append("Regla de negocio: due_date no puede ser anterior a hoy para períodos pasados")
                    # Validar amount > 0
                    amount = data.get('amount')
                    if amount is not None and amount <= 0:
                        errors.append("Regla de negocio: amount debe ser > 0")
                    # Validar periodicity anual => period debe ser YYYY
                    periodicity = data.get('periodicity')
                    if periodicity == 'anual':
                        # period Ya validó formato MM/YYYY, pero anual debe ser YYYY solo
                        # Odoo usa period como char, así que validamos que sea solo año
                        if not re.match(r'^\d{4}$', period):
                            errors.append("Regla de negocio: period anual debe ser YYYY")

        elif import_type == 'document':
            # Validar expiry_date >= issue_date (si ambos existen)
            expiry_date = data.get('expiry_date')
            issue_date = data.get('issue_date')
            if expiry_date and issue_date:
                exp = fields.Date.to_date(expiry_date)
                iss = fields.Date.to_date(issue_date)
                if exp < iss:
                    errors.append("Regla de negocio: expiry_date debe ser >= issue_date")
            # Validar expiry_date > hoy si documento está 'valid'
            state = data.get('state')
            if state == 'valid' and expiry_date:
                exp = fields.Date.to_date(expiry_date)
                today = fields.Date.today()
                if exp <= today:
                    errors.append("Regla de negocio: expiry_date debe ser > hoy para documentos 'valid'")
            # Validar number no vacío
            number = data.get('number')
            if not number:
                errors.append("Regla de negocio: number no debe estar vacío")

        elif import_type == 'client':
            # Validar rif pasa _validate_rif()
            rif = data.get('rif')
            if rif:
                if not wizard._validate_rif(rif):
                    errors.append("Regla de negocio: RIF inválido")
            # Validar activity_type es uno de: comercio, servicios, industria, mixto
            activity_type = data.get('activity_type')
            if activity_type:
                valid_types = ['comercio', 'servicios', 'industria', 'mixto']
                if activity_type not in valid_types:
                    errors.append("Regla de negocio: activity_type debe ser uno de: comercio, servicios, industria, mixto")

        elif import_type == 'retention':
            # Validar amount > 0
            amount = data.get('amount')
            if amount is not None and amount <= 0:
                errors.append("Regla de negocio: amount debe ser > 0")
            # Validar invoice_id.move_type == 'in_invoice'
            invoice_ref = data.get('invoice_id')
            if invoice_ref:
                invoice = self.env['account.move'].search([
                    ('ref', '=', invoice_ref),
                    ('move_type', '=', 'in_invoice'),
                ], limit=1)
                if not invoice:
                    errors.append("Regla de negocio: factura no encontrada por ref")
                elif invoice.move_type != 'in_invoice':
                    errors.append("Regla de negocio: la factura debe ser in_invoice")
            # Validar date <= hoy
            date = data.get('date')
            if date:
                today = fields.Date.today()
                dt = fields.Date.to_date(date)
                if dt > today:
                    errors.append("Regla de negocio: date debe ser <= hoy")

        elif import_type == 'cartelera':
            # Validar RIF no vacío
            rif = data.get('rif')
            if not rif:
                errors.append("Regla de negocio: rif no puede estar vacío")
            # Validar year entre 2020 y 2100
            year = data.get('year')
            if year is not None:
                try:
                    year_int = int(year)
                    if year_int < 2020 or year_int > 2100:
                        errors.append("Regla de negocio: year debe estar entre 2020 y 2100")
                except (ValueError, TypeError):
                    errors.append("Regla de negocio: year debe ser un entero válido")
            # Validar month entre '1' y '12'
            month = data.get('month')
            if month is not None:
                try:
                    month_int = int(month)
                    if month_int < 1 or month_int > 12:
                        errors.append("Regla de negocio: month debe estar entre 1 y 12")
                except (ValueError, TypeError):
                    errors.append("Regla de negocio: month debe ser un entero válido")
            # Validar statuses tiene 36 claves C01..C36
            statuses = data.get('statuses', {})
            if not isinstance(statuses, dict):
                errors.append("Regla de negocio: statuses debe ser un diccionario")
            else:
                expected_codes = [f'C{i:02d}' for i in range(1, 37)]
                for code in expected_codes:
                    if code not in statuses:
                        errors.append(f"Regla de negocio: statuses debe incluir clave '{code}'")
                # Validar que no hay claves extra
                for code in statuses:
                    if code not in expected_codes:
                        errors.append(f"Regla de negocio: statuses contiene clave inválida '{code}'")

        if errors:
            self.write({
                'state': 'error',
                'error_msg': '; '.join(errors)
            })
            return False
        self.write({'state': 'validated', 'error_msg': False})
        return True
