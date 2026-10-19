class TaxGroupMixin:
    """Helper compartido para obtener/crear el grupo de impuestos de la compañía."""

    def _get_or_create_tax_group(self):
        company = getattr(self, 'company', self.env.company)
        country = self.country
        group = self.env['account.tax.group'].search([
            ('company_id', '=', company.id)
        ], limit=1)
        if not group:
            group = self.env['account.tax.group'].create({
                'name': 'IVA', 'country_id': country.id,
            })
        else:
            if group.country_id and group.country_id.id != country.id:
                group.write({'country_id': country.id})
            if 'IVA' not in (group.name or '').upper():
                group.write({'name': 'IVA'})
        return group
