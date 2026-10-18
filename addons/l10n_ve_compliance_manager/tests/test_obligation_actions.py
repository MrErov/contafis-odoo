from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestObligationActions(TransactionCase):
    """Acciones de la bandeja: marcar pagada y reabrir (spec 005, T1)."""

    def _create_client(self, name, rif):
        partner = self.env['res.partner'].create({'name': name})
        return self.env['l10n.ve.compliance.client'].create({
            'name': name,
            'partner_id': partner.id,
            'company_id': self.env.company.id,
            'rif': rif,
        })

    def _create_obligation_type(self):
        institution = self.env['l10n.ve.institution'].create({
            'name': 'SENIAT Test Acciones',
            'type': 'seniat',
        })
        return self.env['l10n.ve.obligation.type'].create({
            'name': 'IVA Test Acciones',
            'institution_id': institution.id,
            'category': 'fiscal_nacional',
            'tax_type': 'iva',
            'periodicity': 'monthly',
            'due_day_rule': '1-15',
        })

    def _create_obligation(self, obligation_type, **values):
        client = self._create_client('Cliente Acciones', 'J-30000001-0')
        vals = {
            'name': 'OBL-ACC-001',
            'client_id': client.id,
            'obligation_type_id': obligation_type.id,
        }
        vals.update(values)
        return self.env['l10n.ve.obligation'].create(vals)

    def test_mark_paid_sets_state_and_payment_date(self):
        obligation_type = self._create_obligation_type()
        obligation = self._create_obligation(obligation_type)
        obligation.due_date = fields.Date.today() + timedelta(days=5)

        result = obligation.action_mark_paid()

        self.assertTrue(result)
        self.assertEqual(obligation.state, 'paid')
        self.assertEqual(obligation.payment_date, fields.Date.today())

    def test_mark_paid_bulk_mixed_states(self):
        obligation_type = self._create_obligation_type()
        today = fields.Date.today()
        pending = self._create_obligation(obligation_type)
        pending.due_date = today + timedelta(days=7)
        existing_date = today - timedelta(days=2)
        with_date = self._create_obligation(
            obligation_type, payment_date=existing_date,
        )
        with_date.due_date = today + timedelta(days=3)
        cancelled = self._create_obligation(obligation_type, state='cancelled')
        already_paid = self._create_obligation(
            obligation_type, state='paid', payment_date=existing_date,
        )

        result = (pending | with_date | cancelled | already_paid).action_mark_paid()

        self.assertTrue(result)
        self.assertEqual(pending.state, 'paid')
        self.assertEqual(pending.payment_date, today)
        self.assertEqual(with_date.state, 'paid')
        self.assertEqual(
            with_date.payment_date, existing_date,
            'La fecha de pago existente no debe pisarse',
        )
        self.assertEqual(cancelled.state, 'cancelled')
        self.assertEqual(already_paid.payment_date, existing_date)

    def test_mark_paid_overdue_allowed(self):
        obligation_type = self._create_obligation_type()
        obligation = self._create_obligation(obligation_type, state='overdue')
        obligation.due_date = fields.Date.today() - timedelta(days=4)

        obligation.action_mark_paid()

        self.assertEqual(obligation.state, 'paid')
        self.assertEqual(obligation.payment_date, fields.Date.today())

    def test_reopen_before_due_sets_pending_and_clears_payment(self):
        obligation_type = self._create_obligation_type()
        obligation = self._create_obligation(
            obligation_type,
            state='paid',
            payment_date=fields.Date.today(),
            payment_reference='REF-001',
            payment_attachment=b'ZmlsZQ==',
        )
        obligation.due_date = fields.Date.today() + timedelta(days=10)

        result = obligation.action_reopen()

        self.assertTrue(result)
        self.assertEqual(obligation.state, 'pending')
        self.assertFalse(obligation.payment_date)
        self.assertFalse(obligation.payment_reference)
        self.assertEqual(
            obligation.payment_attachment, b'ZmlsZQ==',
            'El comprobante debe conservarse al reabrir',
        )

    def test_reopen_after_due_sets_overdue(self):
        obligation_type = self._create_obligation_type()
        obligation = self._create_obligation(obligation_type, state='paid')
        obligation.due_date = fields.Date.today() - timedelta(days=2)

        obligation.action_reopen()

        self.assertEqual(obligation.state, 'overdue')

    def test_reopen_ignores_non_paid(self):
        obligation_type = self._create_obligation_type()
        obligation = self._create_obligation(obligation_type)

        result = obligation.action_reopen()

        self.assertTrue(result)
        self.assertEqual(obligation.state, 'pending')
