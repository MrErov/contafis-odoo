from odoo import api, fields, models


class CarteleraStatus(models.Model):
    _name = 'l10n.ve.cartelera.status'
    _description = 'Snapshot mensual de cartelera fiscal por cliente'
    _order = 'year desc, month desc, document_type_id'

    client_id = fields.Many2one(
        'l10n.ve.compliance.client',
        string='Cliente',
        required=True,
        ondelete='cascade',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        related='client_id.company_id',
        store=True,
        index=True,
        readonly=True,
    )
    year = fields.Integer(string='Año', required=True)
    month = fields.Selection([
        ('1', 'Enero'), ('2', 'Febrero'), ('3', 'Marzo'),
        ('4', 'Abril'), ('5', 'Mayo'), ('6', 'Junio'),
        ('7', 'Julio'), ('8', 'Agosto'), ('9', 'Septiembre'),
        ('10', 'Octubre'), ('11', 'Noviembre'), ('12', 'Diciembre'),
    ], string='Mes', required=True)
    document_type_id = fields.Many2one(
        'l10n.ve.document.type',
        string='Tipo de documento',
        required=True,
    )
    document_id = fields.Many2one(
        'l10n.ve.document',
        string='Documento',
        ondelete='set null',
    )
    state = fields.Selection([
        ('valid', 'Válido'),
        ('expired', 'Expirado'),
        ('pending', 'Pendiente'),
        ('rejected', 'Rechazado'),
        ('missing', 'Faltante'),
    ], string='Estado', required=True)
    expiry_date = fields.Date(string='Fecha de vencimiento')
    date_generated = fields.Datetime(
        string='Fecha de generación',
        default=fields.Datetime.now,
        readonly=True,
    )
    notes = fields.Text(string='Notas')
    evidence_ids = fields.One2many(
        'l10n.ve.cartelera.evidence',
        'cartelera_status_id',
        string='Evidencias',
    )
    evidence_count = fields.Integer(
        string='Nº de evidencias',
        compute='_compute_evidence_count',
    )

    _unique_client_year_month_type = models.Constraint(
        'unique(client_id, year, month, document_type_id)',
        'Ya existe un snapshot para este cliente/mes/tipo.',
    )

    @api.model
    def _compute_state_from_document(self, document):
        """Devuelve el estado basado en un documento existente."""
        if not document:
            return 'missing'
        return document.state

    @api.model
    def _get_document_for_type(self, client_id, document_type_id):
        """Busca el documento vigente del cliente para un tipo dado."""
        return self.env['l10n.ve.document'].search([
            ('client_id', '=', client_id),
            ('document_type_id', '=', document_type_id),
        ], order='expiry_date desc', limit=1)

    @api.model
    def generate_snapshot(self, client_id, year, month, statuses=None):
        """
        Genera/actualiza el snapshot mensual de cartelera para un cliente.

        Dos modos de operación:
        1. Sin `statuses` (modo normal): escanea l10n.ve.document del cliente.
           Para cada tipo requerido (required_for='company'), busca documento
           vigente; si no existe → state='missing'.

        2. Con `statuses` (modo Fase C / import Excel): dict {code: bool}
           donde True = documento presente/válido, False = faltante.
           Usado por el importador de cartelera Excel (Fase C) para crear
           snapshots basados en lo que dice el Excel, no en lo que hay en BD.

        Args:
            client_id (int): ID de l10n.ve.compliance.client
            year (int): Año (ej. 2026)
            month (str): Mes como string '1'..'12'
            statuses (dict|None): {code: bool} opcional desde Excel

        Returns:
            recordset: l10n.ve.cartelera.status creados/actualizados
        """
        client = self.env['l10n.ve.compliance.client'].browse(client_id)
        if not client.exists():
            return self.env['l10n.ve.cartelera.status']

        doc_types = self.env['l10n.ve.document.type'].search([
            ('required_for', '=', 'company'),
        ])

        created = self.env['l10n.ve.cartelera.status']

        for doc_type in doc_types:
            code = doc_type.code
            if statuses is not None and code in statuses:
                # Modo Fase C: usar dato del Excel
                has_doc = statuses[code]
                if has_doc:
                    state = 'valid'
                    expiry_date = False  # Se desconoce la fecha exacta desde Excel
                    document_id = False
                else:
                    state = 'missing'
                    expiry_date = False
                    document_id = False
            else:
                # Modo normal: escanear BD
                document = self._get_document_for_type(client_id, doc_type.id)
                if document:
                    state = self._compute_state_from_document(document)
                    expiry_date = document.expiry_date
                    document_id = document.id
                else:
                    state = 'missing'
                    expiry_date = False
                    document_id = False

            snapshot = self.search([
                ('client_id', '=', client_id),
                ('year', '=', year),
                ('month', '=', month),
                ('document_type_id', '=', doc_type.id),
            ], limit=1)

            vals = {
                'client_id': client_id,
                'year': year,
                'month': month,
                'document_type_id': doc_type.id,
                'state': state,
                'expiry_date': expiry_date,
                'document_id': document_id,
            }

            if snapshot:
                snapshot.write(vals)
            else:
                snapshot = self.create(vals)
            created |= snapshot

        return created

    @api.model
    def generate_snapshot_all_clients(self, year, month, statuses_by_client=None):
        """
        Genera snapshots para todos los clientes activos.

        Args:
            year (int): Año
            month (str): Mes '1'..'12'
            statuses_by_client (dict|None): {client_id: {code: bool}} opcional
        """
        clients = self.env['l10n.ve.compliance.client'].search([])
        all_created = self.env['l10n.ve.cartelera.status']

        for client in clients:
            statuses = None
            if statuses_by_client and client.id in statuses_by_client:
                statuses = statuses_by_client[client.id]
            created = self.generate_snapshot(client.id, year, month, statuses)
            all_created |= created

        return all_created

    @api.model
    def _cron_generate_monthly_snapshot(self):
        """Cron mensual: genera snapshot del mes anterior para todos los clientes."""
        from dateutil.relativedelta import relativedelta
        today = fields.Date.today()
        prev_month = today - relativedelta(months=1)
        year = prev_month.year
        month = str(prev_month.month)
        self.generate_snapshot_all_clients(year, month)

    @api.depends('evidence_ids.state')
    def _compute_evidence_count(self):
        for rec in self:
            rec.evidence_count = len(rec.evidence_ids)

    def _recompute_status_from_evidence(self):
        """
        Recalcula el estado del snapshot basado en las evidencias asociadas.

        Reglas:
        - Si hay al menos una evidencia 'accepted' → state = 'valid'
        - Elif hay al menos una evidencia 'pending' → state = 'pending'
        - Elif hay evidencias (todas 'rejected') → state = 'rejected'
        - Si NO hay evidencias → NO TOCAR el estado (puede ser 'missing' original)
        """
        for status in self:
            evidence_states = status.evidence_ids.mapped('state')
            if not evidence_states:
                # Sin evidencias: no tocar el estado (puede ser 'missing' del cron)
                continue
            if 'accepted' in evidence_states:
                status.state = 'valid'
            elif 'pending' in evidence_states:
                status.state = 'pending'
            else:
                # Solo rejected
                status.state = 'rejected'
