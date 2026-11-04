from odoo import api, models
from odoo.tools.convert import convert_file

MODULE = 'l10n_ve_compliance_manager'
TAX_DATA_FILE = 'data/account_tax_data.xml'


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    def _load(self, template_code, company, install_demo, force_create=True):
        """Restaura los impuestos SENIAT después de cargar la plantilla contable.

        ``account.chart.template._load`` borra los registros de
        ``TEMPLATE_MODELS`` (incluye ``account.tax`` y
        ``account.tax.group``) de la compañía cuando esta no tiene
        contabilidad previa. En una instalación limpia eso elimina los
        impuestos cargados por ``data/account_tax_data.xml``, que se cargan
        antes de que la plantilla se aplique (la auto-instalación de la
        plantilla corre al final de la carga del registro, desde
        ``ir.module.module._register_hook``).

        Reproducir el XML aquí, con sus xmlids y en modo ``noupdate``,
        garantiza que los impuestos existan en cuanto la plantilla termina.
        Es idempotente: si los registros sobrevivieron, no se modifican.
        """
        res = super()._load(
            template_code, company, install_demo, force_create=force_create,
        )
        self._l10n_ve_ensure_vat_taxes()
        return res

    @api.model
    def _l10n_ve_ensure_vat_taxes(self):
        """(Re)crea los impuestos SENIAT definidos en ``account_tax_data.xml``."""
        convert_file(
            self.env,
            MODULE,
            TAX_DATA_FILE,
            {},
            mode='update',
            noupdate=True,
        )
