# Specs — Features (SDD)

Esta carpeta contiene specs de **features específicas** siguiendo el flujo SDD: nacen, se implementan, quedan como registro histórico.

## Diferencia con docs/capacidades/

- `docs/capacidades/` → specs por **capacidad del módulo** (calendario SENIAT, retenciones, cartelera). Viven para siempre, se actualizan.
- `specs/` (esta carpeta) → specs por **feature/iteración** (backend odoo-first, wizard factura física). Nacen, se implementan, quedan como registro.

## Estructura specs/NNN-nombre/

spec.md ← QUÉ y POR QUÉ (requisitos EARS)
plan.md ← CÓMO (archivos, métodos, tests)
tasks.md ← tareas pequeñas con Hecho cuando:

## Flujo (comandos en .opencode/commands/)

1. /sdd-spec NNN-nombre idea
2. /sdd-clarify NNN-nombre
3. /sdd-plan NNN-nombre
4. /sdd-tasks NNN-nombre
5. /sdd-implement NNN-nombre T1
6. /sdd-status NNN-nombre
