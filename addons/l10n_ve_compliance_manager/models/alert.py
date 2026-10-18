import re
from urllib.parse import quote

from odoo import fields, models


class VeAlert(models.Model):
    _name = 'l10n.ve.alert'
    _description = 'Alerta'

    name = fields.Char(string='Nombre', required=True)
    client_id = fields.Many2one('l10n.ve.compliance.client', string='Cliente')
    obligation_id = fields.Many2one('l10n.ve.obligation', string='Obligación')
    document_id = fields.Many2one('l10n.ve.document', string='Documento')
    alert_type = fields.Selection([
        ('due_soon', 'Vence pronto'),
        ('overdue', 'Vencida'),
        ('missing_payment', 'Falta de pago'),
        ('document_expiring', 'Documento por vencer'),
        ('document_missing', 'Documento faltante'),
        ('calendar_missing', 'Calendario faltante'),
    ], string='Tipo de alerta')
    date = fields.Datetime(string='Fecha')
    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('sent', 'Enviada'),
        ('done', 'Hecha'),
    ], string='Estado', default='pending')
    channel = fields.Selection([
        ('email', 'Email'),
        ('whatsapp', 'WhatsApp'),
    ], string='Canal')
    recipient_ids = fields.Many2many('res.partner', string='Destinatarios')
    message = fields.Text(string='Mensaje')
    sent_date = fields.Datetime(string='Fecha de envío')

    def _get_wa_text(self):
        self.ensure_one()
        parts = ['Alerta de cumplimiento: {}'.format(self.client_id.name or '')]
        parts.append(f'Tipo: {self.alert_type}')
        if self.obligation_id:
            parts.append(
                f'Obligación: {self.obligation_id.name} (Período: {self.obligation_id.period})'
            )
            if self.obligation_id.due_date:
                parts.append(f'Vence: {self.obligation_id.due_date}')
            if self.obligation_id.amount:
                parts.append(
                    f'Monto: {self.obligation_id.amount} {self.obligation_id.currency_id.name}'
                )
        if self.document_id:
            parts.append(
                'Documento: {} (Vence: {})'.format(
                    self.document_id.number or '', self.document_id.expiry_date
                )
            )
        return ' - '.join(part for part in parts if part)

    def get_wa_url(self, partner):
        self.ensure_one()
        partner = self.env['res.partner'].browse(partner)
        phone = ''.join(re.findall(r'\d+', partner.phone or ''))
        if not phone:
            return False
        return f'https://wa.me/{phone}?text={quote(self._get_wa_text())}'

    def _get_wa_partner(self):
        """Partner cuyo teléfono alimenta el link wa.me.

        El teléfono del contador asignado tiene prioridad; si el cliente no
        tiene contador, se usa el primer destinatario disponible. El orden de
        un Many2many se rige por `_order` de res.partner, por lo que no se
        puede confiar en `recipient_ids[0]`.
        """
        self.ensure_one()
        accountant_partner = self.client_id.accountant_id.partner_id
        if accountant_partner:
            return accountant_partner
        return self.recipient_ids[:1]

    def _send_email(self):
        """Enviar la alerta por email con la plantilla del módulo (RF-16).

        Devuelve False (y deja la alerta pendiente) cuando ningún
        destinatario tiene email, para no romper el cron.
        """
        self.ensure_one()
        if not self.recipient_ids.filtered('email'):
            return False
        template = self.env.ref(
            'l10n_ve_compliance_manager.email_template_l10n_ve_alert',
            raise_if_not_found=False,
        )
        if not template:
            return False
        template.send_mail(self.id, force_send=False)
        return True
