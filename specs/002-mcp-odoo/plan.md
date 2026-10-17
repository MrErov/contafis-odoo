# Plan 002 - MCP Odoo: control programático de Odoo 19 desde OpenCode Desktop

## Arquitectura

```
┌────────────────────┐   stdio (JSON-RPC)   ┌──────────────────────┐   HTTP /json/2    ┌──────────────┐
│ OpenCode Desktop   │ ───────────────────► │ mcp-server-odoo      │ ────────────────► │ Odoo 19      │
│ (agente IA)        │ ◄─────────────────── │ v0.2.1 (Rust)        │ ◄──────────────── │ contea:8069  │
└────────────────────┘                      └──────────────────────┘                   └──────────────┘
        │                                            │                                      ▲
        │ config global (jsonc)                      │ Bearer <ODOO_API_KEY>                │
        │ env: ODOO_URL/ODOO_DB/...                  │ X-Odoo-Database: contea              │ host: 8090
        └────────────────────────────────────────────┴──────────────────────────────────────┘
```

- Transporte agente↔MCP: stdio, JSON-RPC línea a línea, protocolVersion negociado
  `2024-11-05`, serverInfo `mcp-server-odoo 0.2.1`.
- Transporte MCP↔Odoo: HTTP POST `/json/2/<model>/<method>` con
  `Authorization: Bearer <key>` y header `X-Odoo-Database: contea`.
- Puerto: host `127.0.0.1:8090` → contenedor `contafis-web-1:8069`.

## Selección del server MCP (P1.1)

| Candidato | Resultado | Decisión |
|-----------|-----------|----------|
| `FGRibreau/mcp-odoo` v0.2.1 (Rust, binario único) | 8 tools, soporta JSON/2 nativo de Odoo 19, 1 proceso stdio, sin runtime externo | ✅ **ELEGIDO** |
| `JSDevArt/odoo-mcp-server` | Python, más dependencias y setup por proyecto | ❌ Descartado |
| `mart337i/odoo-dev-mcp` | Enfoque dev/edición de código más que datos; sin release estable | ❌ Descartado (queda como complemento futuro si se necesita) |
| Servidor MCP propio en Python (FastMCP + requests) | Control total, requests secuenciales (evita anomalía) | ❌ Descartado por mantenimiento; anotado como fallback en `spec.md` |

## Instalación y configuración (P1.2 – P1.3)

| Paso | Detalle |
|------|---------|
| Binario | `C:\Users\hp\AppData\Local\mcp-server-odoo\mcp-server-odoo.exe` (SHA256 `C89E17B9FD445542374023512E793A36FE28AB46820357093E0C5FA4F0A33EC5`) |
| API key | Generada en odoo shell: `env['res.users.apikeys']._generate('rpc', 'mcp-server', False)` (usuario admin sobre `contea`) |
| Persistencia key | `setx ODOO_API_KEY <key>` (env var de usuario, NO commitear) |
| Config | `C:\Users\hp\.config\opencode\opencode.jsonc` → bloque `mcp.servers.odoo` (config global del usuario, no del repo) |
| Env del bloque | `ODOO_URL=http://127.0.0.1:8090`, `ODOO_DB=contea`, `ODOO_PROTOCOL=json2`, `ODOO_API_KEY=<key>`, `MODEL_INCLUDE=l10n.ve.*,account.*,res.*,product.*,uom.uom`, `PAGE_SIZE=50`, `timeout=15000` |
| Activación | Reiniciar OpenCode Desktop (recarga el proceso MCP y registra tools `odoo_*`) |

### Por qué la config es global y no de repo

`opencode.json` del repo es público (GitHub). La API key nunca debe commiteartse.
La config global del usuario (`~/.config/opencode/opencode.jsonc`) queda fuera de
control de versiones y es la única con el bloque `odoo`.

## Smoke test E2E (P1.5)

Harness: PowerShell inline (sin archivos): `System.Diagnostics.Process` con
stdin/stdout redirigidos, request JSON-RPC por línea, `ConvertTo-Json -Depth 12
-Compress`, lectura con timeout 30s, `RUST_LOG=error` para silenciar logs.

Secuencia verificada (todo vía tools MCP):

| # | Paso | Tool MCP | Resultado |
|---|------|----------|-----------|
| 1 | Listar clientes de cumplimiento | `search` | 3 registros (1771, 1772, 1773) |
| 2 | Listar impuestos VE | `search` | 5 taxes (3175 IVA 16% Compra … 3178) |
| 3 | Buscar cuenta de gasto | `search` | cuenta id 3295 |
| 4 | Crear partner temporal | `create` | partner 7194 |
| 5 | Crear factura compra con línea + tax | `create` | `account.move` 1531 |
| 6 | Postear factura | `call_method action_post` | `false` (normal) |
| 7 | Verificar línea del libro | `call_method search_count` | 7 (antes 6) ✅ `_post` → `_generate_vat_book_line` |
| 8 | Renombrar partner | `write` | OK ("MCP Smoke Test RENAMED") |
| 9 | Volver factura a borrador | `call_method button_draft` | true; libro vuelve a 6 ✅ |
| 10 | Borrar factura | `delete` | true |
| 11 | Borrar partner | `delete` | true |
| 12 | Verificación final | psql directo | book_lines=6, partner_7194=0, moves=0, clients=3 |

## Anomalía conocida (documentada, no parcheada)

**Síntoma**: fallos intermitentes HTTP 500 desde el MCP, no reproducibles vía
REST directo:

1. `search` sobre `l10n.ve.vat.book.line` → `builtins.TypeError: unhashable
   type: 'dict'` en `odoo/orm/domains.py` (`_operator_equal_as_in`, el valor de
   un dominio llega como dict inesperado).
2. `create` de `account.move` → `builtins.ValueError: Invalid field 'Count' on
   model 'res.partner'` en `_prepare_create_values → _add_precomputed_values →
   new()` (un dict llega como valor de un campo m2o).

**Evidencia recogida**:
- Ambos fallos aparecen solo en ráfagas: `search.rs` del server dispara
  `search_read` + `search_count` en paralelo (`tokio::join!`).
- Logs de Odoo: las dos peticiones paralelas fallan con 500 en el mismo
  milisegundo; en otra iteración las mismas peticiones suceden.
- Replay REST secuencial del mismo payload (mismos ids, mismo dominio): 200 OK.
- El mensaje serializado por el harness (partner_id int, tax command
  `[[6,0,[3175]]]`) se verificó limpio; el fallo ocurre antes de llegar a Odoo
  o por corrupción de la conexión concurrente.

**Hipótesis**: el relay de puertos de Docker Desktop en Windows (`wslrelay`,
`8090→8069`) interfiere con las conexiones keep-alive concurrentes del binario
Rust (pool `reqwest`), mezclando bytes de requests simultáneos en casos raros.

**Decisión (2026-10-17)**: documentar + workaround, no parchear terceros.

**Workaround**:
- Si `search` falla → reintentar una vez; si persiste → `call_method` con
  `search_read`/`search_count` (llamadas secuenciales, sin paralelismo).
- Si `create` falla con `Invalid field` → reintentar o crear vía `call_method`.

## Archivos afectados fuera del repo

| Ruta | Cambio | Git |
|------|--------|-----|
| `C:\Users\hp\AppData\Local\mcp-server-odoo\mcp-server-odoo.exe` | Binario del server | Fuera del repo |
| `C:\Users\hp\.config\opencode\opencode.jsonc` | Bloque `mcp.servers.odoo` con API key | Fuera del repo (global) |
| Env var usuario `ODOO_API_KEY` (`setx`) | Key persistida | Fuera del repo |

## Archivos del repo actualizados

| Archivo | Cambio |
|---------|--------|
| `specs/002-mcp-odoo/spec.md` | Este artefacto (retrospectiva P1) |
| `specs/002-mcp-odoo/plan.md` | Este plan |
| `specs/002-mcp-odoo/tasks.md` | Tareas P1.1–P1.6 |
| `AGENTS.md` | Sección "MCP Odoo": workaround + reglas de uso |
| `SPEC.md` | Roadmap: MCP marcado como COMPLETADO |
| `docs/memory.md` | Decisión + sesión (local, no se commitea) |

## Decisiones técnicas justificadas

| Decisión | Justificación | Alternativa descartada |
|----------|---------------|------------------------|
| `ODOO_PROTOCOL=json2` | API nativa Odoo 19 (`/json/2`), auth Bearer estándar, errores tipados | XML-RPC (legacy, sin tipos) |
| Config global fuera del repo | Repo público; key jamás commiteada | `opencode.json` del repo con key (riesgo de filtración) |
| `MODEL_INCLUDE` acotado | Reduce ruido (solo modelos del dominio fiscal + core útil) | Todos los modelos (listado gigante, más tokens) |
| Smoke test vía harness PowerShell inline | Sin archivos temporales (regla del repo), reproducible | Script Playwright (más lento, toca UI) o archivos `.ps1` (prohibidos) |
| Anomalía: documentar + workaround | No se mantiene fork de terceros; frecuencia baja; fallback existe | Fork/parche del binario Rust (mantenimiento alto) |

## Verificación

- Smoke test E2E P1.5 completo (tabla arriba) + verificación psql independiente.
- `docker compose run --rm web odoo -d contea -u l10n_ve_compliance_manager
  --test-enable --stop-after-init --workers 0
  --test-tags /l10n_ve_compliance_manager` → 121/121 (el MCP no toca `addons/`).
