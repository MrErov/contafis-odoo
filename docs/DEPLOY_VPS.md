# Guía de Despliegue en VPS — ContaFis (Producción)

> **Objetivo**: Levantar el stack completo (Odoo 19 + Assistant + ChromaDB + PostgreSQL + Nginx) en un VPS con Ubuntu 22.04/24.04, acceso HTTPS desde el móvil y renovación automática de certificados.

---

## 1. Requisitos previos

| Recurso | Mínimo | Recomendado |
|---------|--------|-------------|
| **RAM** | 4 GB | 8 GB (para workers Odoo + embeddings) |
| **vCPU** | 2 | 4 |
| **Disco** | 30 GB SSD | 50 GB SSD (filestore Odoo + vectores Chroma) |
| **SO** | Ubuntu 22.04 LTS | Ubuntu 24.04 LTS |
| **Dominio** | Sí (ej. `contafis.miempresa.com`) | Registro A apuntando a la IP del VPS |
| **Puertos** | 22 (SSH), 80 (HTTP), 443 (HTTPS) | Abiertos en firewall del proveedor (AWS SG, DigitalOcean Firewall, etc.) |

> **Nota**: El stack usa 5 contenedores. Con 4 GB RAM funcionará, pero los workers de Odoo (`ODOO_WORKERS=4`) y el modelo de embeddings compiten por memoria. Si ves OOM kills, sube a 8 GB o reduce workers a 2.

---

## 2. DNS — Registro A

En tu proveedor de DNS (Cloudflare, Namecheap, GoDaddy, etc.) crea:

| Tipo | Nombre | Valor | TTL |
|------|--------|-------|-----|
| A    | `@` o `contafis` | `<IP_PUBLICA_DEL_VPS>` | Automático / 300 s |

Ejemplo: si tu dominio es `miempresa.com` y quieres `contafis.miempresa.com`, crea un registro A para `contafis` apuntando a la IP del VPS.

Verifica la propagación:
```bash
dig +short contafis.miempresa.com
# Debe devolver la IP de tu VPS
```

---

## 3. Ejecutar el script de inicialización

Conéctate al VPS por SSH como `root` (o usuario con `sudo`) y ejecuta:

```bash
# Opción A: Una línea (descarga y ejecuta)
curl -fsSL https://raw.githubusercontent.com/MrErov/contafis-odoo/19.0/scripts/setup-vps.sh | sudo bash

# Opción B: Descargar, revisar y ejecutar (recomendado)
wget https://raw.githubusercontent.com/MrErov/contafis-odoo/19.0/scripts/setup-vps.sh
chmod +x setup-vps.sh
sudo ./setup-vps.sh
```

**Qué hace el script** (resumen):
- Actualiza paquetes e instala `curl`, `git`, `vim`, `ufw`, `docker`, `docker compose plugin`, `certbot`
- Configura **UFW**: permite 22 (SSH), 80 (HTTP), 443 (HTTPS); deniega lo demás
- Crea usuario **`contafis`** (no-root), lo añade al grupo `docker` y configura `sudo` sin password
- Crea directorio **`/opt/contafis`** (owner: `contafis`)
- Crea **swap de 2 GB** (recomendado para 4 GB RAM)
- Instala script helper `/usr/local/bin/renew-certs.sh` para renovación automática

> **Importante**: Tras el script, **cierra la sesión SSH y vuelve a entrar** (o ejecuta `newgrp docker`) para que los grupos surtan efecto.

---

## 4. Clonar el repositorio y configurar secretos

Ahora como usuario `contafis` (no root):

```bash
# Cambiar a usuario contafis
sudo -iu contafis

# Ir al directorio del proyecto
cd /opt/contafis

# Clonar repo (rama 19.0 = Odoo 19 estable)
git clone https://github.com/MrErov/contafis-odoo.git . -b 19.0

# Verificar estructura
ls -la
# Debes ver: docker-compose.prod.yml, .env.prod.example, config/, addons/, etc.
```

### 4.1 Crear `.env.prod` (secretos del stack)

```bash
cp .env.prod.example .env.prod
vim .env.prod   # O nano, editor que prefieras
```

**Variables CRÍTICAS que DEBES cambiar** (nunca uses los valores de ejemplo en producción):

| Variable | Qué es | Ejemplo de valor real |
|----------|--------|----------------------|
| `POSTGRES_PASSWORD` | Password de la BD PostgreSQL | `Xk9#mP2$vL8@qW4!` (genera uno fuerte con `openssl rand -base64 32`) |
| `OPENAI_API_KEY` | API Key de NVIDIA NIM (OpenAI-compatible) | `nvapi-xxxxxxxxxxxxxxxxxxxxxxxx` (de <https://build.nvidia.com/>) |
| `API_SHARED_SECRET` | Secreto compartido para validar requests internos | `openssl rand -base64 48` |
| `ODOO_API_KEY` | API Key read-only de Odoo (Ajustes → Usuarios → API Keys) | `xxxxxxxxxxxxxxxxxxxx` (crear en Odoo tras primer arranque) |
| `LANGSMITH_API_KEY` | (Opcional) Trazas en LangSmith | `lsv2_pt_xxxxxxxxxxxxxxxxxxxxxxxx` |

**Otras variables a revisar/ajustar**:
- `ODOO_DB`: nombre de la BD (por defecto `contea`)
- `ODOO_WORKERS`: workers de Odoo (4 por defecto; baja a 2 si RAM < 6 GB)
- `CHROMA_COLLECTION`: nombre de la colección vectorial (default `contafis_normativa_v1`)
- `LLM_MODEL` / `EMBEDDING_MODEL`: modelos NVIDIA NIM (ver `.env.prod.example`)

> ⚠️ **NUNCA commitees `.env.prod`**. Está en `.gitignore`. Haz backup seguro (gestor de contraseñas, 1Password, Bitwarden, Vaultwarden).

### 4.2 Configurar `config/odoo.conf/odoo.conf`

Este archivo también está en `.gitignore`. Cópialo del ejemplo y edita:

```bash
mkdir -p config/odoo.conf
cp config/odoo.conf/odoo.conf.example config/odoo.conf/odoo.conf 2>/dev/null || cat > config/odoo.conf/odoo.conf << 'EOF'
[options]
admin_passwd = CAMBIAR_POR_MASTER_PASSWORD_FUERTE
db_host = db
db_port = 5432
db_user = odoo
db_password = CAMBIAR_POR_MISMO_VALOR_QUE_POSTGRES_PASSWORD
db_name = contea
list_db = False
log_level = info
proxy_mode = True
workers = 4
limit_memory_hard = 2684354560
limit_memory_soft = 2147483648
limit_request = 8192
limit_time_cpu = 600
limit_time_real = 1200
max_cron_threads = 1
EOF
vim config/odoo.conf/odoo.conf
```

**Campos obligatorios**:
- `admin_passwd`: Master password de Odoo (para gestión de BD vía interfaz web). Genera uno fuerte.
- `db_password`: **Debe ser idéntico a `POSTGRES_PASSWORD`** de `.env.prod`.
- `list_db = False`: Oculta el selector de BD en login (seguridad en producción).

---

## 5. Levantar el stack (primera vez)

```bash
cd /opt/contafis

# Construir y levantar en background
docker compose -f docker-compose.prod.yml up -d --build

# Ver logs en tiempo real (Ctrl+C para salir sin parar contenedores)
docker compose -f docker-compose.prod.yml logs -f

# Ver estado de salud
docker compose -f docker-compose.prod.yml ps
# Todos deben mostrar "healthy" o "running"
```

**Tiempos típicos primer arranque**:
- `db`: ~10-20 s (PostgreSQL init)
- `odoo`: ~60-120 s (carga módulos, migraciones, crea BD `contea`)
- `chromadb`: ~15-30 s
- `assistant`: ~60-180 s (descarga modelos NIM si no están en caché, construye índice BM25)
- `nginx`: ~5 s

> **Si `assistant` tarda mucho**: revisa logs con `docker compose -f docker-compose.prod.yml logs assistant`. La primera vez descarga pesos del modelo de embeddings (~2 GB).

---

## 6. Obtener certificado TLS (Let's Encrypt) y activar HTTPS

### 6.1 Emitir certificado (con HTTP ya funcionando en puerto 80)

```bash
# Como root o con sudo (certbot necesita acceso a /etc/letsencrypt y puerto 80)
sudo certbot certonly \
  --webroot \
  -w /var/www/certbot \
  -d contafis.miempresa.com \
  --email admin@miempresa.com \
  --agree-tos \
  --no-eff-email \
  --rsa-key-size 4096
```

- `-w /var/www/certbot`: usa el webroot que nginx sirve en `/.well-known/acme-challenge/`
- Reemplaza `contafis.miempresa.com` por tu dominio real.
- El certificado se guarda en `/etc/letsencrypt/live/contafis.miempresa.com/`.

### 6.2 Activar HTTPS en Nginx

Edita `config/nginx/prod.conf`:

```bash
vim config/nginx/prod.conf
```

**Cambios necesarios**:
1. En el bloque `server { listen 80; ... }`, **descomenta** la línea:
   ```nginx
   return 301 https://$host$request_uri;
   ```
2. En el bloque TLS (líneas 82-111), **descomenta todo el bloque** y cambia:
   - `server_name contafis.example.com;` → tu dominio real
   - Rutas `ssl_certificate` y `ssl_certificate_key` → coincidan con tu dominio en `/etc/letsencrypt/live/`

Ejemplo resultado:
```nginx
server {
    listen 80;
    server_name contafis.miempresa.com;
    return 301 https://$host$request_uri;  # <-- descomentado
    # ... resto igual ...
}

server {
    listen 443 ssl;
    http2 on;
    server_name contafis.miempresa.com;  # <-- tu dominio

    ssl_certificate     /etc/letsencrypt/live/contafis.miempresa.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/contafis.miempresa.com/privkey.pem;
    # ... resto igual ...
}
```

### 6.3 Recargar Nginx

```bash
docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

### 6.4 Verificar HTTPS

```bash
curl -I https://contafis.miempresa.com
# Debe responder 200 OK (o 302 a /web/login) con headers SSL
```

---

## 7. Configurar renovación automática de certificados

Los certificados de Let's Encrypt duran 90 días. Configura systemd timer:

```bash
# Como root
sudo tee /etc/systemd/system/certbot-renew.service > /dev/null << 'EOF'
[Unit]
Description=Renovación automática de certificados Let's Encrypt
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/renew-certs.sh
EOF

sudo tee /etc/systemd/system/certbot-renew.timer > /dev/null << 'EOF'
[Unit]
Description=Timer diario para renovación de certificados

[Timer]
OnCalendar=daily
Persistent=true
RandomizedDelaySec=12h

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now certbot-renew.timer
sudo systemctl list-timers | grep certbot
```

Verifica que el script `/usr/local/bin/renew-certs.sh` existe (lo crea `setup-vps.sh`).

---

## 8. Configurar Odoo API Key para el Assistant

El Assistant necesita una API Key read-only de Odoo para consultar datos vía JSON/2.

1. Accede a Odoo en `https://contafis.miempresa.com` (usuario `admin`, password = `admin_passwd` de `odoo.conf`).
2. Ve a **Ajustes → Usuarios → API Keys**.
3. Crea una nueva key:
   - **Usuario**: elige un usuario con permisos de lectura (ej. `admin` o usuario dedicado `api_user`).
   - **Ámbito**: `read-only` (recomendado).
   - Copia la key generada (solo se muestra una vez).
4. Edita `.env.prod` y pon el valor en `ODOO_API_KEY`.
5. Reinicia el assistant:
   ```bash
   cd /opt/contafis
   docker compose -f docker-compose.prod.yml restart assistant
   ```

---

## 9. Verificación final desde el móvil

Abre el navegador en tu móvil y ve a:
- **HTTPS**: `https://contafis.miempresa.com` → Debe cargar el login de Odoo con candado 🔒
- **Healthcheck**: `https://contafis.miempresa.com/healthz` → Debe devolver `ok`

Prueba funcionalidades clave:
1. Login con usuario contador.
2. Menú **Cumplimiento Fiscal → Libro Compras/Ventas → Exportar** → descarga XLSX.
3. Menú **Asistente (Discuss)** → escribe "¿Cuándo vence IVA este mes?" → responde el bot.
4. Digitalizar un recibo (foto) → revisa que extrae RIF, monto, IVA.

---

## 10. Comandos útiles de mantenimiento

```bash
# Ver logs de un servicio
docker compose -f docker-compose.prod.yml logs -f odoo
docker compose -f docker-compose.prod.yml logs -f assistant

# Reiniciar un servicio
docker compose -f docker-compose.prod.yml restart odoo

# Parar todo el stack
docker compose -f docker-compose.prod.yml down

# Parar y borrar volúmenes (¡CUIDADO: borra datos!)
docker compose -f docker-compose.prod.yml down -v

# Actualizar imágenes y reiniciar
cd /opt/contafis
git pull origin 19.0
docker compose -f docker-compose.prod.yml up -d --build

# Backup de la BD (ejecutar en host)
docker compose -f docker-compose.prod.yml exec -T db pg_dump -U odoo postgres > backup_$(date +%F).sql

# Restaurar BD
cat backup_2026-11-13.sql | docker compose -f docker-compose.prod.yml exec -T db psql -U odoo postgres

# Ver uso de recursos
docker stats
```

---

## 11. Troubleshooting rápido

| Síntoma | Causa probable | Solución |
|---------|----------------|----------|
| `assistant` en `unhealthy` / reinicia constante | Falta `OPENAI_API_KEY` o key inválida | Verifica `.env.prod` y que la key NVIDIA NIM tenga créditos |
| `odoo` tarda > 5 min en `healthy` | Migraciones pesadas / poca RAM | `docker compose logs -f odoo` para ver progreso; baja `ODOO_WORKERS` a 2 |
| Error 502 Bad Gateway en HTTPS | Nginx no resuelve `odoo` / `assistant` | `docker compose ps` → todos healthy? `docker compose restart nginx` |
| Certbot falla "connection refused" | Puerto 80 bloqueado / DNS no propagado | Verifica UFW (`ufw status`), `dig` tu dominio, espera propagación DNS |
| "Disk full" / contenedores parados | Volúmenes llenos (filestore, chroma, logs) | `docker system prune -a --volumes` (cuidado: borra datos no usados) |

---

## 12. Seguridad adicional (opcional pero recomendado)

- **Fail2ban** para SSH: `sudo apt install fail2ban && sudo systemctl enable --now fail2ban`
- **SSH solo con llaves**: desactiva `PasswordAuthentication` en `/etc/ssh/sshd_config`
- **Restringir acceso a puertos 8069/8072/8000** al VPS (solo nginx expone 80/443; el compose ya usa red interna)
- **Backups automáticos** diarios de PostgreSQL y filestore a almacenamiento externo (S3, Wasabi, Backblaze B2)

---

## Referencias

- `docker-compose.prod.yml` — Definición completa del stack (5 servicios, redes, volúmenes, healthchecks).
- `.env.prod.example` — Plantilla de variables de entorno con descripciones.
- `config/nginx/prod.conf` — Reverse proxy con HTTP→HTTPS redirect y webroot Certbot.
- `scripts/setup-vps.sh` — Automatización de esta guía (ejecutar una vez por VPS nuevo).
- `docs/constitution.md` — Principios de arquitectura del proyecto.

---

*Última actualización: 2026-11-13 | Rama: 19.0 (Odoo 19)*
