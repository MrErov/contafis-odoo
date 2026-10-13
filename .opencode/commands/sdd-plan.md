---
description: SDD — Genera el plan técnico de una spec aprobada
agent: plan
---

IMPORTANTE: las rutas de specs son relativas a la RAÍZ del repo (donde está AGENTS.md). NO usar docs/capacidades/.

Lee `docs/constitution.md`, `AGENTS.md` y `specs/$1/spec.md (relativo a la RAÍZ del repo, NO a docs/)`.
NO escribas código.

Genera `specs/$1/plan.md` con:

- **Archivos** que se crean o modifican, y responsabilidad de cada uno.
- **Funciones puras** necesarias (con `company_id` o `self.env`
  como parámetro según aplique en Odoo).
- **Algoritmo en pseudocódigo** de la lógica no trivial.
- **Interfaz** (vistas XML, botones, wizard) si aplica.
- **Decisiones técnicas justificadas** con su alternativa descartada.
- **Estrategia de tests** con Odoo (`docker compose run --rm web
  odoo -d contea -u l10n_ve_compliance_manager --test-enable ...`).
- **Qué RF cubre cada parte** (anotación explícita).

Si la spec no está aprobada o tiene dudas abiertas → PARA y avisá.

**Reglas:**
- ❌ NO crear archivos temporales
- ❌ NO tocar código
- ✅ Si una decisión no está clara, listala como pregunta abierta
  y espera mi respuesta

**Entrega:** ruta + resumen de 5 líneas máx.
