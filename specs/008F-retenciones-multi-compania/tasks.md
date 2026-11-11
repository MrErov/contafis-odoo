# Tareas Spec 008-F

## T1 — Confirmar líneas exactas de generate_retentions (solo lectura)
**Alcance:** leer `models/retention_service.py` y localizar el chequeo de `move_type` y el bloque `vals_list` de `generate_retentions`.
**Hecho cuando:** se tienen los números de línea exactos del chequeo de `move_type` y de cada `vals` en `vals_list`.

## T2 — Agregar 4 tests nuevos en rojo (primero en rojo)
**Alcance:** editar `tests/test_multi_company_ux.py` (clase `TestMultiCompanyUx`) y agregar `test_retention_service_propagates_move_company`, `test_move_resolution_posted_without_partner_fails`, `test_move_resolution_draft_with_partner_fails`, `test_retention_sequence_isolation_bidirectional`.
**Hecho cuando:** los 4 tests están escritos y el comando targeted reporta fallos (red) antes del fix.

## T3 — Aplicar fix F-A en retention_service.py
**Alcance:** `models/retention_service.py::generate_retentions`: agregar `self = self.with_company(move.company_id)` tras el chequeo de `move_type` y agregar `'company_id': move.company_id.id` a cada `vals` de `vals_list`.
**Hecho cuando:** ambos cambios están en el archivo y no hay otros archivos de producción modificados.

## T4 — Verificar targeted TestMultiCompanyUx (verde)
**Alcance:** correr el comando targeted de `TestMultiCompanyUx`.
**Hecho cuando:** los tests nuevos pasan (0 failed) y no hay regresiones en la clase.

## T5 — Verificar suite completa /l10n_ve_compliance_manager
**Alcance:** correr la suite completa y consultar `odoo.tests.result`.
**Hecho cuando:** `0 failed, 0 error(s) of N tests` con N >= 465 (contexto: 468).

## T6 — Verificar árbol de git (solo archivos esperados)
**Alcance:** `git status` y `git diff --stat`.
**Hecho cuando:** solo `models/retention_service.py` y `tests/test_multi_company_ux.py` aparecen modificados.

## T7 — Commit (sin push)
**Alcance:** commitear con mensaje `fix(retention): ensure company_id propagation in retention service (Spec 008-F)`.
**Hecho cuando:** el commit existe en rama `19.0` y `git status` está limpio.
