# Estrategia de Escalamiento y Calidad (Roadmap Futuro)

Este documento detalla una estrategia integral para elevar la calidad del proyecto mediante pruebas automáticas y planificar el escalamiento de la infraestructura ante un aumento significativo de usuarios.

---

## 1. Estrategia de Pruebas Automáticas (QA Strategy)

Aunque las pruebas unitarias son la base, para garantizar un producto robusto y visualmente impactante, se recomiendan las siguientes capas de testing:

### A. Pruebas de Integración (Integration Tests)
Verifican que los componentes del sistema (API + Base de Datos + Modelos) funcionen correctamente juntos.
*   **Backend (Pytest):** Crear scripts que levanten una base de datos de prueba (en memoria o contenedor temporal), inserten datos, llamen a los endpoints de la API (`/api/reports`, `/auth/login`) y verifiquen las respuestas JSON y los códigos de estado.
*   **Objetivo:** Asegurar que la lógica de negocio (login, registro, subida de reportes) no se rompa al refactorizar.

### B. Pruebas End-to-End (E2E)
Simulan el comportamiento de un usuario real navegando en la aplicación. Son críticas para flujos complejos.
*   **Herramienta recomendada:** **Playwright** o **Cypress**.
*   **Escenarios Clave:**
    1.  Usuario entra al Home -> Ve el Mapa -> Hace Login.
    2.  Usuario Autenticado -> Abre el diálogo de reporte -> Sube una foto -> Envía reporte -> Verifica que aparece en el mapa.
    3.  Admin -> Entra al panel -> Envía una Notificación Push.
*   **Ventaja:** Detectan errores que las pruebas unitarias no ven (ej: un botón que no es clicable porque un div lo tapa).

### C. Pruebas de Regresión Visual (Visual Regression Testing)
Dado que la estética ("Wow factor") es una prioridad, estas pruebas aseguran que los cambios en CSS/Componentes no rompan el diseño visual.
*   **Herramientas:** **Percy**, **Chromatic**, o los snapshots visuales de **Playwright**.
*   **Cómo funciona:** Toman capturas de pantalla de tus componentes en cada commit y las comparan píxel a píxel con la versión "aprobada". Si hay diferencias (ej: un margen cambió 2px), la prueba falla.

### D. Pruebas de Carga (Load Testing)
Simulan cientos o miles de usuarios concurrentes para identificar cuellos de botella.
*   **Herramientas:** **k6** o **Locust**.
*   **Escenario Crítico:** 500 usuarios solicitando simultáneamente las imágenes del radar (`/api/images`) durante una tormenta.
*   **Objetivo:** Determinar cuántos usuarios soporta tu servidor actual antes de caerse o volverse lento.

---

## 2. Estrategia de Escalamiento (Scaling Strategy)

Si la aplicación gana tracción, la arquitectura actual (Monolito Flask + SQLite + Worker en Vast.ai) necesitará evolucionar.

### Fase 1: Optimización del Monolito (Corto Plazo)
*   **Base de Datos:** Migrar de **SQLite** a **PostgreSQL**.
    *   *Por qué:* SQLite bloquea toda la base de datos cuando hay una escritura (ej: un reporte nuevo). Con muchos usuarios simultáneos, esto causará errores ("Database is locked"). PostgreSQL maneja concurrencia masiva nativamente.
*   **Caching (Redis):** Implementar **Redis**.
    *   *Uso:* Cachear las respuestas de `/api/images` y endpoints pesados. Si 1000 usuarios piden la misma imagen del radar, el backend la sirve desde la RAM (Redis) en milisegundos sin tocar el disco ni procesar nada.
    *   *Uso 2:* Gestionar sesiones de usuario de forma distribuida.

### Fase 2: Infraestructura Híbrida (Mediano Plazo)
Separar responsabilidades es clave para la estabilidad.
*   **Frontend:** **Seguir usando Vercel.**
    *   *Por qué:* Vercel escala automáticamente el frontend (Next.js) usando una red global (CDN). Es robusto, rápido y maneja picos de tráfico sin que tengas que configurar servidores.
*   **Backend API (Web Server):** Mover a un **VPS Estable** o servicio PaaS (DigitalOcean Droplet, AWS EC2, Render, Railway).
    *   *Por qué:* Los servidores de **Vast.ai** son "Spot Instances" (alquiler de GPU barato pero volátil). Pueden interrumpirse o tener IPs marcadas como spam. Necesitas un servidor **fijo y estable** (CPU-based) para manejar la API HTTP, usuarios y base de datos.
*   **Worker de IA (GPU):** Mantener en **Vast.ai** (o mover a GPU dedicada).
    *   *Arquitectura:* La API (en el servidor estable) recibe las imágenes MDV. Las sube a un Storage (S3/MinIO). Envía un mensaje a una **Cola (RabbitMQ/Redis)**. El Worker GPU (en Vast.ai) lee el mensaje, descarga, procesa con convLSTM, y sube el resultado.
    *   *Ventaja:* Si Vast.ai se cae, la web sigue funcionando (los usuarios pueden ver reportes, historial, chatear), solo se detienen las predicciones nuevas temporalmente.

### Fase 3: Microservicios y Balanceo (Largo Plazo / Masivo)
Solo si tienes un equipo de desarrollo y tráfico constante muy alto.
*   **Load Balancer (Traefik / Nginx):** Colocar un balanceador de carga frente a múltiples instancias de tu Backend API. Traefik es excelente por su integración dinámica con Docker.
*   **Microservicios:**
    *   `Auth Service`: Solo maneja usuarios y tokens.
    *   `Radar Service`: Maneja la ingesta y servido de imágenes.
    *   `Report Service`: Maneja la geolocalización y reportes ciudadanos.
    *   `Notification Service`: Maneja WebSockets/Push.
*   **Kubernetes (K8s):** Para orquestar todos estos contenedores automáticamente. (Generalmente "overkill" para proyectos iniciales, mejor empezar con Docker Compose o Swarm).

---

## Plan de Acción Recomendado (Resumen)

1.  **Inmediato:** Implementar **Tests E2E (Playwright)** para los flujos principales. Esto te dará seguridad al desplegar.
2.  **Si crece el uso:**
    *   Migrar DB a **PostgreSQL** (Managed en Supabase/Neon o Dockerizado).
    *   Deployar el Backend API en un servidor **VPS estable** (no GPU, costos bajos ~5-10 USD/mes).
    *   Conectar el Worker GPU (Vast.ai) a la API mediante una cola o API interna.
    *   Implementar **Redis** para caching.
3.  **Frontend:** Quedarse en **Vercel**. Es la mejor opción costo-beneficio y rendimiento para Next.js.
