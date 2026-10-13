# 📋 Tareas Pendientes Antes de Lanzar a Producción

Lista de tareas prioritarias y requerimientos técnicos antes del lanzamiento público de la aplicación:

---

## 1. 📧 Configurar SMTP propio en Supabase
- [ ] Configurar un proveedor de correo transaccional en **Supabase** (*Authentication* ➔ *Emails* ➔ *SMTP Settings*).
- [ ] **Servicios recomendados:** Resend, Brevo o Amazon SES.
- [ ] Configurar dominio propio y validar registros DNS esenciales (**SPF**, **DKIM** y **DMARC**).
- [ ] *Motivo:* Sin un servidor SMTP propio, los correos de confirmación y reseteo de contraseña dependen del límite bajo compartido de Supabase y corren alto riesgo de caer en spam.

---

## 2. 🏷️ Nombre de la App y Dominio Propio
- [ ] Definir el nombre comercial final de la aplicación y branding.
- [ ] Comprar el dominio web correspondiente (ej. en Cloudflare, Namecheap o Google Domains/Squarespace).
- [ ] Configurar los registros DNS y enlazar el dominio personalizado con la plataforma de hosting.

---

## 3. 🖥️ Frontend y Renderizado: Reemplazar `st.components.v1.html` por `st.iframe`
- [ ] Evaluar y migrar las llamadas a `st.components.v1.html` hacia `st.iframe` (o la solución de iframe nativa recomendada por Streamlit) para mejorar el aislamiento del DOM, estabilidad y compatibilidad con vistas previas responsivas en producción.

---

## 4. ⚖️ Fase 1: Operaciones, Cumplimiento Legal y Monitoreo
- [ ] **Facturación y límites de Gemini (Google Cloud / Google AI Studio):**
  - Configurar límites de cuotas, alertas de presupuesto y método de facturación formal para evitar bloqueos por rate limiting o costos imprevistos.
- [ ] **Privacidad y Consentimiento Legal:**
  - Redactar Términos y Condiciones y Política de Privacidad con asesoría de un abogado (tratamiento de datos laborales, currículums, cookies y consentimiento explícito GDPR / legislación local).
- [ ] **Monitoreo de Errores con Sentry:**
  - Integrar SDK de Sentry en Streamlit para capturar excepciones en tiempo real de los usuarios en producción.
- [ ] **Logs y Pruebas Automatizadas:**
  - Robustecer el logging estructurado y ejecutar la suite de pruebas unitarias/integración antes de liberar cada versión.

---

## 5. 🗄️ Separación de Entornos en Supabase (Staging vs. Producción)
- [ ] Crear un proyecto independiente en Supabase para **Pruebas / Staging**, completamente aislado del proyecto de **Producción**.
- [ ] Mantener las migraciones de esquemas y políticas RLS sincronizadas entre ambos proyectos para validar cambios sin poner en riesgo datos reales.

---

## 6. 🔐 Gestión Segura de Secretos en el Hosting
- [ ] Al desplegar en la plataforma de producción (ej. Streamlit Community Cloud u otro proveedor), configurar todas las variables sensibles en la sección de **Secrets / Environment Variables** del panel del hosting:
  - `SUPABASE_URL`
  - `SUPABASE_KEY`
  - `SUPABASE_SERVICE_ROLE_KEY`
  - `SESSION_ENCRYPTION_KEY`
  - `GEMINI_API_KEY`
- [ ] Verificar que ningún archivo local `.streamlit/secrets.toml` o `.env` se incluya en el control de versiones (mantener en `.gitignore`).
