# Guía: Configurar Dominio Propio con Cloudflare Tunnel 🌐

Para evitar bloqueos en redes móviles (4G/5G) y tener una URL profesional (ej: `app.midominio.com`), necesitas un **Dominio Propio**.

## Paso 1: Comprar un Dominio (Costo: $1 - $10 USD/año) 💰

No necesitas un dominio caro. Puedes comprar uno en:
1.  **Cloudflare Registrar** (Recomendado): Es el más barato porque vende al costo (sin recargos).
    *   Ve a [Cloudflare Dashboard](https://dash.cloudflare.com/) > **Domain Registration** > **Register Domain**.
    *   Busca algo disponible (ej: `tormenta-mendoza.com` o `.net`, `.org`).
2.  **Namecheap** o **GoDaddy**:
    *   Son populares, a veces tienen ofertas de $1 para el primer año.
    *   *Si compras aquí, tendrás que "apuntar" el dominio a Cloudflare (cambiar los Nameservers).*

## Paso 2: Conectar Dominio a Cloudflare ☁️

*Si compraste el dominio en Cloudflare, salta este paso.*

1.  Crea una cuenta gratuita en [Cloudflare](https://dash.cloudflare.com/sign-up).
2.  Haz clic en **"Add a Site"** y escribe tu dominio (ej: `midominio.com`).
3.  Selecciona el **Plan Free** (abajo de todo).
4.  Cloudflare te dará dos "Nameservers" (ej: `bob.ns.cloudflare.com`, `alice.ns.cloudflare.com`).
5.  Ve a donde compraste el dominio (Namecheap/GoDaddy), busca la configuración de **DNS / Nameservers** y reemplaza los que haya por los dos de Cloudflare.
6.  Espera unos minutos (puede tardar hasta 24h, pero suele ser rápido) hasta que Cloudflare te diga "Active".

## Paso 3: Crear el Túnel "Fijo" (Zero Trust) 🚇

Una vez tu dominio esté activo en Cloudflare:

1.  En el panel de Cloudflare (izquierda), ve a **Zero Trust** (puede pedirte activar la cuenta Zero Trust gratuita).
2.  Ve a **Networks > Tunnels** y haz clic en **Create a Tunnel**.
3.  Elige **Cloudflared**.
4.  Ponle un nombre (ej: `backend-vast`).
5.  Te mostrará un comando de instalación. **Solo necesitas el TOKEN** (la cadena larga de letras y números después de `--token`). Copia ese Token.
6.  En la siguiente pantalla ("Public Hostnames"), añade un subdominio:
    *   **Subdomain:** `api` (para que quede `api.midominio.com`) o déjalo vacío para usar la raíz.
    *   **Domain:** Selecciona tu dominio.
    *   **Service:** `HTTP` -> `localhost:8000`.
7.  Guardar.

## Paso 4: Actualizar tu Servidor (Vast.ai) 🖥️

Ahora, en lugar de ejecutar el comando que genera una URL aleatoria, usarás el Token fijo.

### Opción A: Modificar el comando manual
Cuando inicies el servidor, ejecuta:
```bash
cloudflared tunnel run --token TU_TOKEN_LARGO_AQUI > /app/logs/tunnel.log 2>&1 &
```

### Opción B: Automatizar en el Docker (Recomendado)
Agrega el token como Variable de Entorno en Vast.ai (`CLOUDFLARE_TOKEN`) y actualiza el script de inicio (`run.sh` o `vast_start.sh`) para usarlo si existe.

---

## Paso 5: Actualizar Frontend (Vercel) 🎨

1.  Ve a tu proyecto en Vercel > Settings > Environment Variables.
2.  Edita `NEXT_PUBLIC_API_URL`.
3.  Pon tu nueva URL fija: `https://api.midominio.com` (o la que hayas configurado).
4.  Redesplegar (Redeploy) el frontend.

¡Listo! Ahora tendrás conexión segura, fija y desbloqueada en todas las redes.
