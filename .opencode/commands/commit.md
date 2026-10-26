---
description: "Verifica el estado de git, los tests, y crea un commit siguiendo Conventional Commits"
---
Vas a crear un commit siguiendo estrictamente el flujo definido en `@AGENTS.md`.

### Paso 1: Verificación obligatoria
Ejecuta y muéstrame la salida literal de:

1.  `git status` → Solo deben aparecer los archivos esperados.
2.  `git diff --stat` → La cantidad de cambios debe ser coherente.
3.  `pytest -q` → Debe decir todos los tests pasaron (ej. `562 passed`).

### Paso 2: Commit
Si y solo si la verificación es exitosa, crea un commit usando **Conventional Commits** (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`).

El mensaje debe describir claramente el cambio. Aquí tienes el contexto: **$ARGUMENTS**

### Reglas estrictas
- ❌ NO crear archivos temporales (`fix_*.py`, `check_*.py`, etc.).
- ❌ NO commitear si los tests fallan o si hay archivos inesperados.
- ✅ Editar archivos directamente con la herramienta `edit`.
