# Guía: Configurar Cloudflare Tunnel para Backend VPS 🚇

Para que tu frontend en Vercel (`https://hail-cast.vercel.app`) pueda hablar con tu backend en el VPS sin errores de seguridad ("Mixed Content"), necesitas exponer el backend con HTTPS. Usaremos **Cloudflare Tunnel** para esto.

## Requisitos
- Acceso al panel de Cloudflare.
- Acceso SSH a tu VPS.
- Dominio configurado en Cloudflare (ej. `midominio.com`).

## Paso 1: Crear el Túnel en Cloudflare
1.  Ve a **Zero Trust** > **Networks** > **Tunnels**.
2.  Haz clic en **Create a Tunnel**.
3.  Selecciona **Cloudflared**.
4.  Dale un nombre: `vps-backend`.
5.  **Instalación**:
    *   Elige "Debian" (tu VPS es Ubuntu, es compatible).
    *   Copia el comando de instalación que aparece en el cuadro (empieza con `sudo cloudflared service install...`).

## Paso 2: Ejecutar en el VPS
1.  Conéctate por SSH a tu VPS.
2.  Pega y ejecuta el comando que copiaste.
3.  Si todo va bien, verás en el panel web que el "Connector" está **Connected**.

## Paso 3: Configurar el Subdominio (Public Hostname)
1.  En el asistente de Cloudflare, dale a **Next**.
2.  **Subdomain**: Escribe `api` (o el que prefieras, ej: `backend`).
3.  **Domain**: Selecciona tu dominio (`midominio.com`).
4.  **Service**:
    *   Type: `HTTP`
    *   URL: `localhost:8000` (El puerto donde Docker expone tu backend).
5.  Guardar.

¡Listo! Ahora tu backend estará accesible en `https://api.midominio.com`.

## Paso 4: Actualizar Variables de Entorno

### En Vercel (Frontend)
1.  Ve a tu proyecto > Settings > Environment Variables.
2.  Edita `NEXT_PUBLIC_API_BASE_URL`.
3.  Pon la nueva URL segura: `https://api.midominio.com`.
4.  **Redesplegar** (Redeploy) para aplicar cambios.

### En el VPS (Backend)
1.  Edita el archivo `.env`:
    ```bash
    nano .env
    ```
2.  Actualiza también ahí la variable (para que los enlaces que genere el backend sean correctos):
    ```ini
    NEXT_PUBLIC_API_BASE_URL=https://api.midominio.com
    ```
3.  Reinicia el backend:
    ```bash
    docker compose -f docker-compose.cpu.yml restart
    ```
