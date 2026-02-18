# Despliegue en VPS usando Git y Docker Compose 🚀

Esta es la estrategia recomendada para mantener tu aplicación actualizada de forma sencilla. El flujo es: **Cambios Locales -> GitHub -> VPS (Pull & Restart)**.

## 1. Preparación del Repositorio (Local)

Asegúrate de tener los archivos para CPU en la raíz de tu proyecto y comitearlos:

1.  **Archivos Clave**:
    *   `Dockerfile.cpu` (La imagen optimizada para Ubuntu/LROSE).
    *   `docker-compose.cpu.yml` (La orquestación de servicios).
    *   `lrose-core-20250105.ubuntu_22.04.amd64.deb` (El instalador de LROSE, necesario para construir la imagen).

2.  **Commit y Push**:
    ```bash
    git add Dockerfile.cpu docker-compose.cpu.yml lrose-core-20250105.ubuntu_22.04.amd64.deb
    git commit -m "Add VPS deployment config"
    git push origin main
    ```

## 2. Preparación del VPS (Solo la primera vez)

Conéctate a tu VPS y clona el repositorio:

```bash
# Instalar Docker si no lo tienes
curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh get-docker.sh

# Clonar tu repo
git clone https://github.com/usuario/mi-proyecto.git app_convlstm
cd app_convlstm

# Copiar tu modelo entrenado (no se sube a git por peso)
# Desde tu PC local:
scp ruta/local/modelo.pth usuario@ip-vps:~/app_convlstm/model/

# Configurar variables de entorno (Crear .env)
nano .env
# Pega tus claves VAPID_PRIVATE_KEY, etc.
```

## 3. Flujo de Actualización (Día a día)

Cada vez que hagas cambios en tu código local y hagas `git push`:

1.  **Entra al VPS**: `ssh usuario@ip-vps`
2.  **Ve a la carpeta**: `cd app_convlstm`
3.  **Descarga cambios**: `git pull origin main`
4.  **Reinicia servicios**:
    ```bash
    # Esto reconstruye la imagen si hubo cambios en el código y levanta todo de nuevo
    docker compose -f docker-compose.cpu.yml up -d --build
    ```

### Nota Importante
Usamos `-f docker-compose.cpu.yml` explícitamente porque queremos usar la configuración de CPU, no la de GPU por defecto (`docker-compose.yml`).

Si quieres simplificar, puedes añadir un alias en el VPS:
`alias deploy="git pull && docker compose -f docker-compose.cpu.yml up -d --build"`
Y luego solo escribes `deploy`.
