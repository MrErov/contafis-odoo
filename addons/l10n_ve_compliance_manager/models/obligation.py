from calendar import monthrange
from datetime import date, timedelta

from odoo import api, fields, models


def _add_months(year, month, n):
    index = year * 12 + (month - 1) + n
    return index // 12, index % 12 + 1


def _quincena_table_code(periodicity, table_code, quincena):
    if periodicity == 'quincenal' and quincena in ('q1', 'q2'):
        return 'a1' if quincena == 'q1' else 'a2'
    return table_code


def _last_period_month(periodicity, month):
    if periodicity == 'trimestral':
        return month % 3 == 0
    if periodicity == 'anual':
        return month == 12
    if periodicity == 'bimonthly':
        return month % 2 == 0
    return True


class VeObligation(models.Model):
    _name = 'l10n.ve.obligation'
    _description = 'Obligación'

    ALERT_TYPE_LABELS = {
        'due_soon': 'Vence pronto',
        'overdue': 'Vencida',
        'missing_payment': 'Falta de pago',
        'document_expiring': 'Documento por vencer',
        'document_missing': 'Documento faltante',
        'calendar_missing': 'Calendario faltante',
    }

    SENIAT_2026_CALENDAR = {
        1: {0: 28, 1: 19, 2: 21, 3: 30, 4: 23, 5: 22, 6: 20, 7: 27, 8: 26, 9: 29},
        2: {0: 20, 1: 23, 2: 18, 3: 18, 4: 25, 5: 27, 6: 19, 7: 24, 8: 26, 9: 27},
        3: {0: 25, 1: 20, 2: 24, 3: 23, 4: 26, 5: 30, 6: 27, 7: 18, 8: 31, 9: 17},
        4: {0: 23, 1: 27, 2: 21, 3: 30, 4: 20, 5: 22, 6: 24, 7: 17, 8: 29, 9: 28},
        5: {0: 20, 1: 18, 2: 29, 3: 22, 4: 21, 5: 28, 6: 19, 7: 26, 8: 27, 9: 25},
        6: {0: 29, 1: 26, 2: 16, 3: 18, 4: 19, 5: 17, 6: 30, 7: 22, 8: 23, 9: 25},
        7: {0: 27, 1: 21, 2: 30, 3: 23, 4: 28, 5: 22, 6: 20, 7: 31, 8: 17, 9: 29},
        8: {0: 31, 1: 25, 2: 24, 3: 18, 4: 19, 5: 21, 6: 28, 7: 20, 8: 26, 9: 27},
        9: {0: 29, 1: 18, 2: 24, 3: 21, 4: 30, 5: 25, 6: 28, 7: 22, 8: 17, 9: 23},
        10: {0: 20, 1: 28, 2: 29, 3: 23, 4: 22, 5: 30, 6: 21, 7: 27, 8: 26, 9: 19},
        11: {0: 27, 1: 26, 2: 17, 3: 23, 4: 20, 5: 18, 6: 25, 7: 19, 8: 24, 9: 30},
        12: {0: 16, 1: 29, 2: 21, 3: 28, 4: 22, 5: 17, 6: 18, 7: 18, 8: 30, 9: 23},
    }

    name = fields.Char(string='Nombre', required=True)
    client_id = fields.Many2one('l10n.ve.compliance.client', string='Cliente')
    obligation_type_id = fields.Many2one('l10n.ve.obligation.type', string='Tipo de obligación')
    period = fields.Char(string='Período')
    quincena = fields.Selection([
        ('monthly', 'Mensual'),
        ('q1', '1ra quincena (01–15)'),
        ('q2', '2da quincena (16–fin)'),
    ], string='Quincena', default='monthly')
    due_date_override = fields.Boolean(string='Vencimiento manual')
    due_date = fields.Date(
        string='Fecha de vencimiento',
        compute='_compute_due_date',
        inverse='_inverse_due_date',
        store=True,
    )
    amount = fields.Monetary(string='Monto')
    currency_id = fields.Many2one('res.currency', string='Moneda')
    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('paid', 'Pagada'),
        ('overdue', 'Vencida'),
        ('cancelled', 'Cancelada'),
    ], string='Estado', default='pending')
    payment_date = fields.Date(string='Fecha de pago')
    payment_reference = fields.Char(string='Referencia de pago')
    payment_attachment = fields.Binary(string='Comprobante de pago')
    retention_id = fields.Many2one('l10n.retention', string='Retención')
    move_id = fields.Many2one('account.move', string='Factura')
    document_ids = fields.One2many('l10n.ve.document', 'obligation_id', string='Documentos')
    alert_ids = fields.One2many('l10n.ve.alert', 'obligation_id', string='Alertas')
    responsible_id = fields.Many2one('res.users', string='Responsable')
    notes = fields.Text(string='Notas')

    def _cron_generate_compliance_alerts(self):
        today = fields.Date.today()
        now = fields.Datetime.now()
        obligations = self.search([('state', 'in', ('pending', 'overdue'))])
        obligations._mark_overdue(today)
        obligations._generate_obligation_alerts(today, now)
        self.env['l10n.ve.document'].search([('state', '=', 'valid')])._generate_document_alerts(now)

    def _mark_overdue(self, today):
        overdue = self.filtered(
            lambda obligation: obligation.state == 'pending'
            and obligation.due_date
            and obligation.due_date < today
        )
        overdue.write({'state': 'overdue'})

    @api.depends(
        'due_date_override',
        'period',
        'quincena',
        'client_id.rif',
        'client_id.rif_last_digit',
        'client_id.is_spe',
        'obligation_type_id.due_day_rule',
        'obligation_type_id.due_day_value',
        'obligation_type_id.periodicity',
        'obligation_type_id.seniat_table_code',
    )
    def _compute_due_date(self):
        today = fields.Date.today()
        for obligation in self:
            if obligation.due_date_override:
                continue
            obligation.due_date = obligation._get_computed_due_date(today)

    def _inverse_due_date(self):
        for obligation in self:
            obligation.due_date_override = True

    def _get_computed_due_date(self, today):
        self.ensure_one()
        if not self.period or '/' not in self.period:
            return False
        try:
            month_str, year_str = self.period.split('/')
            month, year = int(month_str), int(year_str)
        except ValueError:
            return False
        if not 1 <= month <= 12 or not 1900 <= year <= 9999:
            return False
        return self._resolve_due_date(month, year, today)

    def _get_target_month(self, month, year):
        periodicity = self.obligation_type_id.periodicity
        if periodicity == 'trimestral':
            month = ((month - 1) // 3 + 1) * 3
        elif periodicity == 'anual':
            month = 12
        elif periodicity == 'bimonthly':
            month = ((month - 1) // 2 + 1) * 2
        month += 1
        if month == 13:
            month, year = 1, year + 1
        return month, year

    def _resolve_due_date(self, month, year, today):
        table_code = self.obligation_type_id.seniat_table_code
        if table_code and table_code != 'none':
            if self.client_id.is_spe:
                return self._resolve_due_date_calendar(month, year)
            return self._resolve_day_15(month, year)
        rule = self.obligation_type_id.due_day_rule
        target_month, target_year = self._get_target_month(month, year)
        if rule == 'dia_fijo':
            day = self.obligation_type_id.due_day_value or 1
            return date(target_year, target_month, min(day, 28))
        if rule == '1-15':
            day = self._get_calendar_day(year, 'a1', month, self.client_id.rif_last_digit)
            if not day:
                return False
            return self._shift_to_next_banking_day(date(year, month, day))
        if rule == 'primeros_5_dias_habiles':
            return self._get_nth_business_day(target_year, target_month, 5)
        if rule == 'ultimo_digito_rif':
            digit = self.client_id.rif_last_digit
            day = 10 if digit == 0 else digit
            return date(target_year, target_month, day) if day else False
        return False

    def _resolve_due_date_calendar(self, month, year):
        self.ensure_one()
        if not any(character.isdigit() for character in (self.client_id.rif or '')):
            return False
        code = _quincena_table_code(
            self.obligation_type_id.periodicity,
            self.obligation_type_id.seniat_table_code,
            self.quincena,
        )
        day = self._get_calendar_day(year, code, month, self.client_id.rif_last_digit)
        if not day:
            return False
        offset = self._get_calendar_month_offset(year, code)
        target_year, target_month = _add_months(year, month, offset)
        if day > monthrange(target_year, target_month)[1]:
            return False
        return self._shift_to_next_banking_day(date(target_year, target_month, day))

    def _resolve_day_15(self, month, year):
        target_month, target_year = self._get_target_month(month, year)
        return self._shift_to_next_banking_day(date(target_year, target_month, 15))

    def _get_calendar_day(self, year, code, month, rif_digit):
        line = self.env['l10n.ve.seniat.calendar'].search([
            ('year', '=', year),
            ('table_id.code', '=', code),
            ('month', '=', month),
            ('rif_digit', '=', rif_digit),
        ], limit=1)
        return line.day if line else False

    def _get_calendar_month_offset(self, year, code):
        table = self.env['l10n.ve.seniat.calendar.table'].search([
            ('year', '=', year),
            ('code', '=', code),
        ], limit=1)
        return int(table.month_offset) if table else 0

    def _is_banking_day(self, day):
        if day.weekday() >= 5:
            return False
        holiday = self.env['l10n.ve.bank.holiday'].search([('date', '=', day)], limit=1)
        return not holiday

    def _shift_to_next_banking_day(self, day):
        while not self._is_banking_day(day):
            day += timedelta(days=1)
        return day

    def _get_nth_business_day(self, year, month, n):
        current = date(year, month, 1)
        count = 0
        while current.month == month:
            if current.weekday() < 5:
                count += 1
                if count == n:
                    return current
            current += timedelta(days=1)
        return False

    def _generate_obligation_alerts(self, today, now):
        for obligation in self:
            obligation_type = obligation.obligation_type_id
            client = obligation.client_id
            if not obligation_type or not client or not obligation_type.alert_enabled:
                continue
            if obligation.state == 'cancelled':
                continue
            if obligation.state == 'overdue':
                if obligation_type.alert_on_overdue:
                    self._create_alert(
                        client, obligation, 'overdue', obligation_type.alert_channel, now
                    )
                if obligation_type.alert_on_missing_payment and not obligation.payment_date:
                    self._create_alert(
                        client, obligation, 'missing_payment', obligation_type.alert_channel, now
                    )
            elif obligation.due_date:
                days_left = (obligation.due_date - today).days
                if 0 <= days_left <= obligation_type.alert_days_before:
                    self._create_alert(
                        client, obligation, 'due_soon', obligation_type.alert_channel, now
                    )

    def _get_alert_channels(self, channel):
        return {
            'email': ['email'],
            'whatsapp': ['whatsapp'],
            'both': ['email', 'whatsapp'],
        }.get(channel or 'email', ['email'])

    def _create_alert(self, client, obligation, alert_type, channel, now):
        alert_obj = self.env['l10n.ve.alert']
        recipients = client.accountant_id.partner_id
        if (obligation.obligation_type_id.alert_cc_client
                and client.partner_id
                and client.partner_id != recipients):
            recipients |= client.partner_id
        for channel_name in self._get_alert_channels(channel):
            exists = alert_obj.search([
                ('client_id', '=', client.id),
                ('obligation_id', '=', obligation.id),
                ('alert_type', '=', alert_type),
                ('channel', '=', channel_name),
                ('state', 'in', ('pending', 'sent')),
            ])
            if exists:
                continue
            message = f'Obligación: {obligation.name} (Período: {obligation.period})'
            if obligation.due_date:
                message += f' Vence: {obligation.due_date}'
            if obligation.amount:
                message += f' Monto: {obligation.amount} {obligation.currency_id.name}'
            alert = alert_obj.create({
                'name': f'{client.name} - {self.ALERT_TYPE_LABELS.get(alert_type, alert_type)} - {obligation.period}',
                'client_id': client.id,
                'obligation_id': obligation.id,
                'alert_type': alert_type,
                'date': now,
                'channel': channel_name,
                'recipient_ids': [(6, 0, recipients.ids)],
                'message': message,
            })
            self._send_alert(alert)

    def _send_alert(self, alert):
        if alert.channel == 'email':
            if alert._send_email():
                alert.write({
                    'state': 'sent',
                    'sent_date': fields.Datetime.now(),
                })
            return
        if alert.channel == 'whatsapp':
            partner = alert._get_wa_partner()
            if partner:
                link = alert.get_wa_url(partner.id)
                if link:
                    alert.message = f'{alert.message}\nWhatsApp: {link}'
            alert.write({
                'state': 'sent',
                'sent_date': fields.Datetime.now(),
            })

    @api.model
    def _cron_generate_obligations(self):
        """Generar las obligaciones del mes actual y el siguiente para todos los clientes."""
        clients = self.env['l10n.ve.compliance.client'].search([])
        for client in clients:
            self._generate_window_for_client(client)

    def _generate_window_for_client(self, client):
        today = fields.Date.today()
        months = [
            (today.year, today.month),
            _add_months(today.year, today.month, 1),
        ]
        created = 0
        for year, month in months:
            created += self._generate_for_client(client, year, month)
        return created

    def _generate_for_client(self, client, year, month):
        """Generar las obligaciones de un cliente para un período (RF-12)."""
        period = f'{month:02d}/{year}'
        created = 0
        for obligation_type in client.applicable_type_ids:
            periodicity = obligation_type.periodicity
            if periodicity == 'quincenal':
                if not client.is_spe:
                    continue
                for quincena in ('q1', 'q2'):
                    created += self._create_obligation_if_missing(
                        client, obligation_type, period, quincena, year
                    )
            elif periodicity == 'event':
                continue
            elif _last_period_month(periodicity, month):
                created += self._create_obligation_if_missing(
                    client, obligation_type, period, 'monthly', year
                )
        return created

    def _create_obligation_if_missing(self, client, obligation_type, period, quincena, year):
        existing = self.search([
            ('client_id', '=', client.id),
            ('obligation_type_id', '=', obligation_type.id),
            ('period', '=', period),
            ('quincena', '=', quincena),
        ], limit=1)
        if existing:
            return 0
        if not self._is_calendar_available(client, obligation_type, year, quincena):
            self._create_missing_calendar_alert(client, year)
            return 0
        self.create({
            'name': self._generate_obligation_name(obligation_type, period, quincena),
            'client_id': client.id,
            'obligation_type_id': obligation_type.id,
            'period': period,
            'quincena': quincena,
        })
        return 1

    def _generate_obligation_name(self, obligation_type, period, quincena):
        suffixes = {'q1': ' (1ra quincena)', 'q2': ' (2da quincena)'}
        return f'{obligation_type.name} {period}{suffixes.get(quincena, "")}'

    def _is_calendar_available(self, client, obligation_type, year, quincena):
        table_code = obligation_type.seniat_table_code
        if not client.is_spe or not table_code or table_code == 'none':
            return True
        code = _quincena_table_code(obligation_type.periodicity, table_code, quincena)
        table = self.env['l10n.ve.seniat.calendar.table'].search([
            ('year', '=', year),
            ('code', '=', code),
        ], limit=1)
        return bool(table)

    def _create_missing_calendar_alert(self, client, year):
        alert_obj = self.env['l10n.ve.alert']
        alert_name = f'{client.name} — Calendario SENIAT {year} faltante'
        existing = alert_obj.search([
            ('client_id', '=', client.id),
            ('alert_type', '=', 'calendar_missing'),
            ('name', '=', alert_name),
            ('state', 'in', ('pending', 'sent')),
        ], limit=1)
        if existing:
            return existing
        return alert_obj.create({
            'name': alert_name,
            'client_id': client.id,
            'alert_type': 'calendar_missing',
            'date': fields.Datetime.now(),
            'channel': 'email',
            'recipient_ids': [(6, 0, client.accountant_id.partner_id.ids)],
            'message': (
                f'El calendario SENIAT del año {year} no está cargado: no se '
                f'generaron las obligaciones que dependen de él. Cargue el '
                f'calendario para continuar con {client.name}.'
            ),
        })
