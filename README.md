# ⚡ MikroTik Cloud Orchestrator

Una plataforma completa de orquestación, monitoreo y gestión masiva para routers **MikroTik RouterOS**, inspirada en la arquitectura de **Cloutik**. 

Desarrollada para funcionar mediante aprovisionamiento automático mediante agentes o conexión directa (REST API / SSH), permitiendo administrar routers **detrás de NAT/CGNAT/4G LTE** sin necesidad de IP pública en los equipos clientelares.

---

## 🚀 Características Principales (Cloutik Architecture)

- **Panel Centralizado**: Visualización en tiempo real del estado de la flota (CPU, Memoria, Disco, Uptime, versión de RouterOS, Modelo y Número de Serie).
- **Aprovisionamiento en 1 Clic (Agent Pull / HTTPS Fetch)**: Genera un comando de 1 sola línea para pegar en el Terminal de MikroTik. El router realiza un polling periódico enviando telemetría y consultando tareas pendientes.
- **Respaldos Automáticos (.rsc / export)**: Generación y almacenamiento seguro de configuraciones con historial y visor de diferencias (Diff).
- **Ejecución Masiva de Scripts (Batch Tasks)**: Envío simultáneo de comandos RouterOS a 1 o múltiples routers (ej: cambiar contraseñas, actualizar servidores DNS, aplicar reglas de firewall).
- **Gestión y Actualización de Firmware**: Detección de versiones obsoletas y actualización masiva de la flota a la versión estable recomendada.
- **Alertas y Notificaciones**: Generación automática de alertas por alto consumo de CPU o pérdida de conectividad.
- **Doble Modelo de Despliegue**:
  1. **VPS Autohospedado**: Script de 1 solo clic (`install.sh`) usando Docker Compose, Nginx y PostgreSQL.
  2. **Vercel Serverless**: Listo para desplegar en Vercel con backend FastAPI serverless y base de datos Supabase / Neon / PostgreSQL.

---

## 🛠️ Estructura del Proyecto

```
mikrotik-orchestrator/
├── backend/
│   ├── app/
│   │   ├── api/v1/         # Endpoints (auth, routers, backups, tasks, agent, firmware)
│   │   ├── core/           # Configuración, base de datos SQLAlchemy, seguridad JWT
│   │   ├── models/         # Modelos de base de datos (Router, Backup, Task, User, Alert)
│   │   ├── schemas/        # Validadores Pydantic
│   │   ├── services/       # Cliente MikroTik (REST/SSH), script provisioner, task runner
│   │   ├── static/         # Dashboard Web Interactivo (HTML5 + Tailwind CSS + Lucide Icons)
│   │   └── main.py         # Punto de entrada FastAPI
│   ├── Dockerfile
│   └── requirements.txt
├── deploy/
│   ├── docker-compose.yml  # PostgreSQL + Backend + Nginx
│   ├── install.sh          # Script automatizado para VPS Ubuntu/Debian
│   └── nginx.conf          # Reverse proxy para SSL y WebSockets
├── api/
│   └── index.py            # Adaptador Serverless para Vercel
├── vercel.json             # Configuración de despliegue Vercel
└── README.md
```

---

## ⚡ 1. Despliegue en VPS (Recomendado)

En tu VPS (Ubuntu 20.04 / 22.04 / 24.04 o Debian 11/12), ejecuta como `root`:

```bash
curl -sSL https://raw.githubusercontent.com/svasmifibra-glitch/mikrotik-orchestrator/main/deploy/install.sh | bash
```

O clonando el repositorio:

```bash
git clone https://github.com/svasmifibra-glitch/mikrotik-orchestrator.git
cd mikrotik-orchestrator/deploy
chmod +x install.sh
sudo ./install.sh
```

---

## ☁️ 2. Despliegue en VERCEL + Base de Datos Cloud

1. Conecta este repositorio a tu cuenta de **Vercel**.
2. En las Variables de Entorno de Vercel (Environment Variables), agrega:
   - `DATABASE_URL`: URL de tu PostgreSQL en **Supabase**, **Neon.tech** o **ElephantSQL** (ej: `postgresql://user:pass@ep-xxx.neon.tech/neondb`).
   - `SECRET_KEY`: Tu clave secreta JWT.
   - `SERVER_HOST`: La URL de tu dominio en Vercel (ej: `https://mi-mikrotik-orchestrator.vercel.app`).
3. Presiona **Deploy**. Vercel desplegará automáticamente la API en Serverless Functions (`/api/*`) y el Dashboard frontend.

---

## 💻 3. Ejecución Local para Desarrollo (Pruebas)

1. Crear un entorno virtual de Python:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate   # En Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Iniciar el servidor FastAPI:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
3. Abre en tu navegador:
   - **Dashboard Web**: `http://localhost:8000`
   - **Documentación Swagger API**: `http://localhost:8000/docs`

---

## 🔑 Credenciales por Defecto de Administración

- **Usuario**: `admin@mikrotik.cloud`
- **Contraseña**: `admin123`

---

## 📡 Cómo Vincular un Router MikroTik (Aprovisionamiento)

1. Entra a la plataforma web y haz clic en **"Agregar MikroTik"**.
2. Asigna un nombre al router y presiona **"Generar Comando"**.
3. Copia el comando generado, por ejemplo:
   ```routeros
   /tool fetch url="http://tu-vps.com/api/v1/agent/script/mt_tok_abc123" mode=http keep-result=yes dst-path="orchestrator_install.rsc"; /import orchestrator_install.rsc; /file remove orchestrator_install.rsc;
   ```
4. Pégalo en el **Terminal de WinBox** o **Webfig** de tu MikroTik router.
5. ¡Listo! El router comenzará a reportar métricas cada 5 minutos y podrás controlarlo de forma remota.
