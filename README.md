# ⚡ MikroTik Cloud Orchestrator

Una plataforma completa de orquestación, monitoreo y gestión masiva para routers **MikroTik RouterOS**, inspirada en la arquitectura de **Cloutik**. 

Desarrollada para funcionar mediante aprovisionamiento automático mediante agentes o conexión directa (REST API / SSH), permitiendo administrar routers **detrás de NAT/CGNAT/4G LTE** sin necesidad de IP pública en los equipos clientelares.

---

## 🚀 Características Principales (Cloutik Architecture)

- **Panel Centralizado**: Visualización en tiempo real del estado de la flota (CPU, Memoria, Disco, Uptime, versión de RouterOS, Modelo y Número de Serie).
- **Aprovisionamiento en 1 Clic (Agent Pull / HTTPS Fetch)**: Genera un comando de 1 sola línea para pegar en el Terminal de MikroTik. El router realiza un polling periódico enviando telemetría y consultando tareas pendientes.
- **Soporte Híbrido LAN + WAN (Port Forwarding / NAT)**: Detección automática de la IP privada del servidor (LAN) e IP pública (WAN) con generación de la regla `/ip firewall nat` para redirección automática.
- **Respaldos Automáticos (.rsc / export)**: Generación y almacenamiento seguro de configuraciones con historial y visor de diferencias (Diff).
- **Ejecutor de Tareas y Scripts Masivos (Batch Tasks)**: Envío simultáneo de comandos RouterOS a 1 o múltiples routers (ej: cambiar contraseñas, actualizar servidores DNS, aplicar reglas de firewall).
- **Gestión y Actualización de Firmware**: Detección de versiones obsoletas y actualización masiva de la flota a la versión estable recomendada.
- **Alertas y Notificaciones**: Generación automática de alertas por alto consumo de CPU o pérdida de conectividad.

---

## ⚡ 1. Despliegue en Servidor VPS o Servidor LAN

En tu servidor Linux (Ubuntu 20.04 / 22.04 / 24.04 o Debian 11/12), ejecuta como `root`:

```bash
curl -sSL https://raw.githubusercontent.com/svasmifibra-glitch/mikrotik-orchestrator/main/deploy/install.sh | bash
```

> **Nota para Servidores LAN con NAT**: Si deseas usar un puerto específico (ejemplo: `8080`), puedes indicarlo así:
> ```bash
> PORT=8080 curl -sSL https://raw.githubusercontent.com/svasmifibra-glitch/mikrotik-orchestrator/main/deploy/install.sh | bash
> ```

Al finalizar la instalación, el script te mostrará:
1. La URL de **Acceso Local (LAN)** (ej: `http://192.168.1.50:8080`).
2. La URL de **Acceso Externo (WAN)** (ej: `http://38.199.156.3:8080`).
3. La **regla de NAT** lista para copiar y pegar en tu Router MikroTik Gateway principal:
   ```routeros
   /ip firewall nat add chain=dstnat action=dst-nat to-addresses=192.168.1.50 to-ports=8080 protocol=tcp dst-port=8080 comment="MikroTik Orchestrator NAT"
   ```

---

## ☁️ 2. Despliegue en VERCEL + Base de Datos Cloud

1. Conecta este repositorio a tu cuenta de **Vercel**.
2. En las Variables de Entorno de Vercel (Environment Variables), agrega:
   - `DATABASE_URL`: URL de tu PostgreSQL en **Supabase**, **Neon.tech** o **ElephantSQL**.
   - `SECRET_KEY`: Tu clave secreta JWT.
   - `SERVER_HOST`: La URL de tu dominio en Vercel.
3. Presiona **Deploy**. Vercel desplegará automáticamente la API en Serverless Functions (`/api/*`) y el Dashboard frontend.

---

## 🔑 Credenciales por Defecto de Administración

- **Usuario**: `admin@mikrotik.cloud`
- **Contraseña**: `admin123`
