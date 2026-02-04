# Estrategia de Despliegue Cost-Effective y Segura 🛡️🚀

Este documento detalla la arquitectura "Split" para desplegar la aplicación de Radar con seguridad (HTTPS) y bajo costo.

## 1. Arquitectura General

*   **Backend (Vast.ai) 🧠**: 
    *   Ejecuta el modelo de IA y la API en una instancia con GPU.
    *   **Costo:** Bajo demanda (~$0.20/hr).
    *   **Seguridad:** Expuesto a internet mediante **Cloudflare Tunnel** (evita abrir puertos y certificados manuales).
*   **Frontend (Vercel) 🎨**:
    *   Sirve la interfaz de usuario (Next.js).
    *   **Costo:** Gratis (Plan Hobby).
    *   **Seguridad:** HTTPS nativo y CDN global.

---

## 2. Implementación Paso a Paso

### Fase A: Backend Seguro con Cloudflare Tunnel

1.  **Instalar `cloudflared` en la imagen Docker**:
    Añadir al `Dockerfile`:
    ```dockerfile
    RUN curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb && \
        dpkg -i cloudflared.deb && \
        rm cloudflared.deb
    ```

2.  **Configurar el Túnel en `on_start_inference.sh`**:
    En lugar de esperar una IP pública, el script iniciará el túnel:
    ```bash
    # En Background
    cloudflared tunnel --url http://localhost:8000 > /app/logs/tunnel.log 2>&1 &
    ```
    *Nota:* Esto generará una URL aleatoria (ej: `https://dark-star-123.trycloudflare.com`). Para una URL fija, se requiere un dominio propio (gratis/barato) y un token de Cloudflare.

### Fase B: Frontend en Vercel

1.  **Preparar el Código**:
    *   Asegurar que la URL del backend no esté "hardcoded" en el frontend.
    *   Usar variable de entorno: `NEXT_PUBLIC_API_URL`.

2.  **Despliegue**:
    *   Subir carpeta `frontend/` a GitHub.
    *   Importar proyecto en Vercel.
    *   Configurar Environment Variable:
        `NEXT_PUBLIC_API_URL` = `https://<tu-url-de-cloudflare>.trycloudflare.com`

---

## 3. Flujo de Trabajo Operativo

1.  Inicias la instancia en Vast.ai.
2.  Obtienes la URL del túnel desde los logs (`grep "trycloudflare.com" /app/logs/tunnel.log`).
3.  Actualizas la variable en Vercel (si usas túnel aleatorio) o usas siempre la misma (si configuras dominio propio).
4.  ¡Listo! Usuarios acceden a `https://tu-proyecto.vercel.app` de forma segura.

---

## 4. Persistencia de Datos (Base de Datos) 💾

⚠️ **Importante:** Las instancias de Vast.ai son **efímeras**. Si destruyes la instancia, pierdes la base de datos de usuarios y comentarios (`/app/data/radar_history.db`).

### Estrategia de Backup (Gratis con Rclone)
Aprovechando que ya tenemos Rclone configurado para `mydrive`, podemos respaldar la DB periódicamente.

1.  **Script de Backup (`backup_db.sh`)**:
    ```bash
    #!/bin/bash
    rclone copy /app/data/radar_history.db mydrive:RadarBackups/
    echo "DB Backed up at $(date)" >> /app/logs/backup.log
    ```

2.  **Automatización (Cron)**:
    En la instancia:
    ```bash
    # Editar crontab
    crontab -e
    # Agregar: Respaldo cada hora
    0 * * * * bash /app/tools/backup_db.sh
    ```
    *(Nota: Docker a veces requiere iniciar cron manualmente `service cron start`)*.

3.  **Restauración**:
    Al iniciar una nueva instancia, descargar la DB antes de iniciar el servidor:
    ```bash
    rclone copy mydrive:RadarBackups/radar_history.db /app/data/
    ```
