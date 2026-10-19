{
    'name': 'Venezuela - Cumplimiento Fiscal y Documental',
    'version': '19.0.1.2.0',
    'author': 'Eurick Ospino',
    'website': 'https://github.com/MrErov/contafis-odoo-19.0v',
    'category': 'Accounting/Localizations',
    'summary': 'Gestión de cumplimiento fiscal, parafiscal y documental para Venezuela',
    'description': """
Módulo Odoo 19.0 para contadores y firmas contables que gestionan múltiples
clientes en Venezuela.

Incluye:
- Calendario SENIAT 2026 con cálculo de vencimientos por RIF.
- Seguimiento de obligaciones fiscales, parafiscales y municipales.
- Cartelera fiscal documental con alertas de renovación.
- Alertas por email y WhatsApp (wa.me).
- Dashboard de cumplimiento por cliente.
- Retenciones de IVA/ISLR/IGTF vinculadas a facturas de proveedor.
- Libro de Compras/Ventas y Planilla IVA 99030 (Forma 99030 SENIAT).
    """,
    'license': 'LGPL-3',
    'depends': ['base', 'account', 'mail', 'l10n_ve'],
    'post_init_hook': 'post_init_hook',
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'data/mail_templates.xml',
        'data/cron.xml',
        'data/ir_sequence.xml',
        'data/seniat_calendar_2026.xml',
        'data/islr_calendar_2026.xml',
        'data/bank_holidays_2026.xml',
        'data/institution_data.xml',
        'data/islr_obligation_types.xml',
        'data/account_tax_data.xml',
        'data/document_type_cartelera.xml',
        'data/obligation_bulk_actions.xml',
        'data/ir_config_parameter_data.xml',
        'report/compliance_report.xml',
        'report/vat_return_report.xml',
        'report/islr_conciliation_report.xml',
        'views/institution_views.xml',
        'views/obligation_type_views.xml',
        'views/document_views.xml',
        'views/alert_views.xml',
        'views/compliance_client_views.xml',
        'views/obligation_views.xml',
        'views/obligation_payment_wizard_views.xml',
        'wizards/copy_calendar_wizard_views.xml',
        'views/seniat_calendar_views.xml',
        'views/bank_holiday_views.xml',
        'views/account_move_views.xml',
        'views/physical_invoice_wizard_views.xml',
        'views/islr_conciliation_views.xml',
        'views/menu.xml',
        'views/obligation_analysis_views.xml',
        'views/import_views.xml',
        'views/cartelera_evidence_views.xml',
        'views/cartelera_status_views.xml',
        'views/vat_book_views.xml',
        'views/vat_book_generate_views.xml',
        'views/vat_return_views.xml',
        'views/vat_book_export_views.xml',
        'views/regenerate_confirm_wizard_views.xml',
    ],
    'demo': [
        'demo/demo_data.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
