# Configurar Servidor de Correos (SMTP) para Hailcast

Para que Hailcast pueda enviar correos reales (Bienvenida y Recuperación de Contraseña), necesitas configurar credenciales SMTP en el Backend. La forma más sencilla, gratuita y confiable para iniciar es usar una cuenta de **Gmail** con una "Contraseña de Aplicación".

## Paso 1: Configurar cuenta de Gmail

Para usar una cuenta de Google, por seguridad no debes usar tu contraseña real, sino crear una **Contraseña de Aplicación**:

1. Ve a la configuración de seguridad de tu cuenta de Google: [https://myaccount.google.com/security](https://myaccount.google.com/security)
2. Asegúrate de tener activada la **Verificación en dos pasos**.
3. Ve a la sección **Contraseñas de aplicaciones** (App Passwords) o usa el buscador de tu cuenta y busca "App Passwords".
4. Crea una contrasña nueva. Asignale un nombre que reconozcas, como `Hailcast Backend`.
5. Google te mostrará una contraseña de **16 letras**. Cópiala, porque no la volverás a ver.

## Paso 2: Configurar el Backend (Local)

En tu PC de desarrollo, debes editar el archivo `.env` del backend (ubicado en `backend/.env`) y agregar las siguientes variables de entorno. 

```env
# ----- CONFIGURACIÓN SMTP GMAIL ----- 
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER="tucorreo@gmail.com"
SMTP_PASS="xxxx xxxx xxxx xxxx"     # La contraseña de 16 letras que generaste en el Paso 1 (sin espacios)
FROM_EMAIL="tucorreo@gmail.com"
```

1. Guarda el archivo `.env`
2. Reinicia el backend de FastAPI (`python3 api.py` o tmux).

## Paso 3: Configurar el Servidor en Producción (VPS)

En tu servidor VPS, debes hacer exactamente lo mismo. Como usas Docker Compose, debes pasar estas variables al contenedor del backend:

1. Entra por SSH a tu VPS de Hostinger.
2. Ve a la carpeta del proyecto:
   ```bash
   cd ~/app_convlstm
   ```
3. Edita tu archivo `.env`
   ```bash
   nano backend/.env
   ```
4. Agrega las configuraciones SMTP de arriba al final del archivo.
5. Presiona `Ctrl+X`, luego `Y` y finalmente `Enter` para guardar changes.
6. Reinicia el contenedor del backend para que tome las nuevas variables:
   ```bash
   docker compose -f docker-compose.cpu.yml restart backend
   ```

¡Con estos simples pasos ya estará funcionando el envío automático de correos (Avisos y recuperación de password)! Si falla la conexión a Gmail, revisa los logs del Docker o del backend para ver si de casualidad la red del VPS bloquea el puerto 587 (poco probable).
