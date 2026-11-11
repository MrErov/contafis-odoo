# Tasks 007-D — "Usar datos" por fila del lote

Spec: `specs/007-digitalizacion/007-d-spec.md` · Plan: `007-d-plan.md`.
Baseline: `0 failed, 0 error(s) of 433 tests` (`TestDigitizeBatch` 22/22).
Objetivo: `0 failed, 0 error(s) of 437 tests`.

Reglas: una tarea a la vez, TDD (test rojo antes del código). Commit solo al final, si
todo está verde. El conteo oficial es el de Odoo, nunca `grep -c`. Sin archivos
temporales, sin `git push`, sin comandos git destructivos.

Comando targeted:

```
docker compose run --rm web odoo -d contea -u l10n_ve_compliance_manager \
  --test-enable --stop-after-init --workers 0 \
  --test-tags /l10n_ve_compliance_manager:TestDigitizeBatch
```

Comando suite:

```
docker compose run --rm web odoo -d contea -u l10n_ve_compliance_manager \
  --test-enable --stop-after-init --workers 0 \
  --test-tags /l10n_ve_compliance_manager
```

---

- [ ] **T1. RED — los 4 tests primero.**
      Archivo: `tests/test_digitize_batch.py` (solo tests).
      Añadir `_load_fixture` al import de `.test_digitize_wizard`, el helper local
      `_analyzed_batch()` y los tests 23-26 al final de `TestDigitizeBatch`:
      `test_batch_line_apply_to_invoice_done`, `..._pending`, `..._error`,
      `test_batch_line_apply_to_invoice_without_result_json` (5 variantes con
      `subTest`). No tocar modelos ni vista.
      **Hecho cuando:** el módulo actualiza sin error y los 4 tests fallan por
      `AttributeError` de `action_apply_line_to_invoice` (no por import/sintaxis), con
      los 22 anteriores verdes. Este estado no se commitea.

- [ ] **T2. GREEN — helper compartido en el wizard.**
      Archivo: `models/digitize_wizard.py`.
      (a) `_map_extracted_to_invoice_defaults(self, extracted, document_type=None,
      confidence=None)` con el bloque de procedencia normalizado; (b) nuevo
      `_build_apply_to_invoice_action(self, extracted, document_type=None,
      confidence=None)` que construye y devuelve el `ir.actions.act_window`;
      (c) `action_apply_to_invoice()` delega en el helper conservando su validación y
      su tolerancia a `extracted_json` inválido.
      **Hecho cuando:** `--test-tags …:TestDigitizeBatch` sigue con 22 verdes y
      `TestDigitizeMapping::test_apply_returns_physical_wizard_action_with_defaults`
      pasa **sin editarlo** (los 4 nuevos siguen rojos).

- [ ] **T3. GREEN — `action_apply_line_to_invoice` en la fila.**
      Archivo: `models/digitize_batch_line.py`.
      Añadir `import json` y `UserError`; implementar la validación estado → JSON →
      `extracted` (dict no vacío) con los 3 mensajes en español, y delegar en
      `self.wizard_id._build_apply_to_invoice_action(extracted,
      document_type=data.get('document_type'), confidence=data.get('confidence'))`.
      Sin `write`/`create`/`sudo`.
      **Hecho cuando:** `0 failed, 0 error(s) of 26 tests` en `TestDigitizeBatch`.

- [ ] **T4. Vista — botón "Usar datos" en la lista del lote.**
      Archivo: `views/digitize_wizard_views.xml`.
      `<button name="action_apply_line_to_invoice" string="Usar datos" type="object"
      class="btn-link" invisible="status != 'done'"/>` entre `status` y
      `error_message`; `<list>` (no `<tree>`), sin `attrs`/`states`; header y botón
      single intactos.
      **Hecho cuando:** `-u l10n_ve_compliance_manager` no reporta error de RelaxNG y
      la vista carga.

- [ ] **T5. Verificación visual del botón y del diálogo anidado.**
      `docker compose restart web`, upgrade CLI y navegador en incógnito (Ctrl+Shift+R).
      Probar con un lote de 2 filas: una *Analizado* y una *Error*.
      **Hecho cuando:** solo la fila *Analizado* muestra **Usar datos**, al pulsarlo se
      abre *Factura Física Rápida* prellenado, la consola no muestra errores JS. Si el
      botón no renderiza con `section_and_note_one2many`, aplicar el plan B de R-2
      (one2many plano) y repetir.

- [ ] **T6. Cierre — suite completa, lint y commit.**
      Correr el comando suite, `pre-commit run --all-files`, `git status` y
      `git diff --stat`.
      **Hecho cuando:** `0 failed, 0 error(s) of 437 tests`, `pre-commit` verde,
      `git status` con solo los 4 archivos esperados
      (`models/digitize_wizard.py`, `models/digitize_batch_line.py`,
      `views/digitize_wizard_views.xml`, `tests/test_digitize_batch.py`) y commit
      `feat(digitize): add per-line apply to invoice in batch wizard` (sin push).

---

## Fuera de estas tasks

- `docs/guia-usuario/14-digitalizacion-facturas.md` (sección *Qué hacer con los
  resultados*, línea 152, y FAQ línea 196) y rebuild del PDF con `npm run build:guide`:
  los ejecuta el agente principal.
- `docs/memory.md`: lo actualiza el agente principal al cerrar.
- Backend `contafis-assistant`: sin cambios.
