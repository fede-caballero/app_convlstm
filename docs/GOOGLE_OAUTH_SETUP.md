# Guía de Configuración: Google OAuth 2.0 (Simplificado)

Para habilitar el botón "Continuar con Google", necesitamos un **Client ID** de Google Cloud.

## Paso 1: Crear Proyecto
1.  Ve a [Google Cloud Console](https://console.cloud.google.com/).
2.  Arriba a la izquierda, selecciona **"New Project"**.
3.  Nombre: `Hailcast Alert` (o similar).
4.  Haz clic en **Create**.

## Paso 2: Configurar Pantalla de Consentimiento
1.  En el menú lateral, ve a **APIs & Services** > **OAuth consent screen**.
2.  Selecciona **External** y haz clic en **Create**.
3.  **App Information**:
    *   App name: `Hailcast Alert`
    *   User support email: (Tu email)
    *   Developer contact information: (Tu email)
4.  Haz clic en **Save and Continue** (puedes saltar lo demás por ahora).

## Paso 3: Crear Credenciales (Solo JavaScript Origins)
1.  En el menú lateral, ve a **Credentials**.
2.  Haz clic en **+ CREATE CREDENTIALS** > **OAuth client ID**.
3.  **Application type**: Selecciona **Web application**.
4.  **Name**: `Hailcast Web`.
5.  **Authorized JavaScript origins** (ESTO ES LO IMPORTANTE):
    *   Haz clic en "ADD URI" y añade:
        *   `http://localhost:3000`
        *   `https://hailcast-frontend.vercel.app` (Si ya tienes URL de producción).
        *   `http://127.0.0.1:3000` (Opcional, a veces útil).
6.  **Authorized redirect URIs**:
    *   **¡DÉJALO VACÍO!** (No usamos redirección de servidor, el botón de Google lo maneja todo en la página).
7.  Haz clic en **CREATE**.

## Paso 4: Instalar en el Código
1.  Copia tu **Client ID**.
2.  Abre (o crea) el archivo `frontend/.env.local`.
3.  Añade la siguiente línea:
    ```bash
    NEXT_PUBLIC_GOOGLE_CLIENT_ID=TU_CLIENT_ID_COPIADO_AQUI.apps.googleusercontent.com
    ```
4.  Reinicia el servidor de desarrollo (`npm run dev`) para que cargue la nueva variable.
5.  ¡Listo! El botón leerá automáticamente esta configuración.
