---
description: Cierra una fase de desarrollo (actualiza SPEC.md, memory.md, verifica y commitea)
---
Estás cerrando la fase de trabajo: **$ARGUMENTS**

Sigue este protocolo de cierre en orden estricto.

## Paso 1: Verificación previa

Ejecuta y muéstrame la salida literal:

1. `git log --oneline -5`
2. `git status`
3. Tests:
   !docker compose run --rm web odoo -d contea -u l10n_ve_compliance_manager --test-enable --stop-after-init --workers 0 --test-tags /l10n_ve_compliance_manager 2>&1 | grep -E "failed|tests when"

   Esperado: `0 failed, 0 error(s) of N tests`.

   Si hay algún test fallando → DETENTE y reporta. No continúes.

4. Verificación de constitución:
   ¿La fase cerrada respetó los 6 principios de
   `docs/constitution.md`? Reportar cualquier violación antes
   de continuar.

## Paso 2: Actualizar SPEC.md

Lee `@SPEC.md`. Verifica si necesita cambios según la fase cerrada:

- ¿La fase está en el roadmap? Actualízala a ✅.
- ¿Se añadió una spec nueva en `docs/capacidades/`? Agrégala al índice.
- ¿Hay nuevos modelos? Añádelos a la lista.
- ¿Cambió el estado del portafolio? Actualízalo.

Muéstrame el diff de `SPEC.md` antes de continuar.

## Paso 3: Actualizar docs/memory.md (local, no se commitea)

Actualiza el archivo local con:
- Último commit real (`git log --oneline -1`).
- Estado actual de las fases.
- Próxima fase pendiente.

Este archivo está en `.gitignore`, no se commitea.

## Paso 4: Commit final

Solo si los pasos 1-3 están OK, crea el commit siguiendo Conventional Commits.

Sugerencia de mensaje:
    docs(spec): close phase $ARGUMENTS

    - Update roadmap: mark $ARGUMENTS as completed
    - Add any new specs to index
    - Sync SPEC.md with actual project state

Contexto adicional: **$ARGUMENTS**

## Reglas estrictas

- ❌ NO crear archivos temporales.
- ❌ NO commitear si hay tests fallando.
- ❌ NO modificar código de `addons/` en este comando.
- ✅ Editar `SPEC.md` con la herramienta `edit`.
- ✅ Verificar el conteo real de tests antes de commitear.

## Entrega

1. Estado de git antes del cierre.
2. Línea literal de tests.
3. Diff de `SPEC.md`.
4. Salida del commit + push.
