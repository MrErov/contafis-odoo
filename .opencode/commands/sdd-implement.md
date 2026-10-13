---
description: SDD — Implementa UNA tarea, tests primero
agent: build
---

IMPORTANTE: las rutas de specs son relativas a la RAÍZ del repo (donde está AGENTS.md). NO usar docs/capacidades/.

Implementa SOLO la tarea `$2` de `specs/$1/tasks.md (relativo a la RAÍZ del repo, NO a docs/)`, siguiendo
`specs/$1/plan.md (relativo a la RAÍZ del repo, NO a docs/)`, `docs/constitution.md` y `AGENTS.md`.

Pasos:

1. Escribe primero los tests (en rojo).
2. Corre los tests → confirma que fallan por la razón correcta.
3. Escribe el código hasta que pasen.
4. Corre: `docker compose run --rm web odoo -d contea -u
   l10n_ve_compliance_manager --test-enable --stop-after-init
   --workers 0 --test-tags /l10n_ve_compliance_manager`
5. Verifica que sigue siendo `0 failed, 0 error(s) of 107 tests`
   (o más, si la tarea agrega tests nuevos).
6. Si hay cambios visuales, verificalos con el MCP de Chrome
   DevTools (regla #9 de AGENTS.md).
7. Marca `$2` como hecha en tasks.md (`- [x]`).

Después PÁRATE. No empieces la siguiente tarea.

**Reglas:**
- ❌ NO crear archivos temporales (violación recurrente en UX-1)
- ❌ NO usar sed, awk, python -c
- ❌ NO commitear (el usuario commitea desde WSL)
- ❌ NO tocar tareas que no sean `$2`
- ✅ Editar con edit
- ✅ Si el plan es incorrecto o imposible → PARA y explica,
  no improvises

**Entrega:**
1. Tarea completada + RF que cubre.
2. Archivos modificados.
3. Output literal de la línea de tests (`0 failed, 0 error(s) of N`).
4. Cualquier decisión que el plan no cubría.
