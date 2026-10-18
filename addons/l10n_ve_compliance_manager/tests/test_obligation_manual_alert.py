from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestObligationManualAlert(TransactionCase):
    """Alerta manual a demanda desde bandeja/formulario (spec 005, T3)."""

    def _create_accountant(self, phone=False, email=False):
        user = self.env['res.users'].create({
            'name': 'Contador Manual',
            'login': 'contador_manual',
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('account.group_account_user').id,
            ])],
        })
        user.partner_id.write({'phone': phone, 'email': email})
        return user

    def _create_client(self, accountant=None):
        partner = self.env['res.partner'].create({
            'name': 'Cliente Alerta Manual',
            'phone': '+58 424-9999999',
        })
        return self.env['l10n.ve.compliance.client'].create({
            'name': 'Cliente Alerta Manual',
            'partner_id': partner.id,
            'company_id': self.env.company.id,
            'rif': 'J-30000003-6',
            'accountant_id': accountant.id if accountant else False,
        })

    def _create_obligation_type(self, alert_channel='whatsapp', alert_cc_client=False):
        institution = self.env['l10n.ve.institution'].create({
            'name': 'SENIAT Test Alerta',
            'type': 'seniat',
        })
        return self.env['l10n.ve.obligation.type'].create({
            'name': 'IVA Test Alerta',
            'institution_id': institution.id,
            'category': 'fiscal_nacional',
            'tax_type': 'iva',
            'periodicity': 'monthly',
            'due_day_rule': '1-15',
            'alert_channel': alert_channel,
            'alert_cc_client': alert_cc_client,
        })

    def _create_obligation(self, obligation_type, client=None, **values):
        vals = {
            'name': 'OBL-ALERT-001',
            'client_id': (client or self._create_client()).id,
            'obligation_type_id': obligation_type.id,
        }
        vals.update(values)
        obligation = self.env['l10n.ve.obligation'].create(vals)
        if 'due_date' not in values:
            obligation.due_date = fields.Date.today() + timedelta(days=5)
        return obligation

    def test_creates_whatsapp_alert_with_link_and_cc(self):
        accountant = self._create_accountant(
            phone='+58 412-1234567', email='contador@example.com',
        )
        client = self._create_client(accountant=accountant)
        obligation_type = self._create_obligation_type(
            alert_channel='whatsapp', alert_cc_client=True,
        )
        obligation = self._create_obligation(obligation_type, client=client)

        result = obligation.action_create_manual_alert()

        alerts = self.env['l10n.ve.alert'].search([
            ('obligation_id', '=', obligation.id),
        ])
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts.alert_type, 'manual')
        self.assertEqual(alerts.channel, 'whatsapp')
        self.assertEqual(alerts.state, 'sent')
        self.assertEqual(alerts.client_id, client)
        self.assertIn(accountant.partner_id, alerts.recipient_ids)
        self.assertIn(client.partner_id, alerts.recipient_ids)
        self.assertIn(
            'https://wa.me/584121234567?text=', alerts.message,
            'El link wa.me debe apuntar al teléfono del contador',
        )
        self.assertEqual(result['params']['type'], 'success')
        self.assertEqual(result['params']['message'], 'Alerta manual creada y enviada.')

    def test_dedupe_blocks_pending_duplicate(self):
        accountant = self._create_accountant(phone='+58 412-1234567')
        client = self._create_client(accountant=accountant)
        obligation = self._create_obligation(
            self._create_obligation_type(), client=client,
        )
        self.env['l10n.ve.alert'].create({
            'name': 'Alerta previa',
            'client_id': client.id,
            'obligation_id': obligation.id,
            'alert_type': 'manual',
            'channel': 'whatsapp',
            'state': 'pending',
        })

        result = obligation.action_create_manual_alert()

        alerts = self.env['l10n.ve.alert'].search([
            ('obligation_id', '=', obligation.id),
        ])
        self.assertEqual(len(alerts), 1, 'No debe duplicar la alerta vigente')
        self.assertEqual(result['params']['type'], 'warning')
        self.assertIn('no se duplicó', result['params']['message'])

    def test_allows_new_after_done(self):
        accountant = self._create_accountant(phone='+58 412-1234567')
        client = self._create_client(accountant=accountant)
        obligation = self._create_obligation(
            self._create_obligation_type(), client=client,
        )
        self.env['l10n.ve.alert'].create({
            'name': 'Alerta cerrada',
            'client_id': client.id,
            'obligation_id': obligation.id,
            'alert_type': 'manual',
            'channel': 'whatsapp',
            'state': 'done',
        })

        result = obligation.action_create_manual_alert()

        alerts = self.env['l10n.ve.alert'].search([
            ('obligation_id', '=', obligation.id),
        ])
        self.assertEqual(len(alerts), 2, 'Una alerta cerrada permite reenviar')
        self.assertEqual(
            alerts.filtered(lambda alert: alert.state == 'sent').mapped('channel'),
            ['whatsapp'],
        )
        self.assertEqual(result['params']['type'], 'success')

    def test_email_without_address_stays_pending(self):
        accountant = self._create_accountant(phone=False, email=False)
        client = self._create_client(accountant=accountant)
        obligation = self._create_obligation(
            self._create_obligation_type(alert_channel='email'), client=client,
        )

        result = obligation.action_create_manual_alert()

        alert = self.env['l10n.ve.alert'].search([
            ('obligation_id', '=', obligation.id),
        ])
        self.assertEqual(len(alert), 1)
        self.assertEqual(alert.state, 'pending')
        self.assertIn('pendiente', result['params']['message'])

    def test_requires_client(self):
        obligation = self._create_obligation(self._create_obligation_type())
        obligation.client_id = False

        with self.assertRaises(UserError):
            obligation.action_create_manual_alert()

    def test_form_wrapper_adds_reload_next(self):
        accountant = self._create_accountant(phone='+58 412-1234567')
        client = self._create_client(accountant=accountant)
        obligation = self._create_obligation(
            self._create_obligation_type(), client=client,
        )

        result = obligation.action_create_manual_alert_and_refresh()

        self.assertEqual(
            result['params']['next'],
            {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            'El botón del formulario debe recargar la vista sin navegar',
        )

    def test_views_have_manual_alert_buttons(self):
        tray_view = self.env.ref(
            'l10n_ve_compliance_manager.view_l10n_ve_obligation_due_soon_list'
        )
        form_view = self.env.ref(
            'l10n_ve_compliance_manager.view_l10n_ve_obligation_form'
        )

        self.assertIn('action_create_manual_alert"', tray_view.arch)
        self.assertIn('action_create_manual_alert_and_refresh', form_view.arch)
