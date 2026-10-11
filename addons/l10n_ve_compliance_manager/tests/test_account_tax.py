from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAccountTaxL10nVeType(TransactionCase):

    def test_account_tax_l10n_ve_type_field(self):
        """Verifica que account.tax tiene campo l10n_ve_tax_type con valores correctos."""
        model = self.env['account.tax']
        field = model._fields.get('l10n_ve_tax_type')
        self.assertIsNotNone(field, "Campo l10n_ve_tax_type no existe en account.tax")
        self.assertEqual(field.type, 'selection', "l10n_ve_tax_type debe ser Selection")

        # Verificar que tiene los 8 valores esperados
        selection_values = dict(field.selection)
        expected_values = {
            'general', 'reduced', 'additional', 'no_credit',
            'exempt', 'not_subject', 'import', 'non_contrib'
        }
        self.assertEqual(set(selection_values.keys()), expected_values,
                         f"Valores esperados: {expected_values}, encontrados: {set(selection_values.keys())}")

        # Verificar que se puede crear un tax con cada valor
        for val in expected_values:
            tax = self.env['account.tax'].create({
                'name': f'Test Tax {val}',
                'amount_type': 'percent',
                'amount': 16.0,
                'l10n_ve_tax_type': val,
            })
            self.assertEqual(tax.l10n_ve_tax_type, val)
            tax.unlink()
