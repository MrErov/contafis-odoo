# Spec 002 - MCP Odoo: control programático de Odoo 19 desde OpenCode Desktop

Estado: completado

## Contexto y objetivo

El desarrollo del módulo se verifica vía Playwright (E2E) y odoo shell (diagnóstico),
pero no existe una vía directa para que el agente IA consulte y modifique registros
reales de la DB `contea` (clientes, facturas, libro de compras/ventas) sin pasar por
el navegador. El objetivo es integrar un servidor MCP (Model Context Protocol) de
Odoo en OpenCode Desktop, hablando la API JSON/2 nativa de Odoo 19 con API key
Bearer, para: (a) verificar flujos de negocio end-to-end contra datos reales,
(b) diagnosticar registros sin scripts temporales, (c) acelerar las fases SDD.

La fase P1 (MCP Odoo en OpenCode Desktop) está **completada**: smoke test end-to-end
verde (crear partner → crear factura → postear → verificar línea del libro →
renombrar → volver a borrador → borrar), con una anomalía intermitente documentada
y un workaround definido.

## Usuarios / actores

- **Agente IA (opencode)**: usa las tools `odoo_*` para consultar/crear/editar
  registros durante tareas SDD o Lightweight.
- **Contador (dueño de la instancia)**: mantiene la API key y la configuración
  global; no requiere acceso al repo para operar el MCP.
- **Sistema (Odoo 19)**: expone `/json/2/<model>/<method>` con auth Bearer +
  header `X-Odoo-Database`.

## Historias de usuario

- HU-1: Como agente IA, quiero listar/describir modelos y buscar registros de Odoo
  por dominio, para verificar estados y conteos durante una fase sin escribir
  scripts de diagnóstico.
- HU-2: Como agente IA, quiero crear/editar/borrar registros (partner, factura con
  líneas e impuestos) vía MCP, para correr smoke tests de flujos de negocio reales.
- HU-3: Como agente IA, quiero verificar que al postear una factura el módulo genera
  la línea del libro fiscal (`l10n.ve.vat.book.line`) y que `button_draft` la borra.
- HU-4: Como contador, quiero que la API key viva solo en mi máquina (config global
  + env var) y que NUNCA se commitee al repo.
- HU-5: Como agente IA, quiero un workaround conocido cuando el server MCP falla de
  forma intermitente (paralelismo + relay Docker), para no quedar bloqueado.

## Requisitos funcionales (EARS)

- RF-1: EL SISTEMA usa el server MCP `FGRibreau/mcp-odoo` v0.2.1 (binario Rust,
  stdio, `C:\Users\hp\AppData\Local\mcp-server-odoo\mcp-server-odoo.exe`,
  SHA256 `C89E17B9FD445542374023512E793A36FE28AB46820357093E0C5FA4F0A33EC5`).
- RF-2: CUANDO se configura el server, EL SISTEMA pasa `--odoo-url`, `--odoo-db` y
  `--odoo-api-key` vía env vars `ODOO_URL`, `ODOO_DB`, `ODOO_API_KEY`, y
  `ODOO_PROTOCOL=json2` (API JSON/2 de Odoo 19, no XML-RPC).
- RF-3: EL SISTEMA restringe modelos vía `MODEL_INCLUDE=l10n.ve.*,account.*,res.*,product.*,uom.uom`
  y `PAGE_SIZE=50`.
- RF-4: EL SISTEMA expone 8 tools MCP: `list_models`, `describe_model`, `search`,
  `read`, `create`, `write`, `delete`, `call_method` (estas dos últimas son la
  vía de escape para métodos del ORM).
- RF-5: CUANDO el agente ejecuta el smoke test E2E, EL SISTEMA (1) crea un
  `res.partner`, (2) crea un `account.move` de compra con línea, impuesto VE
  (`account.tax` id 3175, IVA General 16% Compra) y cuenta de gasto (id 3295),
  (3) lo postea con `action_post`, (4) verifica que `l10n.ve.vat.book.line`
  creció en 1, (5) renombra el partner (write), (6) pasa la factura a borrador
  (`button_draft`), (7) verifica que la línea del libro volvió al conteo inicial,
  (8) borra la factura y el partner (delete) y verifica conteos finales.
- RF-6: SI `search` falla por la anomalía de concurrencia (ver RF-8), ENTONCES el
  agente usa `call_method` con `search_read`/`search_count` secuenciales como
  workaround, o reintenta.
- RF-7: EL SISTEMA no expone la API key en el repo: vive en la config global de
  OpenCode (`~/.config/opencode/opencode.jsonc`) y en env var de usuario (`setx`).
- RF-8: EL SISTEMA documenta la anomalía conocida: `mcp-server-odoo` dispara
  `search_read` + `search_count` en paralelo (`tokio::join!` en
  `src/tools/search.rs`); a través del relay de puertos de Docker Desktop
  (`wslrelay`, 8090→8069) el payload concurrente puede corromperse de forma
  intermitente y Odoo responde HTTP 500 (`builtins.TypeError: unhashable type:
  'dict'` en `domains.py` al optimizar el dominio; `builtins.ValueError: Invalid
  field 'Count' on model 'res.partner'` al crear). No reproducible vía REST
  directo/secuencial. Decisión: documentar + workaround, NO parchear un binario
  de terceros.

## Requisitos no funcionales

- Portabilidad de config: el bloque MCP vive en la config global del usuario,
  no en `opencode.json` del repo (evita filtrar la key en un repo público).
- Observabilidad: errores del server MCP llegan como `Odoo API error (name): message`
  mapeados desde HTTP 500.
- Seguridad: API key generada con `env['res.users.apikeys']._generate('rpc', ...)`,
  revocable desde Ajustes → Usuarios → Claves API.
- Reproducibilidad del smoke test: script PowerShell inline (stdin/stdout JSON-RPC
  línea a línea, `ConvertTo-Json -Depth 12 -Compress`, timeout 30s por respuesta).
  Gotcha documentado: `$args` NO puede usarse como nombre de parámetro de función
  en PowerShell (se recibe vacío → `"arguments":}}` → serde error col 85).

## Casos límite

- El binario no soporta `--version` (menor, no bloqueante).
- Puerto 8090 ocupado por un Odoo fantasma en WSL histórico → ver `AGENTS.md`
  (sección diagnóstico menú); para MCP aplica el mismo chequeo (`wslrelay`).
- Concurrencia del server MCP → anomalía RF-8 con workaround RF-6.
- Puerto 8073→8072 del compose corresponde a otro servicio (no MCP).
- `search` sobre campos inexistentes de Odoo 19 → error `Invalid field` del ORM;
  verificar el nombre real del campo antes (ej. `compliance_status`, no `status`).

## Fuera de alcance

- Corregir `mcp-server-odoo` (binario de terceros) o hacer fork del mismo.
- Automatizar el MCP dentro de CI (la CI no tiene OpenCode Desktop).
- Exponer el MCP fuera de `localhost` o con TLS.
- Sustituir a Playwright E2E ni a odoo shell: el MCP es complementario.
- Modelos fuera de `MODEL_INCLUDE` (se evalúa ampliar por fase).

## Criterios de finalización

- 8 tools MCP responden contra `contea` (list_models, search, create, ...).
- Smoke test E2E completo con verificación psql independiente:
  libro 6→7→6, partner temporal creado→borrado, factura creada→posteada→borrador→borrada.
- Anomalía documentada en spec/plan + workaround en `AGENTS.md`.
- `docs/memory.md` actualizado (decisión técnica + pendiente mart337i cerrado).
- 121/121 tests backend siguen verdes (el MCP no toca `addons/`).

## Dudas abiertas

- [RESUELTA] ¿Binario de terceros o servidor propio Python? → Binario de terceros
  (FGRibreau/mcp-odoo v0.2.1); descartado servidor propio por mantenimiento.
- [RESUELTA] ¿Dónde vive la API key? → Config global del usuario + env var; nunca
  en el repo.
- [ABIERTA] Si la anomalía RF-8 escala (frecuencia > reintento), evaluar fork del
  server o servidor Python propio con requests secuenciales.
