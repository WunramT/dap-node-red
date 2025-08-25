# DAP Node-RED Management Platform

Ein umfassendes Management-System für die Verwaltung und Bereitstellung von Node-RED Flows auf mehreren Linux-Servern mit Multi-Instance-Unterstützung.

## 🎯 Hauptfunktionen

- **Multi-Server-Deployment**: Deployment von Node-RED Flows auf mehrere Server gleichzeitig
- **Multi-Instance-Support**: Mehrere Node-RED Instanzen pro Server mit unterschiedlichen Umgebungsvariablen
- **Template-System**: Wiederverwendbare Flow-Templates mit Jinja2-Variablenersetzung
- **Backup-Management**: Automatische Backups mit Target-Backup-Funktionalität
- **SSH-basiertes Deployment**: Sichere Deployments ohne Harbor-Registry
- **GitLab CI/CD Integration**: Automatische Tests und Deployments
- **Web-Interface**: Vue3/Vuetify Frontend für einfache Verwaltung

## 📋 Voraussetzungen

### Entwicklung (DevContainer)
- VS Code mit Remote-Containers Extension
- Docker oder Podman
- Git

### Production Server
- Linux (Ubuntu 20.04+ empfohlen) oder Windows Server 2019+
- Docker oder Podman
- SSH-Zugang
- Python 3.11+
- Node.js 18+
- PostgreSQL 14+

## 🚀 Schnellstart

### 1. DevContainer starten

```bash
# Repository klonen
git clone https://gitlab.company.com/dap/dap_node_red.git
cd dap_node_red

# In VS Code öffnen
code .

# DevContainer starten (F1 -> "Remote-Containers: Reopen in Container")
```

### 2. Backend starten

```bash
cd backend

# Datenbank-Migrationen ausführen
alembic upgrade head

# Backend-Server starten
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Frontend starten

```bash
cd frontend

# Dependencies installieren
npm install

# Development Server starten
npm run dev
```

Das Frontend ist dann unter http://localhost:2999 erreichbar.

### 4. Templates importieren

```bash
# Alle Templates importieren
python scripts/import_templates.py --all

# Einzelnes Template importieren
python scripts/import_templates.py --template opc-ua-collector
```

## 🏗️ Projektstruktur

```
dap_node_red/
├── backend/               # FastAPI Backend
│   ├── app/
│   │   ├── api/          # REST API Endpoints
│   │   ├── core/         # Core-Konfiguration
│   │   ├── models/       # SQLAlchemy Models
│   │   └── services/     # Business Logic
│   └── tests/            # Backend Tests
├── frontend/             # Vue3 Frontend
│   ├── src/
│   │   ├── views/        # UI Views
│   │   ├── components/   # Vue Components
│   │   └── stores/       # Pinia Stores
│   └── tests/            # Frontend Tests
├── flow-templates/       # Node-RED Flow Templates
├── deployments/          # Deployment Manifeste
├── scripts/              # Utility Scripts
└── .devcontainer/        # DevContainer Konfiguration
```

## 🧪 Testing

### Backend Tests

```bash
cd backend

# Alle Tests ausführen
./run_tests.sh all

# Nur Unit Tests
./run_tests.sh unit

# Nur Integration Tests
./run_tests.sh integration

# Service-spezifische Tests
./run_tests.sh template    # Template Service
./run_tests.sh ssh         # SSH Service
./run_tests.sh deployment  # Deployment Service
./run_tests.sh backup      # Backup Service

# Mit Coverage Report
pytest --cov=app --cov-report=html
# Report öffnen: backend/htmlcov/index.html
```

### Frontend Tests

```bash
cd frontend

# Unit Tests
npm run test:unit

# E2E Tests
npm run test:e2e

# Mit Coverage
npm run test:coverage
```

### Template Validation

```bash
# Einzelnes Template validieren
python scripts/validate_template.py --template flow-templates/opc-ua-collector

# Alle Templates validieren
for template in flow-templates/*/; do
    python scripts/validate_template.py --template "$template"
done
```

## 🚢 Deployment

### Server vorbereiten

**Linux Server:**
```bash
# Setup-Script auf Zielserver ausführen
wget https://gitlab.company.com/dap/dap_node_red/raw/main/scripts/setup_server.sh
chmod +x setup_server.sh
sudo ./setup_server.sh -u nodered -s "ssh-rsa AAAAB3..."
```

**Windows Server:**
```powershell
# Als Administrator ausführen
.\setup_server.ps1 -User nodered -SSHKey "ssh-rsa AAAAB3..."
```

### Deployment ausführen

**Manuell:**
```bash
# Dry-run (Simulation)
python scripts/deploy.py --manifest deployments/production/default.yaml --dry-run

# Tatsächliches Deployment
python scripts/deploy.py --manifest deployments/production/default.yaml
```

**Über GitLab CI/CD:**
```yaml
# Push zu develop Branch triggert Staging Deployment
git push origin develop

# Push zu main Branch triggert Production Deployment
git push origin main
```

## 📊 Monitoring & Wartung

### Instance Health Check

```bash
# Auf Zielserver
/opt/node-red/health_check.sh

# Remote über SSH
ssh nodered@server "/opt/node-red/health_check.sh"
```

### Backup Management

```bash
# Backup erstellen
/opt/node-red/backup.sh all

# Backup einer spezifischen Instanz
/opt/node-red/backup.sh instance_name

# Alte Backups aufräumen (älter als 30 Tage)
python scripts/cleanup_backups.py --days 30
```

### Monitoring

```bash
# Auf Zielserver
/opt/node-red/monitor.sh

# Über API
curl http://localhost:8000/api/monitoring/status
```

## 🔧 Konfiguration

### Umgebungsvariablen (.env)

```env
# Database
DATABASE_URL=postgresql://dap_user:password@localhost:5431/dap_nodered

# API
SECRET_KEY=your-secret-key-change-this
CORS_ORIGINS=["http://localhost:2999"]

# SSH
SSH_KEY_PATH=/workspace/dap_node_red/keys/id_rsa
SSH_TIMEOUT=30

# Node-RED
NODERED_BASE_PATH=/opt/node-red
NODERED_IMAGE=nodered/node-red:latest

# Backup
BACKUP_PATH=/opt/backups
BACKUP_RETENTION_DAYS=30
```

### Deployment Manifest

```yaml
deployment:
  name: "Production Deployment"
  template_id: 1
  template_version: "1.0.0"
  
  global_variables:
    MQTT_BROKER_HOST: "mqtt.company.local"
    MQTT_BROKER_PORT: 1883
  
  targets:
    - server_id: 1
      instances:
        - name: "machine_1"
          port: 1881
          variables:
            MACHINE_ID: "M001"
            OPC_URL: "opc.tcp://192.168.1.100:4840"
        
        - name: "machine_2"
          port: 1882
          variables:
            MACHINE_ID: "M002"
            OPC_URL: "opc.tcp://192.168.1.101:4840"
```

## 🐛 Troubleshooting

### Container startet nicht

```bash
# Logs prüfen
podman logs nodered_instance_name

# Port-Konflikte prüfen
netstat -tulpn | grep 188

# Container-Status prüfen
podman ps -a | grep nodered
```

### SSH-Verbindung schlägt fehl

```bash
# SSH-Key Permissions prüfen
chmod 600 ~/.ssh/id_rsa

# SSH-Verbindung testen
ssh -v nodered@server
```

### Template-Import schlägt fehl

```bash
# Template validieren
python scripts/validate_template.py --template flow-templates/template-name

# JSON-Syntax prüfen
python -m json.tool flow-templates/template-name/flows.json
```

## 📚 API Dokumentation

Die vollständige API-Dokumentation ist verfügbar unter:
- http://localhost:8000/docs (Swagger UI)
- http://localhost:8000/redoc (ReDoc)

### Wichtige Endpoints

```bash
# Templates
GET    /api/templates          # Liste aller Templates
POST   /api/templates          # Neues Template erstellen
GET    /api/templates/{id}     # Template Details
PUT    /api/templates/{id}     # Template aktualisieren
DELETE /api/templates/{id}     # Template löschen

# Deployments
GET    /api/deployments        # Liste aller Deployments
POST   /api/deployments        # Neues Deployment erstellen
GET    /api/deployments/{id}   # Deployment Status
POST   /api/deployments/{id}/rollback  # Deployment zurückrollen

# Servers
GET    /api/servers            # Liste aller Server
POST   /api/servers            # Server hinzufügen
PUT    /api/servers/{id}       # Server aktualisieren
DELETE /api/servers/{id}       # Server entfernen

# Backups
GET    /api/backups            # Liste aller Backups
POST   /api/backups            # Backup erstellen
POST   /api/backups/{id}/restore  # Backup wiederherstellen
POST   /api/backups/{id}/target   # Als Target-Backup setzen
```

## 🔐 Sicherheit

- SSH-Key-basierte Authentifizierung für Server-Zugriff
- JWT-Token für API-Authentifizierung
- Verschlüsselte Passwort-Speicherung
- CORS-Protection
- SQL-Injection Prevention durch SQLAlchemy ORM
- Input Validation auf allen API-Endpoints

## 🤝 Contributing

1. Feature Branch erstellen (`git checkout -b feature/AmazingFeature`)
2. Änderungen committen (`git commit -m 'Add some AmazingFeature'`)
3. Branch pushen (`git push origin feature/AmazingFeature`)
4. Merge Request erstellen

## 📝 Lizenz

Proprietär - Alle Rechte vorbehalten