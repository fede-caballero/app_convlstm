
# 🌩️ HailCast VPS Maintenance & Update Guide

Esta guía explica cómo mantener y actualizar el sistema HailCast desplegado en el VPS.

## 🔄 Estrategia de Actualización

### 1. Actualizar Frontend (Vercel)
**Automático**: Simplemente haz `git push` a la rama principal (o la configurada en Vercel). Vercel detectará el cambio, reconstruirá la aplicación y la desplegará automáticamente.
- **Nota**: Si cambias variables de entorno en Vercel, recuerda hacer un Redeploy manual.

### 2. Actualizar Backend (VPS)
**Manual (pero sencillo)**:
Cuando hagas cambios en `backend/`, `tools/` o `Dockerfile.cpu`, sigue estos pasos en el VPS:

1.  **Traer cambios**:
    ```bash
    cd ~/app_convlstm
    git pull origin feature/vps-deployment  # O main, según tu rama
    ```

2.  **Reconstruir y Reiniciar**:
    ```bash
    # Reconstruye la imagen (solo si cambiaste código o dependencias)
    docker compose -f docker-compose.cpu.yml up -d --build
    
    # Si solo cambiaste .env, basta con:
    # docker compose -f docker-compose.cpu.yml restart
    ```

3.  **Verificar**:
    ```bash
    docker compose -f docker-compose.cpu.yml logs -f app_cpu
    ```

---

## 💾 Copias de Seguridad (Base de Datos)

La base de datos `radar_history.db` contiene tus usuarios y el historial de predicciones.

**Ubicación en VPS**: `~/app_convlstm/data/radar_history.db`
**Persistencia**: Esta carpeta está mapeada fuera de Docker, así que no se pierde al reiniciar contenedores.

**Cómo hacer un Backup manual a tu PC:**
Desde tu computadora local (no el VPS):
```bash
scp root@<IP_VPS>:~/app_convlstm/data/radar_history.db ./backup_radar_history.db
```

---

## 🛠️ Solución de Problemas Comunes

**El sitio no carga**:
- Verifica el Túnel Cloudflare: `https://dash.cloudflare.com` -> Zero Trust -> Tunnels. Debe decir "Healthy".
- Verifica el contenedor: `docker compose -f docker-compose.cpu.yml ps`.

**Error de "Network Error" en el Frontend**:
- Probablemente el backend está caído o CORS está bloqueando.
- Revisa logs: `docker compose -f docker-compose.cpu.yml logs --tail 100 app_cpu`.
- Verifica `FRONTEND_URL` en `.env`.

**El modelo no predice (Worker clavado)**:
- Revisa logs del worker: `docker compose -f docker-compose.cpu.yml logs app_cpu | grep "Worker"`.
- Puede reiniciarse solo el worker reiniciando el contenedor.
