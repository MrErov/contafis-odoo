"""
Headers mapping para Libro de Compras/Ventas (Excel real del contador).

Normalización aplicada: lowercase, quitar puntos, quitar acentos,
colapsar espacios múltiples. Ejemplo:
  "I.V.A. Alicuota General 16%" → "iva alicuota general 16%"
  "R.I.F." → "rif"
  "R.I.F" → "rif"
"""

# Todas las keys YA NORMALIZADAS (sin puntos, sin acentos, lowercase, espacios colapsados)
VAT_BOOK_HEADER_MAP = {
    # COMPRAS
    'rif': 'partner_vat',
    'nombre o razon social': 'partner_name',
    'razon social': 'partner_name',
    'tipo doc': 'invoice_type',
    'tipo de documento': 'invoice_type',
    'numero de factura': 'invoice_number',
    'nº factura': 'invoice_number',
    'numero factura / reporte z': 'invoice_number',
    'numero factura 0 reporte z': 'invoice_number',
    'numero de factura 0 reporte z': 'invoice_number',
    'numero de control': 'control_number',
    'fecha': 'invoice_date',
    'fecha de la factura': 'invoice_date',
    'base alicuota general 16%': 'base_general',
    'iva alicuota general 16%': 'vat_general',
    'base alicuota reducida': 'base_reduced',
    'iva alicuota reducida': 'vat_reduced',
    'compras no sujetas': 'base_not_subject',
    'compras sin derecho a credito (nacional)': 'base_no_credit',
    'base importacion 16%': 'base_import_16',
    'iva de importacion 16%': 'vat_import_16',
    'iva importacion 16%': 'vat_import_16',
    'nº comprob retencion 75%': 'retention_number',
    'iva retenido (al vendedor)': 'vat_retained_vendor',
    'iva retenido (a terceros)': 'vat_retained_third',
    'anticipo iva (importacion)': 'anticipo_import',
    # VENTAS
    'ventas internas no sujetas': 'base_not_subject',
    'ventas internas no gravadas (no contrib)': 'base_not_taxed',
    'base imponible (no contrib)': 'base_general_non_contrib',
    'impuesto iva (no contrib)': 'vat_general_non_contrib',
    'base imponible (contrib)': 'base_general_contrib',
    'impuesto iva (contrib)': 'vat_general_contrib',
    'nº comprob retencion 75% iva': 'retention_number',
    'iva retenido (por comprador)': 'vat_retained_buyer',
}
