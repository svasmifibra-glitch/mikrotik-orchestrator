#!/usr/bin/env bash
# ==============================================================================
# MikroTik Cloud Orchestrator - Automated VPS/LAN Installation Script
# Supported OS: Ubuntu 20.04/22.04/24.04, Debian 11/12
# ==============================================================================

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=====================================================${NC}"
echo -e "${BLUE}   MikroTik Cloud Orchestrator - VPS/LAN Installer   ${NC}"
echo -e "${BLUE}=====================================================${NC}"

# Check root privileges
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}[ERROR] Este script debe ejecutarse como root (sudo bash install.sh)${NC}"
  exit 1
fi

echo -e "${GREEN}[1/6] Actualizando repositorios e instalando dependencias básicas...${NC}"
apt-get update -y
apt-get install -y curl git ufw ca-certificates gnupg lsb-release net-tools

# Install Docker if missing
if ! command -v docker &> /dev/null; then
    echo -e "${GREEN}[2/6] Instalando Docker Engine...${NC}"
    curl -fsSL https://get.docker.com | sh
    systemctl enable --now docker
else
    echo -e "${GREEN}[2/6] Docker ya está instalado. Continuando...${NC}"
fi

# Ensure Docker Compose plugin is available
if ! docker compose version &> /dev/null; then
    echo -e "${GREEN}Instalando docker-compose-plugin...${NC}"
    apt-get install -y docker-compose-plugin
fi

# Setup App Directory
INSTALL_DIR="/opt/mikrotik-orchestrator"
if [ ! -d "$INSTALL_DIR" ]; then
    echo -e "${GREEN}[3/6] Clonando repositorio en $INSTALL_DIR...${NC}"
    git clone https://github.com/svasmifibra-glitch/mikrotik-orchestrator.git "$INSTALL_DIR"
else
    echo -e "${GREEN}[3/6] Actualizando repositorio en $INSTALL_DIR...${NC}"
    cd "$INSTALL_DIR" && git pull || true
fi

cd "$INSTALL_DIR"

# Detect Network Interfaces (LAN & WAN)
LOCAL_IP=$(ip route get 1.1.1.1 2>/dev/null | awk '{print $7}')
if [ -z "$LOCAL_IP" ]; then
    LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "127.0.0.1")
fi

PUBLIC_IP=$(curl -s --max-time 5 https://api.ipify.org || curl -s --max-time 5 https://ifconfig.me || echo "$LOCAL_IP")

# Custom Port configuration (default to 8080 if not specified)
TARGET_PORT="${PORT:-8080}"
EXTERNAL_HOST="${SERVER_DOMAIN:-$PUBLIC_IP}"

echo -e "${GREEN}[4/6] Detección de Red:${NC}"
echo -e "  - IP Privada (LAN interface):  ${YELLOW}$LOCAL_IP${NC}"
echo -e "  - IP Pública (WAN / NAT):      ${YELLOW}$PUBLIC_IP${NC}"
echo -e "  - Puerto Asignado:             ${YELLOW}$TARGET_PORT${NC}"

# Reuse existing SECRET_KEY or generate stable one
if [ -f deploy/.env ]; then
    source deploy/.env
fi

SECRET_KEY="${SECRET_KEY:-$(openssl rand -hex 32)}"
POSTGRES_PASS="mikrotik_secure_db_pass_2026"

# Create environment configuration
cat <<EOF > deploy/.env
HOST_PORT=$TARGET_PORT
LOCAL_IP=$LOCAL_IP
PUBLIC_IP=$PUBLIC_IP
SERVER_HOST=http://$EXTERNAL_HOST:$TARGET_PORT
SECRET_KEY=$SECRET_KEY
POSTGRES_PASSWORD=$POSTGRES_PASS
DATABASE_URL=postgresql://mikrotik:$POSTGRES_PASS@postgres:5432/mikrotik_orchestrator
EOF

echo -e "${GREEN}[5/6] Construyendo e iniciando contenedores Docker (FastAPI + Postgres + Nginx en puerto $TARGET_PORT)...${NC}"
cd "$INSTALL_DIR/deploy"
docker compose down --remove-orphans || true
docker compose build --no-cache
docker compose up -d

echo -e "${GREEN}[6/6] Configurando Firewall UFW (Puerto $TARGET_PORT)...${NC}"
ufw allow $TARGET_PORT/tcp || true

echo -e "${BLUE}=====================================================${NC}"
echo -e "${GREEN} ¡INSTALACIÓN COMPLETADA EXITOSAMENTE! 🎉${NC}"
echo -e "${BLUE}=====================================================${NC}"
echo -e "Puntos de Acceso al Panel Web:"
echo -e "  1. Acceso Local (LAN):       ${YELLOW}http://$LOCAL_IP:$TARGET_PORT${NC}"
echo -e "  2. Acceso Externo (WAN/NAT): ${YELLOW}http://$EXTERNAL_HOST:$TARGET_PORT${NC}"
echo -e "  3. Documentación API:        ${YELLOW}http://$LOCAL_IP:$TARGET_PORT/docs${NC}"
echo -e ""
echo -e "Credenciales por defecto de Administración:"
echo -e "  Usuario:    ${YELLOW}admin@mikrotik.cloud${NC}"
echo -e "  Contraseña: ${YELLOW}admin123${NC}"
echo -e ""
echo -e "${BLUE}-----------------------------------------------------${NC}"
echo -e "${YELLOW} Regla de NAT para copiar en tu Router MikroTik Principal:${NC}"
echo -e " /ip firewall nat add chain=dstnat action=dst-nat to-addresses=$LOCAL_IP to-ports=$TARGET_PORT protocol=tcp dst-port=$TARGET_PORT comment=\"MikroTik Orchestrator NAT\""
echo -e "${BLUE}=====================================================${NC}"
