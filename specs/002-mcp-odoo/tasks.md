# Tasks 002 - MCP Odoo: control programático de Odoo 19 desde OpenCode Desktop

Estado: completado

## Tareas

- [x] **T1 (P1.1). Selección del server MCP.**
  RF-1.
  Criterios: soporte JSON/2 Odoo 19, stdio, binario sin runtime extra.
  Hecho cuando: comparados FGRibreau/mcp-odoo v0.2.1, JSDevArt/odoo-mcp-server,
  mart337i/odoo-dev-mcp y servidor propio Python → elegido FGRibreau v0.2.1.

- [x] **T2 (P1.2). API key + binario.**
  RF-2, RF-7.
  Pasos: `_generate('rpc', 'mcp-server', False)` en odoo shell sobre `contea`;
  `setx ODOO_API_KEY`; descarga del binario + verificación SHA256.
  Hecho cuando: key verificada contra `/json/2` (200 admin) + binario en
  `%LOCALAPPDATA%\mcp-server-odoo\mcp-server-odoo.exe`.

- [x] **T3 (P1.3). Configuración global de OpenCode.**
  RF-2, RF-3, RF-7.
  Editar `~/.config/opencode/opencode.jsonc` (bloque `mcp.servers.odoo`).
  Hecho cuando: bloque con command + env (`ODOO_URL`, `ODOO_DB`, `ODOO_PROTOCOL=json2`,
  `ODOO_API_KEY`, `MODEL_INCLUDE`, `PAGE_SIZE`, `timeout`) aplicado.

- [x] **T4 (P1.4). Verificación de tools y paridad de datos.**
  RF-4.
  Hecho cuando: 8 tools responden (`list_models`, `describe_model`, `search`,
  `read`, `create`, `write`, `delete`, `call_method`) + conteos MCP == psql
  (3 clientes de cumplimiento, 2 instituciones, 108 snapshots de cartelera,
  6 líneas del libro) + `create` res.partner id 7194 verificado +
  campo correcto `compliance_status` confirmado.

- [x] **T5 (P1.5). Smoke test E2E.**
  RF-5.
  Secuencia: crear partner → crear factura compra (línea + tax 3175 + cuenta 3295)
  → `action_post` → libro 6→7 → `write` rename → `button_draft` → libro 7→6
  → `delete` factura → `delete` partner → verificación psql.
  Hecho cuando: todo verde + psql confirma `book_lines=6`, partner y move
  temporales ausentes, `clients=3`.
  Nota: primera corrida falló por bug del harness (parámetro `$args` en
  PowerShell); corregido con nombres distintos + `ConvertTo-Json -Depth 12`.

- [x] **T6 (P1.5b). Análisis de anomalía + workaround.**
  RF-6, RF-8.
  Hecho cuando: identificados los dos errores intermitentes
  (`unhashable type: 'dict'` en `search`, `Invalid field 'Count'` en `create`),
  confirmado que `search.rs` usa `tokio::join!` (paralelo) y que REST secuencial
  nunca falla; decidido documentar + workaround `call_method` secuencial;
  registrado en `plan.md` (sección Anomalía) y `AGENTS.md`.

- [x] **T7 (P1.6). Documentación y cierre.**
  Criterios de finalización de `spec.md`.
  Hecho cuando: `specs/002-mcp-odoo/{spec,plan,tasks}.md` creados, `AGENTS.md`
  con sección "MCP Odoo", `SPEC.md` con MCP completado, `docs/memory.md`
  actualizado, regresión 121/121 verde, commit `docs(spec): close phase MCP Odoo`.

## Pendiente futuro (fuera de P1)

- [ ] Evaluar ampliar `MODEL_INCLUDE` si alguna fase lo requiere.
- [ ] Si la anomalía escala: fork del server o servidor MCP propio con requests
      secuenciales (fallback anotado en `spec.md`).
- [ ] MCP en CI: descartado (CI no tiene OpenCode Desktop).
