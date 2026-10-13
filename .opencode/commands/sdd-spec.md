---
description: SDD — Entrevista y genera spec (uso: /sdd-spec NNN-nombre idea)
agent: plan
---

IMPORTANTE: las rutas de specs son relativas a la RAÍZ del repo (donde está AGENTS.md). NO usar docs/capacidades/.

NO escribas código en ningún momento. Lee `docs/constitution.md`,
`AGENTS.md` y `docs/memory.md`.

**Carpeta de la spec:** `specs/$1/ (relativo a la RAÍZ del repo, NO a docs/)`
**Idea inicial:** $ARGUMENTS

Tu trabajo:

1. Hazme preguntas de UNA en UNA para eliminar ambigüedades
   (casos límite, errores, qué queda fuera de esta versión).
   Máximo 5 preguntas. No avances hasta tener respuesta.

2. Con mis respuestas, genera `specs/$1/spec.md` con esta
   plantilla exacta:

# Spec NNN - <Nombre>

Estado: borrador

## Contexto y objetivo
<Qué problema resuelve y por qué merece la pena. Un párrafo.>

## Usuarios / actores
<Quién lo usa.>

## Historias de usuario
- HU-1: Como <rol> quiero <acción> para <beneficio>.

## Requisitos funcionales (EARS)
- RF-1: CUANDO <evento>, EL SISTEMA <respuesta>.
- RF-2: SI <condición no deseada>, ENTONCES EL SISTEMA <respuesta>.
- RF-3: MIENTRAS <estado>, EL SISTEMA <respuesta>.
- RF-4: EL SISTEMA <comportamiento permanente>.

## Requisitos no funcionales
<Solo los que apliquen.>

## Casos límite
<Vacíos, duplicados, datos corruptos, límites, concurrencia.>

## Fuera de alcance
<Lo que explícitamente NO se hace en esta iteración.>

## Criterios de finalización
<Todos los RF con test en verde + demo manual.>

## Dudas abiertas
- [NECESITA ACLARACIÓN] <duda>

3. Solo el QUÉ y el POR QUÉ. Nada de stack, arquitectura ni
   nombres de archivos (eso va en plan.md).

**Reglas:**
- ❌ NO crear archivos temporales
- ❌ NO editar nada fuera de `specs/$1/spec.md`
- ✅ Cada RF verificable (nada de "rápido", "bonito" sin criterio)
- ✅ Una frase = un comportamiento
- ✅ Español para el QUÉ, inglés para nombres de campo/método

**Entrega:** ruta del archivo + resumen de 5 líneas máx.
