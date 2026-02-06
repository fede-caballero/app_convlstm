# Manual de Despliegue y Configuración

Guía paso a paso para desplegar **Hailcast Alert** en producción (Vast.ai + Vercel) de forma segura y persistente.

## 1. Configuración de Instancia (Vast.ai + Cloudflare)

El backend corre en Vast.ai y se expone al mundo de forma segura mediante Cloudflare Tunnel.

1.  **Iniciar Instancia**: Asegúrate de que la imagen de Docker tenga instalado `cloudflared`.
2.  **Obtener URL Segura**:
    Una vez iniciada la instancia, busca la URL generada en los logs:
    ```bash
    grep "trycloudflare.com" /app/logs/tunnel.log
    ```
    *(Copia la URL que termina en `.trycloudflare.com`)*.

3.  **Conectar Frontend**:
    Ve a tu proyecto en **Vercel** -> Settings -> Environment Variables.
    *   Actualiza la variable `NEXT_PUBLIC_API_URL` con la URL que copiaste (ej: `https://slap-monkey-tennis-shoe.trycloudflare.com`).
    *   *Nota: No olvides el `https://` al principio.*

---

## 2. Persistencia de Datos (Base de Datos en Drive)

Para evitar perder usuarios y alertas al apagar la instancia, usamos **Rclone** con Google Drive.

### A. Configuración "Zero-Touch" (Recomendado)
Para que todo sea automático al iniciar:

1.  **Preparar el On-Start Script**:
    En la configuración de la plantilla de Vast.ai ("On-start script"), asegúrate de incluir:
    
    *   **Instalación Rclone**:
        ```bash
        if ! command -v rclone &> /dev/null; then
            curl https://rclone.org/install.sh | sudo bash
        fi
        ```
    
    *   **Inyección de Credenciales**:
        Copia el contenido de tu archivo local `~/.config/rclone/rclone.conf` y pégalo así:
        ```bash
        mkdir -p /root/.config/rclone
        cat <<EOF > /root/.config/rclone/rclone.conf
        [mydrive]
        type = drive
        ... (contenido de tu config) ...
        EOF
        ```

    *   **Restauración Automática**:
        Al final del script, antes de iniciar los servicios:
        ```bash
        # Restaurar DB si existe en Drive
        /app/scripts/restore_db.sh || echo "⚠️ No se encontró backup previo, iniciando limpia."
        ```

### B. Respaldo Manual (Antes de Destruir Instancia)
**¡MUY IMPORTANTE!** Antes de eliminar o detener la instancia, guarda los cambios:

1.  Abre una terminal en la instancia (SSH o Jupyter Lab).
2.  Ejecuta el script de respaldo:
    ```bash
    /app/scripts/backup_db.sh
    ```
    *Esto subirá `backend/app.db` a tu carpeta `convlstm_backups` en Drive.*

---

## 3. Seguridad (Variables de Entorno)

Para proteger la aplicación, configura estas variables en **Docker Options** (Launch Mode) en Vast.ai.
**No escribas estas claves en archivos de texto.**

Añade esto al campo de opciones de Docker:
```bash
-e SECRET_KEY="TU_CLAVE_LARGA_GENERADA" -e FRONTEND_URL="https://hailcast.vercel.app"
```

*   **SECRET_KEY**: Generada con `openssl rand -hex 32`. Protege las sesiones y tokens.
*   **FRONTEND_URL**: La URL real de tu web en Vercel. Bloquea peticiones de otros sitios (CORS).
