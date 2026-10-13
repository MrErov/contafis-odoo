---
description: SDD — Divide el plan en tareas pequeñas y verificables
agent: plan
---

IMPORTANTE: las rutas de specs son relativas a la RAÍZ del repo (donde está AGENTS.md). NO usar docs/capacidades/.

A partir de `specs/$1/spec.md (relativo a la RAÍZ del repo, NO a docs/)` y `specs/$1/plan.md (relativo a la RAÍZ del repo, NO a docs/)`, genera
`specs/$1/tasks.md (relativo a la RAÍZ del repo, NO a docs/)` con:

- Tareas pequeñas (máx. 20-30 min cada una), en orden de dependencia.
- Cada una con los RF que cubre y una línea "Hecho cuando:"
  verificable (ej: "los 107 tests siguen pasando + demo visual").
- Checkboxes: `- [ ] **T1. <descripción>.** RF-1, RF-2`.
- Máximo 10 tareas. Si salen más, proponé dividir la spec en dos.

**Reglas:**
- ❌ NO crear archivos temporales
- ❌ NO tocar código
- ✅ "Hecho cuando:" debe ser comprobable sin ambigüedad

**Entrega:** ruta + lista de tareas (solo los títulos).
