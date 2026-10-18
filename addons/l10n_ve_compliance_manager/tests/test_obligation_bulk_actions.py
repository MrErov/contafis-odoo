from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestObligationBulkActions(TransactionCase):
    """Acciones masivas y vistas de análisis (spec 005, T4)."""

    def _create_client(self):
        partner = self.env['res.partner'].create({'name': 'Cliente Masivo'})
        return self.env['l10n.ve.compliance.client'].create({
            'name': 'Cliente Masivo',
            'partner_id': partner.id,
            'company_id': self.env.company.id,
            'rif': 'J-30000004-4',
        })

    def _create_obligation_type(self):
        institution = self.env['l10n.ve.institution'].create({
            'name': 'SENIAT Test Masivo',
            'type': 'seniat',
        })
        return self.env['l10n.ve.obligation.type'].create({
            'name': 'IVA Test Masivo',
            'institution_id': institution.id,
            'category': 'fiscal_nacional',
            'tax_type': 'iva',
            'periodicity': 'monthly',
            'due_day_rule': '1-15',
        })

    def _create_obligation(self, obligation_type, **values):
        client = self._create_client()
        vals = {
            'name': 'OBL-BULK-001',
            'client_id': client.id,
            'obligation_type_id': obligation_type.id,
        }
        vals.update(values)
        obligation = self.env['l10n.ve.obligation'].create(vals)
        if 'due_date' not in values:
            obligation.due_date = fields.Date.today() + timedelta(days=6)
        return obligation

    def _run_server_action(self, xmlid, obligations):
        action = self.env.ref(xmlid).with_context(
            active_model='l10n.ve.obligation',
            active_ids=obligations.ids,
        )
        return action.run()

    def test_mark_paid_server_action_reports_counts(self):
        obligation_type = self._create_obligation_type()
        first = self._create_obligation(obligation_type)
        second = self._create_obligation(obligation_type)
        cancelled = self._create_obligation(obligation_type, state='cancelled')

        result = self._run_server_action(
            'l10n_ve_compliance_manager.action_server_obligation_mark_paid',
            first | second | cancelled,
        )

        self.assertEqual(first.state, 'paid')
        self.assertEqual(second.state, 'paid')
        self.assertEqual(first.payment_date, fields.Date.today())
        self.assertEqual(cancelled.state, 'cancelled')
        self.assertEqual(result['tag'], 'display_notification')
        self.assertEqual(
            result['params']['message'],
            'Se marcaron 2 obligación(es) como pagadas. 1 quedaron fuera por su estado.',
        )
        self.assertEqual(
            result['params']['next'],
            {'type': 'ir.actions.client', 'tag': 'soft_reload'},
        )

    def test_reopen_server_action_reports_counts(self):
        obligation_type = self._create_obligation_type()
        paid = self._create_obligation(obligation_type, state='paid')
        paid.payment_date = fields.Date.today()
        pending = self._create_obligation(obligation_type)

        result = self._run_server_action(
            'l10n_ve_compliance_manager.action_server_obligation_reopen',
            paid | pending,
        )

        self.assertEqual(paid.state, 'pending')
        self.assertFalse(paid.payment_date)
        self.assertEqual(pending.state, 'pending')
        self.assertEqual(
            result['params']['message'],
            'Se reabrieron 1 obligación(es). 1 quedaron fuera por su estado.',
        )

    def test_analysis_views_load(self):
        obligation_graph = self.env.ref(
            'l10n_ve_compliance_manager.view_l10n_ve_obligation_graph'
        )
        obligation_pivot = self.env.ref(
            'l10n_ve_compliance_manager.view_l10n_ve_obligation_pivot'
        )
        alert_graph = self.env.ref(
            'l10n_ve_compliance_manager.view_l10n_ve_alert_graph'
        )
        alert_pivot = self.env.ref(
            'l10n_ve_compliance_manager.view_l10n_ve_alert_pivot'
        )

        self.assertIn('<graph', obligation_graph.arch)
        self.assertIn('amount', obligation_graph.arch)
        self.assertIn('<pivot', obligation_pivot.arch)
        self.assertIn('<graph', alert_graph.arch)
        self.assertIn('<pivot', alert_pivot.arch)

        self.env['l10n.ve.obligation'].get_view(
            obligation_graph.id, 'graph',
        )
        self.env['l10n.ve.obligation'].get_view(
            obligation_pivot.id, 'pivot',
        )
        self.env['l10n.ve.alert'].get_view(alert_graph.id, 'graph')
        self.env['l10n.ve.alert'].get_view(alert_pivot.id, 'pivot')

    def test_analysis_actions_and_menu(self):
        obligation_action = self.env.ref(
            'l10n_ve_compliance_manager.action_l10n_ve_obligation_analysis'
        )
        alert_action = self.env.ref(
            'l10n_ve_compliance_manager.action_l10n_ve_alert_analysis'
        )

        self.assertEqual(obligation_action.view_mode, 'graph,pivot,list')
        self.assertEqual(alert_action.view_mode, 'graph,pivot,list')
        self.assertEqual(obligation_action.res_model, 'l10n.ve.obligation')
        self.assertEqual(alert_action.res_model, 'l10n.ve.alert')

        menu = self.env.ref(
            'l10n_ve_compliance_manager.menu_l10n_ve_compliance_analysis'
        )
        menu_obligations = self.env.ref(
            'l10n_ve_compliance_manager.menu_l10n_ve_compliance_analysis_obligations'
        )
        menu_alerts = self.env.ref(
            'l10n_ve_compliance_manager.menu_l10n_ve_compliance_analysis_alerts'
        )

        self.assertEqual(menu_obligations.parent_id, menu)
        self.assertEqual(menu_alerts.parent_id, menu)
        self.assertEqual(menu_obligations.action, obligation_action)
        self.assertEqual(menu_alerts.action, alert_action)
