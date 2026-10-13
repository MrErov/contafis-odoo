---
description: "Inicia una nueva fase (MODO PLAN - no escribe código hasta aprobar)"
agent: plan
---
**Contexto:** Lee `@AGENTS.md` y `@docs/memory.md`.

**Fase a planificar:** $ARGUMENTS

**PROTOCOLO OBLIGATORIO — respétalo estrictamente:**

1. Lee `docs/constitution.md`, `AGENTS.md` y `docs/memory.md`.
2. Busca la spec relevante en `docs/capacidades/`.
3. **NO ESCRIBAS CÓDIGO NI MODIFIQUES ARCHIVOS.** Solo propón un plan.
4. El plan debe incluir: archivos a modificar, cambios exactos, tests, casos límite.
5. **ESPERA MI APROBACIÓN EXPLÍCITA** antes de tocar nada.
6. Solo después de aprobar, implementa paso a paso.
7. Al terminar, usa `/phase-closure`.

**Anti-patterns prohibidos (AGENTS.md):**
- ❌ NO crear archivos temporales (`fix_*.py`, `/tmp/*.py`, `check_*.py`).
- ❌ NO usar `sed -i` ni `python3 -c` para editar archivos.
- ❌ NO entrar en loops de "escribir → pensar → reescribir".
- ✅ Editar directamente con la herramienta `edit`.
- ✅ Si fallas 2 veces en el mismo punto, DETENTE y avísame.

**Si no puedes completar una tarea sin violar estas reglas, DETENTE y explica por qué.**
