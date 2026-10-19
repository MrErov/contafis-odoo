from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestObligation(TransactionCase):

    def _create_client(self, name, rif):
        partner = self.env['res.partner'].create({'name': name})
        return self.env['l10n.ve.compliance.client'].create({
            'name': name,
            'partner_id': partner.id,
            'company_id': self.env.company.id,
            'rif': rif,
        })

    def _create_institution(self):
        return self.env['l10n.ve.institution'].create({
            'name': 'SENIAT Test',
            'type': 'seniat',
        })

    def _create_obligation_type(self, due_day_rule='1-15', alert_enabled=False,
                                alert_days_before=0, alert_on_overdue=False,
                                alert_on_missing_payment=False, alert_channel='email'):
        return self.env['l10n.ve.obligation.type'].create({
            'name': 'IVA Test',
            'institution_id': self._create_institution().id,
            'category': 'fiscal_nacional',
            'tax_type': 'iva',
            'periodicity': 'monthly',
            'due_day_rule': due_day_rule,
            'alert_enabled': alert_enabled,
            'alert_days_before': alert_days_before,
            'alert_on_overdue': alert_on_overdue,
            'alert_on_missing_payment': alert_on_missing_payment,
            'alert_channel': alert_channel,
        })

    def _create_obligation(self, client, obligation_type, period=False):
        return self.env['l10n.ve.obligation'].create({
            'name': f'OBL-TEST-{obligation_type.name}',
            'client_id': client.id,
            'obligation_type_id': obligation_type.id,
            'period': period or '',
        })

    def test_compute_due_date_seniat(self):
        client_0 = self._create_client('Cliente 0', 'J-00000000-0')
        client_1 = self._create_client('Cliente 1', 'J-00000001-1')
        obligation_type = self._create_obligation_type()

        ob_0 = self._create_obligation(client_0, obligation_type, '01/2026')
        ob_1 = self._create_obligation(client_1, obligation_type, '01/2026')

        self.assertEqual(ob_0.due_date, fields.Date.to_date('2026-01-28'))
        self.assertEqual(ob_1.due_date, fields.Date.to_date('2026-01-19'))

    def test_recompute_due_date_on_change_when_unpaid(self):
        client_0 = self._create_client('Cliente 0 Recalculo', 'J-00000000-0')
        client_1 = self._create_client('Cliente 1 Recalculo', 'J-00000001-1')
        obligation_type = self._create_obligation_type()
        fixed_type = self._create_obligation_type(due_day_rule='dia_fijo')

        obligation = self._create_obligation(client_0, obligation_type, '01/2026')
        self.assertEqual(obligation.due_date, fields.Date.to_date('2026-01-28'))

        obligation.client_id = client_1
        self.assertEqual(obligation.due_date, fields.Date.to_date('2026-01-19'))

        obligation.obligation_type_id = fixed_type
        self.assertEqual(obligation.due_date, fields.Date.to_date('2026-02-01'))

        obligation.state = 'overdue'
        obligation.obligation_type_id = obligation_type
        self.assertEqual(obligation.due_date, fields.Date.to_date('2026-01-19'))

    def test_keep_due_date_on_change_when_paid(self):
        client_0 = self._create_client('Cliente 0 Pagado', 'J-00000000-0')
        client_1 = self._create_client('Cliente 1 Pagado', 'J-00000001-1')
        obligation_type = self._create_obligation_type()
        fixed_type = self._create_obligation_type(due_day_rule='dia_fijo')

        obligation = self._create_obligation(client_0, obligation_type, '01/2026')
        obligation.state = 'paid'
        self.assertEqual(obligation.due_date, fields.Date.to_date('2026-01-28'))

        obligation.client_id = client_1
        obligation.obligation_type_id = fixed_type
        self.assertEqual(obligation.due_date, fields.Date.to_date('2026-01-28'))

    def test_cron_generate_alerts(self):
        client = self._create_client('Cliente Cron', 'J-00000003-3')
        obligation_type = self._create_obligation_type(
            alert_enabled=True,
            alert_days_before=5,
            alert_on_overdue=True,
            alert_on_missing_payment=True,
        )
        today = fields.Date.today()

        due_soon = self._create_obligation(client, obligation_type)
        due_soon.due_date = today + timedelta(days=3)
        overdue = self._create_obligation(client, obligation_type)
        overdue.due_date = today - timedelta(days=1)

        self.env['l10n.ve.obligation']._cron_generate_compliance_alerts()

        self.assertEqual(overdue.state, 'overdue')
        due_soon_alerts = self.env['l10n.ve.alert'].search([
            ('obligation_id', '=', due_soon.id),
            ('alert_type', '=', 'due_soon'),
        ])
        self.assertTrue(due_soon_alerts)
        overdue_alerts = self.env['l10n.ve.alert'].search([
            ('obligation_id', '=', overdue.id),
            ('alert_type', '=', 'overdue'),
        ])
        self.assertTrue(overdue_alerts)
        missing_payment_alerts = self.env['l10n.ve.alert'].search([
            ('obligation_id', '=', overdue.id),
            ('alert_type', '=', 'missing_payment'),
        ])
        self.assertTrue(missing_payment_alerts)

    def test_compliance_score(self):
        client = self._create_client('Cliente Score', 'J-00000005-5')
        obligation_type = self._create_obligation_type()

        paid = self._create_obligation(client, obligation_type)
        paid.state = 'paid'
        future = self._create_obligation(client, obligation_type)
        future.due_date = fields.Date.today() + timedelta(days=7)

        self.assertEqual(client.compliance_score, 100.0)

        overdue = self._create_obligation(client, obligation_type)
        overdue.due_date = fields.Date.today() - timedelta(days=7)

        self.assertEqual(client.compliance_score, 66.67)

        overdue.state = 'cancelled'
        self.assertEqual(client.compliance_score, 100.0)

        empty_client = self._create_client('Cliente Vacio', 'J-00000006-6')
        self.assertEqual(empty_client.compliance_score, 100.0)
        self.assertTrue(0 <= client.compliance_score <= 100)

    def test_generate_retention(self):
        partner = self.env['res.partner'].create({'name': 'Proveedor Test'})
        journal = self.env['account.journal'].create({
            'name': 'Facturas Proveedor',
            'type': 'purchase',
            'code': 'TSTPUR',
        })
        expense_account = self.env['account.account'].create({
            'name': 'Gastos Test',
            'code': 'TSTEXP',
            'account_type': 'expense',
        })
        payable_account = self.env['account.account'].create({
            'name': 'Cuentas por Pagar Test',
            'code': 'TSTPAY',
            'account_type': 'liability_payable',
        })
        partner.property_account_payable_id = payable_account
        move = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': partner.id,
            'journal_id': journal.id,
            'invoice_date': fields.Date.to_date('2026-01-15'),
            'invoice_line_ids': [(0, 0, {
                'name': 'Servicio Test',
                'quantity': 1,
                'price_unit': 100.0,
                'account_id': expense_account.id,
            })],
        })

        self.assertEqual(move.amount_untaxed, 100.0)
        move.action_generate_retention()

        self.assertEqual(len(move.retention_ids), 1)
        self.assertEqual(move.retention_ids.amount, 3.0)
        self.assertEqual(move.retention_ids.invoice_id, move)

    def test_document_expiry(self):
        client = self._create_client('Cliente Doc', 'J-00000002-2')
        institution = self._create_institution()
        document_type = self.env['l10n.ve.document.type'].create({
            'name': 'RIF Test',
            'code': 'RIF-TEST',
            'institution_id': institution.id,
            'validity_days': 0,
            'renewal_alert_days': 30,
            'required_for': 'company',
            'alert_channel': 'email',
        })
        document = self.env['l10n.ve.document'].create({
            'client_id': client.id,
            'document_type_id': document_type.id,
            'number': 'RIF-123',
            'expiry_date': fields.Date.today() - timedelta(days=1),
            'state': 'valid',
        })

        self.env['l10n.ve.obligation']._cron_generate_compliance_alerts()

        self.assertEqual(document.state, 'expired')
