# Guía de Persistencia de Base de Datos con Rclone

Esta guía explica cómo configurar `rclone` para guardar y recuperar tu base de datos (`app.db`) en Google Drive, permitiéndote conservar tus usuarios y alertas incluso si destruyes la instancia de Vast.ai/Docker.

## 1. Instalación (Solo una vez por Instancia)

Si tu instancia no tiene `rclone` instalado (las imágenes mínimas de Docker no suelen tenerlo), instálalo:

```bash
curl https://rclone.org/install.sh | sudo bash
```

## 2. Configuración Inicial (Solo la primera vez)

Debes autorizar a rclone para acceder a tu Google Drive.

1.  Ejecuta:
    ```bash
    rclone config
    ```
2.  Responde a las preguntas:
    *   **n** (New remote)
    *   name: **gdrive**
    *   Storage: Busca "Google Drive" (suele ser el número 18 o similar). Escribe el número.
    *   Client Id/Secret: Déjalos vacíos (Enter).
    *   Scope: Elige **1** (Full access) o lo que prefieras.
    *   root_folder_id: Vacío.
    *   Service Account: Vacío.
    *   Edit advanced config: **n**.
    *   **Remote config (Use auto config?):** **n** (Importante si estás en una terminal remota sin navegador).
    *   Te dará una URL. Cópiala y pégala en TU navegador local.
    *   Autoriza con tu cuenta de Google.
    *   Copia el **Verification Code** que te da Google y pégalo en la terminal.
    *   **Team Drive:** **n**.
    *   **y** (Yes this is OK).
    *   **q** (Quit).

¡Listo! Rclone ya tiene acceso.

## 3. Uso Diario

Hemos preparado scripts para facilitarte la vida en la carpeta `scripts/`.

### Hacer Backup (Guardar DB en la Nube)
Ejecuta esto antes de destruir la instancia o periódicamente:

```bash
./scripts/backup_db.sh
```
*Esto copiará `backend/app.db` a la carpeta `convlstm_backups/` en tu Drive.*

### Restaurar Backup (Recuperar DB de la Nube)
Ejecuta esto **inmediatamente después** de levantar una nueva instancia limpia:

```bash
./scripts/restore_db.sh
```
*Esto descargará `app.db` desde Drive y sobrescribirá la base de datos vacía actual.*

> [!WARNING]
> Restaurar sobrescribirá cualquier dato nuevo que hayas creado en la instancia actual. Hazlo siempre al principio.
