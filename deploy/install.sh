#!/usr/bin/env bash
# ==============================================================================
# MikroTik Cloud Orchestrator - Automated VPS Installation Script
# Supported OS: Ubuntu 20.04/22.04/24.04, Debian 11/12
# ==============================================================================

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=====================================================${NC}"
echo -e "${BLUE}    MikroTik Cloud Orchestrator - VPS Installer     ${NC}"
echo -e "${BLUE}=====================================================${NC}"

# Check root privileges
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}[ERROR] Este script debe ejecutarse como root (sudo bash install.sh)${NC}"
  exit 1
fi

echo -e "${GREEN}[1/5] Actualizando repositorios e instalando dependencias básicas...${NC}"
apt-get update -y
apt-get install -y curl git ufw ca-certificates gnupg lsb-release

# Install Docker if missing
if ! command -v docker &> /dev/null; then
    echo -e "${GREEN}[2/5] Instalando Docker Engine...${NC}"
    curl -fsSL https://get.docker.com | sh
    systemctl enable --now docker
else
    echo -e "${GREEN}[2/5] Docker ya está instalado. Continuando...${NC}"
fi

# Ensure Docker Compose plugin is available
if ! docker compose version &> /dev/null; then
    echo -e "${GREEN}Instalando docker-compose-plugin...${NC}"
    apt-get install -y docker-compose-plugin
fi

# Setup App Directory
INSTALL_DIR="/opt/mikrotik-orchestrator"
if [ ! -d "$INSTALL_DIR" ]; then
    echo -e "${GREEN}Clonando repositorio en $INSTALL_DIR...${NC}"
    git clone https://github.com/svasmifibra-glitch/mikrotik-orchestrator.git "$INSTALL_DIR"
else
    echo -e "${GREEN}Actualizando repositorio en $INSTALL_DIR...${NC}"
    cd "$INSTALL_DIR" && git pull || true
fi

cd "$INSTALL_DIR"

# Detect IP non-interactively if stdin is a pipe, or prompt if interactive
if [ -t 0 ]; then
    echo -e "${YELLOW}Ingresa tu Nombre de Dominio o Dirección IP Pública de este VPS:${NC}"
    read -p "Dominio / IP: " SERVER_DOMAIN
fi

if [ -z "$SERVER_DOMAIN" ]; then
    SERVER_DOMAIN=$(curl -s https://api.ipify.org || curl -s ifconfig.me || echo "localhost")
    echo -e "${GREEN}Usando IP pública detectada: $SERVER_DOMAIN${NC}"
fi

# Generate secure random secret keys
SECRET_KEY=$(openssl rand -hex 32)
POSTGRES_PASS=$(openssl rand -hex 16)

# Create environment configuration
cat <<EOF > deploy/.env
SERVER_HOST=http://$SERVER_DOMAIN
SECRET_KEY=$SECRET_KEY
POSTGRES_PASSWORD=$POSTGRES_PASS
DATABASE_URL=postgresql://mikrotik:$POSTGRES_PASS@postgres:5432/mikrotik_orchestrator
EOF

echo -e "${GREEN}[3/5] Construyendo e iniciando contenedores Docker (FastAPI + Postgres + Nginx)...${NC}"
cd "$INSTALL_DIR/deploy"
docker compose down --remove-orphans || true
docker compose build --no-cache
docker compose up -d

echo -e "${GREEN}[4/5] Configurando Firewall UFW (Puertos 80 y 443)...${NC}"
ufw allow 80/tcp || true
ufw allow 443/tcp || true

echo -e "${BLUE}=====================================================${NC}"
echo -e "${GREEN} ¡INSTALACIÓN COMPLETADA EXITOSAMENTE! 🎉${NC}"
echo -e "${BLUE}=====================================================${NC}"
echo -e "Puedes acceder a la plataforma desde tu navegador:"
echo -e " URL Plataforma:  ${YELLOW}http://$SERVER_DOMAIN${NC}"
echo -e " Documentación:   ${YELLOW}http://$SERVER_DOMAIN/docs${NC}"
echo -e ""
echo -e " Credenciales por defecto de Administración:"
echo -e " Usuario:         ${YELLOW}admin@mikrotik.cloud${NC}"
echo -e " Contraseña:      ${YELLOW}admin123${NC}"
echo -e "${BLUE}=====================================================${NC}"
