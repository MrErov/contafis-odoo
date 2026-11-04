class TaxGroupMixin:
    """Helper compartido para obtener/crear el grupo de impuestos de la compañía."""

    #: Impuestos SENIAT que el asistente de factura física necesita.
    VAT_TAX_DEFINITIONS = (
        ('general', 16.0, 'purchase', 'IVA General 16% (Compra)'),
        ('general', 16.0, 'sale', 'IVA General 16% (Venta)'),
        ('reduced', 8.0, 'purchase', 'IVA Reducida 8% (Compra)'),
        ('reduced', 8.0, 'sale', 'IVA Reducida 8% (Venta)'),
        ('no_credit', 16.0, 'purchase', 'IVA Sin Crédito 16% (Compra)'),
    )

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

    def _ensure_vat_taxes(self, company=None, country=None):
        """Crea (o reutiliza) los impuestos SENIAT de la compañía activa.

        ``_get_taxes_for_bases`` busca por ``l10n_ve_tax_type`` + uso +
        compañía; sin impuestos el wizard no genera líneas y el asiento no
        se puede publicar. Este helper hace al test independiente de que los
        datos de instalación estén presentes en la base.
        """
        company = company or getattr(self, 'company', self.env.company)
        country = country or self.country
        group = self._get_or_create_tax_group()
        taxes = self.env['account.tax']
        for tax_type, amount, use, name in self.VAT_TAX_DEFINITIONS:
            tax = self.env['account.tax'].search([
                ('l10n_ve_tax_type', '=', tax_type),
                ('type_tax_use', '=', use),
                ('company_id', '=', company.id),
            ], limit=1)
            if not tax:
                tax = self.env['account.tax'].create({
                    'name': name,
                    'amount_type': 'percent',
                    'amount': amount,
                    'l10n_ve_tax_type': tax_type,
                    'type_tax_use': use,
                    'company_id': company.id,
                    'tax_group_id': group.id,
                    'country_id': country.id,
                })
            taxes |= tax
        return taxes
