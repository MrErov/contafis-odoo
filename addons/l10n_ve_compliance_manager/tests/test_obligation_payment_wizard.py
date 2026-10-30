from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.orm.fields_binary import BinaryBytes
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestObligationPaymentWizard(TransactionCase):
    """Wizard Registrar pago de la bandeja (spec 005, T2)."""

    def _create_client(self, accountant=None):
        partner = self.env['res.partner'].create({'name': 'Cliente Pago'})
        return self.env['l10n.ve.compliance.client'].create({
            'name': 'Cliente Pago',
            'partner_id': partner.id,
            'company_id': self.env.company.id,
            'rif': 'J-30000002-8',
            'accountant_id': accountant.id if accountant else False,
        })

    def _create_obligation_type(self):
        institution = self.env['l10n.ve.institution'].create({
            'name': 'SENIAT Test Pago',
            'type': 'seniat',
        })
        return self.env['l10n.ve.obligation.type'].create({
            'name': 'IVA Test Pago',
            'institution_id': institution.id,
            'category': 'fiscal_nacional',
            'tax_type': 'iva',
            'periodicity': 'monthly',
            'due_day_rule': '1-15',
        })

    def _create_obligation(self, obligation_type, client=None, **values):
        vals = {
            'name': 'OBL-PAY-001',
            'client_id': (client or self._create_client()).id,
            'obligation_type_id': obligation_type.id,
        }
        vals.update(values)
        return self.env['l10n.ve.obligation'].create(vals)

    def test_wizard_defaults_and_confirm(self):
        obligation = self._create_obligation(self._create_obligation_type())
        obligation.due_date = fields.Date.today() + timedelta(days=4)

        wizard = self.env['l10n.ve.obligation.payment.wizard'].create({
            'obligation_id': obligation.id,
        })

        self.assertEqual(wizard.payment_date, fields.Date.today())

        wizard.payment_reference = 'REF-123'
        wizard.payment_attachment = BinaryBytes(b'ZmlsZQ==')
        result = wizard.action_confirm()

        self.assertEqual(obligation.state, 'paid')
        self.assertEqual(obligation.payment_date, fields.Date.today())
        self.assertEqual(obligation.payment_reference, 'REF-123')
        self.assertEqual(obligation.payment_attachment, b'ZmlsZQ==')
        self.assertEqual(result['tag'], 'display_notification')
        self.assertEqual(
            result['params']['message'],
            'Se registró el pago de la obligación.',
        )
        self.assertEqual(
            result['params']['next'], {'type': 'ir.actions.act_window_close'},
            'El diálogo debe cerrarse al confirmar',
        )

    def test_wizard_custom_payment_date_and_empty_optionals(self):
        obligation = self._create_obligation(self._create_obligation_type())
        obligation.due_date = fields.Date.today() + timedelta(days=4)
        custom_date = fields.Date.today() - timedelta(days=3)

        wizard = self.env['l10n.ve.obligation.payment.wizard'].create({
            'obligation_id': obligation.id,
            'payment_date': custom_date,
        })
        wizard.action_confirm()

        self.assertEqual(obligation.state, 'paid')
        self.assertEqual(obligation.payment_date, custom_date)
        self.assertFalse(obligation.payment_reference)

    def test_wizard_rejects_non_eligible_state(self):
        obligation = self._create_obligation(
            self._create_obligation_type(), state='paid',
        )
        wizard = self.env['l10n.ve.obligation.payment.wizard'].create({
            'obligation_id': obligation.id,
        })

        with self.assertRaises(UserError):
            wizard.action_confirm()

    def test_action_open_payment_wizard_context(self):
        obligation = self._create_obligation(self._create_obligation_type())

        action = obligation.action_open_payment_wizard()

        self.assertEqual(action['res_model'], 'l10n.ve.obligation.payment.wizard')
        self.assertEqual(action['target'], 'new')
        self.assertEqual(
            action['context']['default_obligation_id'], obligation.id,
        )

    def test_readonly_user_gets_access_error(self):
        readonly_user = self.env['res.users'].create({
            'name': 'Solo Lectura Pago',
            'login': 'readonly_payment',
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('account.group_account_user').id,
            ])],
        })
        client = self._create_client(accountant=readonly_user)
        obligation = self._create_obligation(
            self._create_obligation_type(), client=client,
        )
        obligation.due_date = fields.Date.today() + timedelta(days=4)

        visible = self.env['l10n.ve.obligation'].with_user(readonly_user).search([
            ('id', '=', obligation.id),
        ])
        self.assertEqual(visible.ids, [obligation.id])

        wizard = self.env['l10n.ve.obligation.payment.wizard'].with_user(
            readonly_user,
        ).create({'obligation_id': obligation.id})

        with self.assertRaises(AccessError):
            wizard.action_confirm()

    def test_views_have_tray_and_header_buttons(self):
        tray_view = self.env.ref(
            'l10n_ve_compliance_manager.view_l10n_ve_obligation_due_soon_list'
        )
        form_view = self.env.ref(
            'l10n_ve_compliance_manager.view_l10n_ve_obligation_form'
        )

        self.assertIn('action_open_payment_wizard', tray_view.arch)
        self.assertIn('action_open_payment_wizard', form_view.arch)
        self.assertIn('action_reopen', form_view.arch)
