# Gestión de Usuarios y Base de Datos

El backend de *HailCast* (app_convlstm) utiliza una base de datos SQLite guardada localmente en `/app/data/radar_history.db` dentro del contenedor de Docker. Esta guía explica cómo gestionar los usuarios registrados en el sistema, darles permisos de administrador, o eliminarlos.

## 1. Acceder al Contenedor del Backend

Para ejecutar cualquier script o comando SQL, primero tenés que entrar a la consola (bash) del contenedor del backend donde se está ejecutando la aplicación:

```bash
# Entrar de forma interactiva al contenedor
docker exec -it convlstm_cpu_app bash
```

Una vez dentro, tu consola dirá algo como `root@f1b2c3d4:/app/backend#` o similar, indicando que estás dentro de la carpeta del proyecto.

---

## 2. Promover un Usuario a Administrador

Los usuarios administradores tienen permisos especiales en el dashboard, como por ejemplo la capacidad de enviar notificaciones push a todos los usuarios.

Si querés darle permisos de administrador a un usuario que ya se registró (ej: "fede"), usá el script `promote_admin.py` incluido en el backend:

```bash
# Asegurate de estar en la carpeta /app/backend dentro del contenedor
cd /app/backend

# Ejecutar el script indicando el nombre de usuario
python3 promote_admin.py fede
```

**Respuesta esperada:**
`Success: User 'fede' promoted to 'admin'.`

Si el usuario no existe, el script te avisará con un error.

---

## 3. Gestionar Usuarios Directamente en SQLite (SQL)

Si necesitás hacer consultas más avanzadas, ver la lista completa de usuarios registrados, o eliminar a alguien, podés abrir la base de datos directamente usando el comando `sqlite3`.

Estando dentro del contenedor:

```bash
# Entrar a la consola de SQLite conectada a la base de datos
sqlite3 /app/data/radar_history.db
```

El prompt cambiará a `sqlite>`. Ahora podés ejecutar comandos SQL estándar. No olvides poner punto y coma (`;`) al final de cada consulta.

### A. Ver formato de presentación
Para que las tablas se vean ordenadas te conviene correr estos dos comandos primero:
```sql
.mode column
.headers on
```

### B. Listar todos los usuarios
Para ver quiénes están registrados, sus emails y su rol:
```sql
SELECT id, username, email, role, created_at FROM users;
```

### C. Buscar un usuario específico
```sql
SELECT * FROM users WHERE username = 'juan123';
```

### D. Eliminar un usuario
Si necesitás borrar una cuenta específica:
```sql
-- Reemplazá 'juan123' por el nombre real
DELETE FROM users WHERE username = 'juan123';
```

*(Nota: Al estar usando SQLite, los cambios se aplican de inmediato en la escritura).*

### E. Quitar permisos de Administrador a un usuario
Si en vez de borrar al administrador querés degradarlo a usuario normal de forma manual:
```sql
UPDATE users SET role = 'user' WHERE username = 'fede';
```

### F. Salir de la base de datos
Para cerrar SQLite y volver a la terminal de Docker:
```sql
.quit
```

Finalmente, para salir del contenedor de Docker y volver a la terminal de tu computadora o servidor, escribí:
```bash
exit
```
