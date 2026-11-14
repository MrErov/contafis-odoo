from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestActionPaths(TransactionCase):
    """Regresión: Odoo 19 usa action.path para construir URLs legibles.

    Sin path, el menú enlaza a /odoo/action-<id>; con path, a /odoo/<slug>.
    """

    def test_custom_actions_have_a_unique_path(self):
        data = self.env['ir.model.data'].search([
            ('module', '=', 'l10n_ve_compliance_manager'),
            ('model', '=', 'ir.actions.act_window'),
        ])
        actions = self.env['ir.actions.act_window'].browse(data.mapped('res_id'))

        missing = actions.filtered(lambda action: not action.path)
        self.assertFalse(
            missing,
            f'Acciones sin path: {missing.mapped("name")}',
        )
        self.assertEqual(
            len(set(actions.mapped('path'))),
            len(actions),
            'Cada acción debe tener un path único.',
        )
