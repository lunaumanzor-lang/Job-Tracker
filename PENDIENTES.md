# 📋 Tareas Pendientes Antes del Despliegue en Producción

Lista de verificación y configuraciones requeridas antes de lanzar la aplicación **AI Job Application Tracker** a producción:

---

## 🔐 1. Configuración de Correo y Autenticación (Supabase)
- [ ] **Configurar SMTP propio en Supabase:**
  - **Ruta:** *Supabase Dashboard* ➔ *Authentication* ➔ *Emails* ➔ *SMTP Settings*.
  - **Servicios recomendados:** Resend, Brevo, SendGrid o Amazon SES.
  - **Requisitos:** Configurar un dominio propio con registros DNS **SPF**, **DKIM** y **DMARC**.
  - **Motivo:** Sin esto, los correos de confirmación usan el servidor compartido de Supabase, que tiene límites estrictos (rate limits bajos) y alta probabilidad de caer en la carpeta de spam o correo no deseado. Hacerlo antes del despliegue.

- [ ] **Actualizar Site URL y Redirect URLs para Producción:**
  - **Ruta:** *Supabase Dashboard* ➔ *Authentication* ➔ *URL Configuration*.
  - Configurar **Site URL** con la URL pública de producción (ej. `https://tu-app.streamlit.app`).
  - Añadir en **Redirect URLs** la URL pública permitida (`https://tu-app.streamlit.app/**`) además de las locales para desarrollo.

---

## ☁️ 2. Despliegue e Infraestructura (Streamlit Community Cloud)
- [ ] **Configurar Secrets en la Nube:**
  - Configurar en el panel de Streamlit Cloud (*Settings* ➔ *Secrets*) los mismos valores de `.streamlit/secrets.toml`:
    - `SUPABASE_URL`
    - `SUPABASE_KEY`
    - `SUPABASE_SERVICE_ROLE_KEY`
    - `SESSION_ENCRYPTION_KEY`
    - `GEMINI_API_KEY`
- [ ] **Verificar `requirements.txt`:**
  - Confirmar que todas las dependencias instaladas en local estén reflejadas para que el build en la nube sea limpio y sin fallos.

---

## 🧪 3. Pruebas Finales de Aceptación (QA)
- [ ] **Flujo de Registro y Confirmación:**
  - Registro de cuenta nueva ➔ Recepción de correo ➔ Confirmación por enlace ➔ Redirección limpia a la app.
- [ ] **Persistencia y Auto-login:**
  - Iniciar sesión ➔ Navegar por pestañas ➔ Recargar página con F5 ➔ Confirmar que la sesión se mantiene activa sin interrupciones.
- [ ] **Cierre de sesión:**
  - Hacer clic en "Cerrar Sesión" ➔ Confirmar revocación del token y limpieza de la URL.
