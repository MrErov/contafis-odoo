#!/usr/bin/env bash
# =============================================================================
# setup-vps.sh — Inicialización de VPS para ContaFis (Ubuntu 22.04/24.04)
# =============================================================================
#
# Este script prepara un VPS limpio para ejecutar el stack docker-compose.prod.yml
# de ContaFis. Debe ejecutarse como root o con sudo.
#
# Qué hace:
#   1. Actualiza paquetes e instala dependencias base
#   2. Instala Docker Engine + Docker Compose plugin
#   3. Configura UFW (puertos 22 SSH, 80 HTTP, 443 HTTPS)
#   4. Crea usuario no-root 'contafis' y lo añade al grupo docker
#   5. Prepara el directorio del proyecto /opt/contafis
#   6. (Opcional) Instala certbot para certificados Let's Encrypt
#
# Uso:
#   curl -fsSL https://raw.githubusercontent.com/MrErov/contafis-odoo/19.0/scripts/setup-vps.sh | sudo bash
#   # O descargar, revisar y ejecutar:
#   wget https://raw.githubusercontent.com/MrErov/contafis-odoo/19.0/scripts/setup-vps.sh
#   chmod +x setup-vps.sh
#   sudo ./setup-vps.sh
#
# =============================================================================

set -euo pipefail

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # Sin color

log_info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[OK]${NC}  $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*"; }

# -----------------------------------------------------------------------------
# Comprobaciones previas
# -----------------------------------------------------------------------------
if [[ $EUID -ne 0 ]]; then
    log_error "Este script debe ejecutarse como root (sudo)."
    exit 1
fi

# Detectar Ubuntu version
if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    log_info "Detectado: $PRETTY_NAME"
    if [[ "$ID" != "ubuntu" ]] || [[ ! "$VERSION_ID" =~ ^(22\.04|24\.04)$ ]]; then
        log_warn "Este script está probado en Ubuntu 22.04/24.04. Continuando..."
    fi
else
    log_warn "No se pudo detectar la distribución. Asumiendo Ubuntu compatible."
fi

# -----------------------------------------------------------------------------
# 1. Actualizar sistema e instalar dependencias base
# -----------------------------------------------------------------------------
log_info "Actualizando lista de paquetes..."
apt-get update -y

log_info "Instalando dependencias base (curl, gnupg, lsb-release, ca-certificates, ufw, git, vim)..."
apt-get install -y \
    curl \
    gnupg \
    lsb-release \
    ca-certificates \
    ufw \
    git \
    vim \
    apt-transport-https \
    software-properties-common

# -----------------------------------------------------------------------------
# 2. Instalar Docker Engine + Docker Compose plugin
# -----------------------------------------------------------------------------
log_info "Configurando repositorio oficial de Docker..."

# Añadir clave GPG de Docker
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --batch --yes --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

# Añadir repositorio
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list

apt-get update -y

log_info "Instalando Docker Engine, CLI y Compose plugin..."
apt-get install -y \
    docker-ce \
    docker-ce-cli \
    containerd.io \
    docker-buildx-plugin \
    docker-compose-plugin

# Verificar instalación
docker version
docker compose version
log_success "Docker instalado correctamente."

# -----------------------------------------------------------------------------
# 3. Configurar UFW (firewall)
# -----------------------------------------------------------------------------
log_info "Configurando UFW (permitir 22/SSH, 80/HTTP, 443/HTTPS)..."

# Resetear a defaults (deny incoming, allow outgoing)
ufw --force reset
ufw default deny incoming
ufw default allow outgoing

# Reglas necesarias
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment "HTTP (Let's Encrypt challenge + redirect)"
ufw allow 443/tcp comment 'HTTPS'

# Habilitar firewall
ufw --force enable

log_success "UFW configurado y activo."
ufw status verbose

# -----------------------------------------------------------------------------
# 4. Crear usuario 'contafis' no-root
# -----------------------------------------------------------------------------
log_info "Creando usuario 'contafis' y añadiendo al grupo docker..."

if id "contafis" &>/dev/null; then
    log_warn "El usuario 'contafis' ya existe. Saltando creación."
else
    adduser --disabled-password --gecos "" contafis
    log_success "Usuario 'contafis' creado."
fi

usermod -aG docker contafis
log_success "Usuario 'contafis' añadido al grupo docker."

# Configurar sudo sin password para contafis (opcional, para comodidad en deploy)
echo "contafis ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/contafis
chmod 440 /etc/sudoers.d/contafis
log_info "Configurado sudo sin password para 'contafis' (para deploy automático)."

# -----------------------------------------------------------------------------
# 5. Preparar directorio del proyecto
# -----------------------------------------------------------------------------
PROJECT_DIR="/opt/contafis"
log_info "Creando directorio del proyecto en $PROJECT_DIR..."

mkdir -p "$PROJECT_DIR"
chown contafis:contafis "$PROJECT_DIR"
chmod 755 "$PROJECT_DIR"

# También crear directorio para certbot (se usa en nginx)
mkdir -p /var/www/certbot
chown -R contafis:contafis /var/www/certbot

log_success "Directorio $PROJECT_DIR listo (owner: contafis)."

# -----------------------------------------------------------------------------
# 6. (Opcional) Instalar certbot para Let's Encrypt
# -----------------------------------------------------------------------------
log_info "Instalando certbot (para certificados TLS)..."
apt-get install -y certbot

# Crear script helper para renovación automática
cat > /usr/local/bin/renew-certs.sh << 'EOF'
#!/usr/bin/env bash
# Renovación automática de certificados Let's Encrypt
# Se ejecuta via systemd timer o cron (ver docs/DEPLOY_VPS.md)

set -euo pipefail

certbot renew --webroot -w /var/www/certbot --quiet --no-self-upgrade

# Recargar nginx para cargar nuevos certificados
docker compose -f /opt/contafis/docker-compose.prod.yml exec nginx nginx -s reload 2>/dev/null || true
EOF

chmod +x /usr/local/bin/renew-certs.sh
log_success "Certbot instalado y script de renovación creado en /usr/local/bin/renew-certs.sh"

# -----------------------------------------------------------------------------
# 7. Configurar swap (recomendado para VPS con 4GB RAM)
# -----------------------------------------------------------------------------
if ! swapon --show | grep -q '^/swapfile'; then
    log_info "Creando archivo de swap de 2GB (recomendado para 4GB RAM)..."
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    log_success "Swap de 2GB creado y activado."
else
    log_info "Swap ya configurado."
fi

# -----------------------------------------------------------------------------
# Resumen final
# -----------------------------------------------------------------------------
echo
echo "====================================================================="
log_success "¡Inicialización del VPS completada!"
echo "====================================================================="
echo
echo "Próximos pasos (como usuario 'contafis'):"
echo "  1. sudo -iu contafis"
echo "  2. cd /opt/contafis"
echo "  3. git clone https://github.com/MrErov/contafis-odoo.git . -b 19.0"
echo "  4. cp .env.prod.example .env.prod   # Editar con valores reales"
echo "  5. Editar config/odoo.conf/odoo.conf (ver .gitignore)"
echo "  6. docker compose -f docker-compose.prod.yml up -d --build"
echo "  7. Obtener certificado TLS: sudo certbot certonly --webroot -w /var/www/certbot -d tudominio.com"
echo "  8. Descomentar bloque 443 en config/nginx/prod.conf y recargar nginx"
echo
echo "Documentación completa: docs/DEPLOY_VPS.md"
echo
