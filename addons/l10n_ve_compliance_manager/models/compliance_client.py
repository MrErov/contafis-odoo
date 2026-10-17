from collections import defaultdict

from markupsafe import Markup, escape
from odoo import api, fields, models


class ComplianceClient(models.Model):
    _name = 'l10n.ve.compliance.client'
    _description = 'Compliance Client'

    name = fields.Char(string='Nombre', required=True)
    partner_id = fields.Many2one('res.partner', string='Contacto', required=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True)
    accountant_id = fields.Many2one('res.users', string='Contador')
    rif = fields.Char(string='RIF')
    rif_last_digit = fields.Integer(string='Último dígito RIF', compute='_compute_rif_last_digit')
    is_spe = fields.Boolean(
        string='Sujeto Pasivo Especial',
        default=False,
        help='Si está activo, los vencimientos SENIAT se calculan con el '
             'calendario oficial según el último dígito del RIF.',
    )
    applicable_type_ids = fields.Many2many(
        'l10n.ve.obligation.type',
        string='Obligaciones Aplicables',
        help='Tipos de obligación que la generación automática crea para este '
             'cliente.',
    )
    activity_type = fields.Selection([
        ('comercio', 'Comercio'),
        ('servicios', 'Servicios'),
        ('industria', 'Industria'),
        ('mixto', 'Mixto'),
    ], string='Tipo de actividad')
    municipality = fields.Char(string='Municipio')
    obligation_ids = fields.One2many('l10n.ve.obligation', 'client_id', string='Obligaciones')
    document_ids = fields.One2many('l10n.ve.document', 'client_id', string='Documentos')
    alert_ids = fields.One2many('l10n.ve.alert', 'client_id', string='Alertas')
    compliance_status = fields.Selection([
        ('al_dia', 'Al día'),
        ('pendiente', 'Pendiente'),
        ('vencido', 'Vencido'),
    ], string='Estado de cumplimiento', compute='_compute_compliance_status')
    compliance_score = fields.Float(string='Puntuación de cumplimiento', compute='_compute_compliance_score')
    document_score = fields.Float(
        string='Puntuación documental',
        compute='_compute_document_score',
        help='% de documentos requeridos con estado válido',
    )
    last_alert_date = fields.Datetime(string='Fecha de última alerta')
    pending_alert_count = fields.Integer(string='Alertas pendientes', compute='_compute_pending_alert_count')
    partner_image_1920 = fields.Binary(
        string='Logo',
        related='partner_id.image_1920',
    )
    cartelera_status_current_ids = fields.One2many(
        'l10n.ve.cartelera.status',
        'client_id',
        compute='_compute_cartelera_status_current',
        string='Cartelera Mes Actual',
    )
    cartelera_html = fields.Html(
        string='Mini-Cartelera',
        compute='_compute_cartelera_html',
        sanitize=False,
    )

    @api.depends('rif')
    def _compute_rif_last_digit(self):
        for client in self:
            digits = [c for c in (client.rif or '') if c.isdigit()]
            client.rif_last_digit = int(digits[-1]) if digits else 0

    @api.depends('obligation_ids.state', 'obligation_ids.due_date')
    def _compute_compliance_status(self):
        today = fields.Date.today()
        for client in self:
            active = client.obligation_ids.filtered(
                lambda obligation: obligation.state != 'cancelled'
            )
            overdue = active.filtered(
                lambda obligation: obligation.state == 'overdue'
                or (
                    obligation.state == 'pending'
                    and obligation.due_date
                    and obligation.due_date < today
                )
            )
            pending = active.filtered(
                lambda obligation: obligation.state == 'pending'
            )
            if overdue:
                client.compliance_status = 'vencido'
            elif pending:
                client.compliance_status = 'pendiente'
            else:
                client.compliance_status = 'al_dia'

    @api.depends('obligation_ids.state', 'obligation_ids.due_date')
    def _compute_compliance_score(self):
        today = fields.Date.today()
        for client in self:
            active = client.obligation_ids.filtered(
                lambda obligation: obligation.state != 'cancelled'
            )
            total = len(active)
            if not total:
                client.compliance_score = 100.0
                continue
            subject = active.filtered(
                lambda obligation: obligation.state == 'overdue'
                or (
                    obligation.state == 'pending'
                    and obligation.due_date
                    and obligation.due_date < today
                )
            )
            client.compliance_score = round((total - len(subject)) * 100.0 / total, 2)

    @api.depends('document_ids.state', 'document_ids.document_type_id')
    def _compute_document_score(self):
        for client in self:
            required_types = self.env['l10n.ve.document.type'].search([
                ('required_for', '=', 'company'),
            ])
            if not required_types:
                client.document_score = 100.0
                continue
            valid_count = 0
            for doc_type in required_types:
                docs = client.document_ids.filtered(
                    lambda d: d.document_type_id == doc_type
                )
                if docs.filtered(lambda d: d.state == 'valid'):
                    valid_count += 1
            client.document_score = round(valid_count * 100.0 / len(required_types), 2)

    @api.depends('alert_ids.state')
    def _compute_pending_alert_count(self):
        for client in self:
            client.pending_alert_count = len(
                client.alert_ids.filtered(
                    lambda alert: alert.state == 'pending'
                )
            )

    def action_open_cartelera_gaps(self):
        """Abrir vista de brechas de cartelera (state='missing') para este cliente."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Brechas Cartelera',
            'res_model': 'l10n.ve.cartelera.status',
            'view_mode': 'list,form',
            'domain': [('client_id', '=', self.id), ('state', '=', 'missing')],
            'context': {'default_client_id': self.id},
        }

    def action_generate_obligations(self):
        """Generar las obligaciones del mes actual y el siguiente (RF-12)."""
        self.ensure_one()
        created = self.env['l10n.ve.obligation']._generate_window_for_client(self)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': f'Se generaron {created} obligaciones para {self.name}.',
            },
        }

    @api.depends('cartelera_status_current_ids.state', 'cartelera_status_current_ids.document_type_id')
    def _compute_cartelera_html(self):
        """Genera HTML de mini-cartelera agrupado por institución con badges de estado."""

        for client in self:
            statuses = client.cartelera_status_current_ids

            if not statuses:
                client.cartelera_html = Markup(
                    '<div class="text-muted text-center py-2">Sin datos para el mes actual</div>'
                )
                continue

            # Agrupar por institución
            by_institution = defaultdict(list)
            for status in statuses:
                inst = status.document_type_id.institution_id
                if inst:
                    by_institution[inst.id].append(status)

            parts = [Markup('<div class="cartelera-mini">')]

            # Ordenar instituciones por tipo (orden estándar)
            type_order = ['seniat', 'ivss', 'inces', 'banavih', 'mintra', 'municipal', 'saren', 'otro']
            sorted_institutions = sorted(
                by_institution.items(),
                key=lambda x: type_order.index(x[1][0].document_type_id.institution_id.type) if x[1][0].document_type_id.institution_id and x[1][0].document_type_id.institution_id.type in type_order else 99
            )

            for inst_id, status_list in sorted_institutions:
                if not status_list:
                    continue
                inst = status_list[0].document_type_id.institution_id
                if not inst:
                    continue

                # Nombre de institución escapado
                parts.append(Markup('<div class="institution-block mb-2">'))
                parts.append(Markup('<strong class="institution-title">{}</strong>').format(escape(inst.name)))

                for status in status_list:
                    doc_type = status.document_type_id
                    state = status.state

                    # Clase CSS según estado
                    state_class_map = {
                        'valid': 'bg-success',
                        'missing': 'bg-danger',
                        'expired': 'bg-danger',
                        'pending': 'bg-warning text-dark',
                        'rejected': 'bg-secondary',
                    }
                    badge_class = state_class_map.get(state, 'bg-secondary')

                    # Badge del documento
                    parts.append(Markup(
                        '<span class="badge {cls} me-1">{code}</span>'
                    ).format(
                        cls=escape(badge_class),
                        code=escape(doc_type.code),
                    ))

                parts.append(Markup('</div>'))

            parts.append(Markup('</div>'))
            client.cartelera_html = Markup('').join(parts)

    def _compute_cartelera_status_current(self):
        """Obtiene los statuses de cartelera del mes actual."""
        today = fields.Date.today()
        current_year = today.year
        current_month = str(today.month)

        for client in self:
            client.cartelera_status_current_ids = self.env['l10n.ve.cartelera.status'].search([
                ('client_id', '=', client.id),
                ('year', '=', current_year),
                ('month', '=', current_month),
            ])
