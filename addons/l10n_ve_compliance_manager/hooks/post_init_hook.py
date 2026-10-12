def post_init_hook(env):
    """
    Post-init hook defensivo para vat.book.line.

    CONTEXTO:
    - El campo source se agrego con default='manual' (ver T2). Eso
      significa que Odoo lleno todas las filas existentes con 'manual'.
    - Por lo tanto, esta query WHERE source IS NULL es un no-op en la
      practica: nunca hay NULLs.
    - El hook queda como defensivo por si en alguna migracion futura
      el campo se agrega como nullable.

    LIMITACION CONOCIDA:
    - No es posible distinguir "linea pre-source" de "linea manual del
      usuario" (ambas tienen source='manual'). Intentar migrarlas
      sobrescribiria datos legitimos.
    - Documentado en docs/memory.md como deuda.
    """
    # Actualizar vat.book.line existentes sin source
    env.cr.execute("""
        UPDATE l10n_ve_vat_book_line
        SET source = 'excel_import'
        WHERE source IS NULL
    """)
