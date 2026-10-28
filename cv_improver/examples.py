"""
cv_improver/examples.py

Plantillas de ejemplo fijas y estandarizadas por sector para CV Improver.
- Sin llamadas a IA (consumo de cuota: 0).
- Todos los datos son estrictamente genéricos y ficticios.
- Cada elemento está claramente marcado con '[Ejemplo]' para transparencia del usuario.
- Validadas contra ResumeSchema de Pydantic.
"""

from typing import Dict, Any, List
from .schema import (
    ResumeSchema,
    ContactInfo,
    ExperienceItem,
    BulletItem,
    EducationItem,
    SkillCategory,
    LanguageItem,
    CertificationItem,
)


def _b(text: str) -> BulletItem:
    """Helper conciso para crear BulletItem."""
    return BulletItem(original=text, improved=None, suggestion=None)


def _empty_contact() -> ContactInfo:
    """Retorna datos de contacto vacíos para que el usuario ingrese su información real."""
    return ContactInfo(
        name="",
        email=None,
        phone=None,
        location=None,
        linkedin=None,
        github=None,
        portfolio=None,
    )


# ------------------------------------------------------------------------------
# 1. TECNOLOGÍA E INFORMÁTICA
# ------------------------------------------------------------------------------
def get_tecnologia_example() -> ResumeSchema:
    return ResumeSchema(
        contact=_empty_contact(),
        summary=(
            "[Ejemplo] Ingeniero de Software Full-Stack con más de 6 años de experiencia en el diseño "
            "y escalabilidad de aplicaciones distribuidas basadas en microservicios con Python, Node.js y React. "
            "Especializado en arquitecturas en la nube (AWS/GCP), CI/CD automatizado y optimización de bases de datos de alto tráfico."
        ),
        experience=[
            ExperienceItem(
                company="[Ejemplo] CloudTech Solutions S.L.",
                position="[Ejemplo] Senior Full-Stack Engineer",
                start_date="2022-03",
                end_date="Presente",
                current=True,
                location="Remoto",
                bullets=[
                    _b("Lideró la migración de un monolito legado a una arquitectura de microservicios en AWS ECS/Docker, reduciendo los tiempos de respuesta del API en un 38%."),
                    _b("Diseñó pipelines automatizados de CI/CD con GitHub Actions y Terraform, disminuyendo la tasa de errores de despliegue a producción en un 45%."),
                    _b("Optimizó consultas PostgreSQL y esquemas de indexación en Redis, soportando picos de más de 120,000 usuarios concurrentes sin degradación de servicio."),
                    _b("Mentoreó a un equipo ágil de 5 desarrolladores juniors y mid-level mediante revisiones sistemáticas de código y buenas prácticas de Clean Architecture."),
                ],
            ),
            ExperienceItem(
                company="[Ejemplo] InnovaSoft Labs",
                position="[Ejemplo] Backend Developer",
                start_date="2019-01",
                end_date="2022-02",
                current=False,
                location="Madrid, España",
                bullets=[
                    _b("Desarrolló más de 15 endpoints RESTful y GraphQL con FastAPI y Django, procesando más de 2 millones de peticiones diarias."),
                    _b("Implementó pasarelas de pago seguras (Stripe y PayPal) cumpliendo estándares PCI-DSS con cero incidentes de seguridad."),
                    _b("Automatizó pruebas unitarias y de integración alcanzando un 88% de cobertura de código con pytest."),
                ],
            ),
        ],
        education=[
            EducationItem(
                institution="[Ejemplo] Universidad Politécnica de Madrid (Ficticia)",
                degree="[Ejemplo] Grado en Ingeniería Informática",
                field_of_study="Sistemas de Información y Software",
                start_date="2014-09",
                end_date="2018-06",
                grade_or_details="Mención de honor en Proyecto Final de Carrera",
            )
        ],
        skills=[
            SkillCategory(
                category="Lenguajes & Frameworks",
                skills=["Python", "FastAPI", "Django", "TypeScript", "React", "Node.js", "SQL"],
            ),
            SkillCategory(
                category="Cloud & DevOps",
                skills=["AWS (ECS, S3, RDS, Lambda)", "Docker", "Kubernetes", "Terraform", "GitHub Actions", "CI/CD"],
            ),
            SkillCategory(
                category="Bases de Datos & Caché",
                skills=["PostgreSQL", "MongoDB", "Redis", "Elasticsearch"],
            ),
            SkillCategory(
                category="Metodologías & Prácticas",
                skills=["Scrum", "TDD", "Clean Code", "Arquitectura de Microservicios", "REST & GraphQL"],
            ),
        ],
        languages=[
            LanguageItem(language="Español", proficiency="Nativo"),
            LanguageItem(language="Inglés", proficiency="C1 Profesional Avanzado"),
        ],
        certifications=[
            CertificationItem(
                name="[Ejemplo] AWS Certified Solutions Architect - Associate",
                issuer="Amazon Web Services",
                date="2023",
                credential_url="https://aws.amazon.com/verification/ejemplo",
            )
        ],
        raw_text="Plantilla de ejemplo: Tecnología e Informática",
    )


# ------------------------------------------------------------------------------
# 2. FINANZAS Y CONTABILIDAD
# ------------------------------------------------------------------------------
def get_finanzas_example() -> ResumeSchema:
    return ResumeSchema(
        contact=_empty_contact(),
        summary=(
            "[Ejemplo] Contadora Pública y Analista Financiera Senior con más de 7 años de experiencia "
            "en planificación financiera estratégica (FP&A), control presupuestario y auditoría corporativa. "
            "Historial comprobado en optimización de costos operativos, modelado de flujos de caja y cumplimiento estricto de normas IFRS/NIIF."
        ),
        experience=[
            ExperienceItem(
                company="[Ejemplo] Grupo Financiero Andino S.A.",
                position="[Ejemplo] Analista Financiera Senior (FP&A)",
                start_date="2021-05",
                end_date="Presente",
                current=True,
                location="Ciudad de México, México",
                bullets=[
                    _b("Gestionó el modelo presupuestario anual para operaciones de más de $18M USD, reduciendo variaciones de pronóstico al 2.5%."),
                    _b("Diseñó tableros ejecutivos en Power BI y SAP para seguimiento en tiempo real de márgenes de EBITDA y capital de trabajo."),
                    _b("Lideró un proyecto de renegociación de pasivos bancarios y condiciones comerciales que generó ahorros netos anuales de $420,000 USD."),
                    _b("Coordinó auditorías financieras internas y externas con firmas Big Four sin observaciones materiales durante 3 ejercicios consecutivos."),
                ],
            ),
            ExperienceItem(
                company="[Ejemplo] Consultores Fiscales Delta",
                position="[Ejemplo] Contadora de Auditoría & Impuestos",
                start_date="2018-01",
                end_date="2021-04",
                current=False,
                location="Ciudad de México, México",
                bullets=[
                    _b("Preparó estados financieros consolidados bajo normas NIIF y conciliaciones fiscales mensuales para más de 20 clientes corporativos."),
                    _b("Automatizó el proceso de conciliación bancaria mediante macros avanzadas en Excel, reduciendo el tiempo de cierre de 6 a 2 días hábiles."),
                    _b("Identificó deducciones fiscales no aprovechadas por clientes, recuperando saldos a favor superiores a $150,000 USD."),
                ],
            ),
        ],
        education=[
            EducationItem(
                institution="[Ejemplo] Universidad Nacional de Comercio (Ficticia)",
                degree="[Ejemplo] Licenciatura en Contaduría Pública y Finanzas",
                field_of_study="Finanzas Corporativas y Fiscalidad",
                start_date="2013-08",
                end_date="2017-12",
            )
        ],
        skills=[
            SkillCategory(
                category="Modelado & Análisis Financiero",
                skills=["Modelado Financiero", "Presupuestos y FP&A", "Flujo de Caja", "Análisis de Rentabilidad", "EBITDA"],
            ),
            SkillCategory(
                category="Sistemas & Herramientas",
                skills=["SAP ERP (FI/CO)", "Power BI", "Excel Avanzado (VBA/Power Query)", "Oracle NetSuite", "Tableau"],
            ),
            SkillCategory(
                category="Normativa & Contabilidad",
                skills=["Normas IFRS/NIIF", "Consolidación de Estados Financieros", "Auditoría Interna", "Cumplimiento Fiscal"],
            ),
        ],
        languages=[
            LanguageItem(language="Español", proficiency="Nativo"),
            LanguageItem(language="Inglés", proficiency="B2 Profesional Intermedio-Avanzado"),
        ],
        certifications=[
            CertificationItem(
                name="[Ejemplo] Certified Financial Modeling & Valuation Analyst (FMVA)",
                issuer="Corporate Finance Institute",
                date="2022",
            )
        ],
        raw_text="Plantilla de ejemplo: Finanzas y Contabilidad",
    )


# ------------------------------------------------------------------------------
# 3. VENTAS B2B Y CUENTAS CLAVE
# ------------------------------------------------------------------------------
def get_ventas_b2b_example() -> ResumeSchema:
    return ResumeSchema(
        contact=_empty_contact(),
        summary=(
            "[Ejemplo] Key Account Manager (KAM) y Ejecutivo Comercial B2B con más de 8 años de trayectoria "
            "en el sector SaaS y tecnología empresarial. Especialista en prospección consultiva, negociación de contratos de alto valor "
            "y retención de cuentas clave a nivel regional (LATAM)."
        ),
        experience=[
            ExperienceItem(
                company="[Ejemplo] NexoEnterprise SaaS",
                position="[Ejemplo] Senior Key Account Manager B2B",
                start_date="2021-08",
                end_date="Presente",
                current=True,
                location="Bogotá, Colombia",
                bullets=[
                    _b("Superó la cuota de ingresos anuales en un 134% consecutivamente durante 2022 y 2023, generando más de $1.4M USD en nuevo ARR."),
                    _b("Cerró acuerdos comerciales multianuales con 14 empresas del Top 500 regional con un ciclo de venta promedio de 4 meses."),
                    _b("Elevó la tasa de retención neta (NDR) de cartera de clientes corporativos del 92% al 109% mediante estrategias de upselling y cross-selling."),
                    _b("Lideró la implementación de metodologías de venta consultiva (MEDDIC y Challenger Sale) para un equipo de 6 ejecutivos de cuenta."),
                ],
            ),
            ExperienceItem(
                company="[Ejemplo] ConectaB2B Software",
                position="[Ejemplo] Account Executive Mid-Market",
                start_date="2018-03",
                end_date="2021-07",
                current=False,
                location="Bogotá, Colombia",
                bullets=[
                    _b("Gestionó un pipeline comercial activo de más de $800,000 USD mensuales manteniendo una tasa de conversión de demo a cierre del 28%."),
                    _b("Prospectó y aperturó más de 45 cuentas nuevas en los sectores de banca, seguros y telecomunicaciones."),
                    _b("Diseñó propuestas de valor económico (ROI Business Cases) personalizadas para comités ejecutivos C-Level."),
                ],
            ),
        ],
        education=[
            EducationItem(
                institution="[Ejemplo] Universidad de los Andes (Ficticia)",
                degree="[Ejemplo] Profesional en Administración de Empresas y Negocios",
                start_date="2013-01",
                end_date="2017-11",
            )
        ],
        skills=[
            SkillCategory(
                category="Estrategia Comercial B2B",
                skills=["Venta Consultiva (MEDDIC)", "Negociación C-Level", "Gestión de Pipeline", "Account Management", "Cierre Comercial"],
            ),
            SkillCategory(
                category="Herramientas CRM & Sales Ops",
                skills=["Salesforce CRM", "HubSpot Sales Pro", "LinkedIn Sales Navigator", "Gong", "Outreach"],
            ),
            SkillCategory(
                category="Métricas & Negocio",
                skills=["ARR / MRR", "Net Dollar Retention (NDR)", "Customer Lifetime Value (LTV)", "CAC Payback"],
            ),
        ],
        languages=[
            LanguageItem(language="Español", proficiency="Nativo"),
            LanguageItem(language="Inglés", proficiency="C1 Avanzado de Negocios"),
        ],
        certifications=[
            CertificationItem(
                name="[Ejemplo] Inbound Sales & Enterprise Deal Closing Certification",
                issuer="HubSpot Academy",
                date="2023",
            )
        ],
        raw_text="Plantilla de ejemplo: Ventas B2B y Cuentas Clave",
    )


# ------------------------------------------------------------------------------
# 4. MARKETING Y PRODUCTO
# ------------------------------------------------------------------------------
def get_marketing_producto_example() -> ResumeSchema:
    return ResumeSchema(
        contact=_empty_contact(),
        summary=(
            "[Ejemplo] Product Marketing Manager (PMM) y Growth Strategist con más de 5 años impulsando estrategias "
            "de Go-to-Market (GTM), posicionamiento de marca y adquisición digital orientada a datos (Product-Led Growth). "
            "Experta en experimentación A/B, análisis de cohortes y retención de usuarios."
        ),
        experience=[
            ExperienceItem(
                company="[Ejemplo] AppScale Technologies",
                position="[Ejemplo] Product Marketing Manager",
                start_date="2022-01",
                end_date="Presente",
                current=True,
                location="Barcelona, España (Híbrido)",
                bullets=[
                    _b("Diseñó y ejecutó el lanzamiento de 3 nuevos módulos de producto, alcanzando más de 85,000 usuarios activos en los primeros 60 días."),
                    _b("Redujo el Costo de Adquisición de Clientes (CAC) en un 27% reenfocando la estrategia hacia canales de inbound marketing y contenido técnico SEO."),
                    _b("Implementó un marco de experimentación continua con Mixpanel y Optimizely, elevando la tasa de activación de onboarding del 18% al 32%."),
                    _b("Condujo más de 40 entrevistas cualitativas con clientes para redefinir el Buyer Persona y la matriz de mensajes competitivos."),
                ],
            ),
            ExperienceItem(
                company="[Ejemplo] Digital Pulse Agency",
                position="[Ejemplo] Growth Marketing Specialist",
                start_date="2019-06",
                end_date="2021-12",
                current=False,
                location="Valencia, España",
                bullets=[
                    _b("Gestionó presupuestos de pauta digital mensual superiores a 60,000 € en Google Ads, Meta Ads y LinkedIn Ads con un ROAS promedio de 3.8x."),
                    _b("Optimizó funnels de conversión mediante landing pages dinámicas, incrementando la captura de MQLs cualificados en un 42%."),
                    _b("Creó secuencias automatizadas de email nurturing en ActiveCampaign con tasas de apertura del 39% y CTR del 8.2%."),
                ],
            ),
        ],
        education=[
            EducationItem(
                institution="[Ejemplo] Universidad Pompeu Fabra (Ficticia)",
                degree="[Ejemplo] Grado en Publicidad, Relaciones Públicas y Marketing Digital",
                start_date="2015-09",
                end_date="2019-06",
            )
        ],
        skills=[
            SkillCategory(
                category="Estrategia de Producto & GTM",
                skills=["Go-to-Market (GTM)", "Posicionamiento & Mensajería", "Product-Led Growth (PLG)", "Investigación de Usuarios", "Análisis Competitivo"],
            ),
            SkillCategory(
                category="Analítica & Experimentación",
                skills=["Google Analytics 4 (GA4)", "Mixpanel", "Amplitude", "Hotjar", "Optimizely (A/B Testing)"],
            ),
            SkillCategory(
                category="Canales de Crecimiento & Adquisición",
                skills=["SEO Técnico & Contenidos", "Google Ads", "LinkedIn Ads", "Email Automation", "Copywriting Persuasivo"],
            ),
        ],
        languages=[
            LanguageItem(language="Español", proficiency="Nativo"),
            LanguageItem(language="Inglés", proficiency="C1 Profesional"),
        ],
        certifications=[
            CertificationItem(
                name="[Ejemplo] Product Marketing Certified (PMMC)",
                issuer="Product Marketing Alliance",
                date="2023",
            )
        ],
        raw_text="Plantilla de ejemplo: Marketing y Producto",
    )


# ------------------------------------------------------------------------------
# 5. OPERACIONES Y LOGÍSTICA
# ------------------------------------------------------------------------------
def get_operaciones_logistica_example() -> ResumeSchema:
    return ResumeSchema(
        contact=_empty_contact(),
        summary=(
            "[Ejemplo] Responsable de Operaciones y Cadena de Suministro (Supply Chain Lead) con más de 7 años de experiencia "
            "en logística omnicanal, gestión de centros de distribución (CDs), compras estratégicas y mejora continua (Lean/Six Sigma). "
            "Enfocado en la reducción de mermas, optimización de tiempos de entrega de última milla y control de inventarios."
        ),
        experience=[
            ExperienceItem(
                company="[Ejemplo] LogiSur Distribución & Fulfillment",
                position="[Ejemplo] Jefe de Operaciones & Logística",
                start_date="2021-02",
                end_date="Presente",
                current=True,
                location="Buenos Aires, Argentina",
                bullets=[
                    _b("Supervisó las operaciones diarias de un Centro de Distribución de 15,000 m² con un equipo de 65 operarios y despachos de 8,000 pedidos/día."),
                    _b("Disminuyó los tiempos de ciclo de preparación de pedidos (picking & packing) en un 22% implementando zonificación por rotación ABC."),
                    _b("Mejoró el indicador de entregas a tiempo y completas (OTIF) del 89% al 97.4% a través de alianzas con operadores de última milla."),
                    _b("Redujo la rotura de stock y obsolescencia de inventarios en $180,000 USD anuales mediante integración de software WMS con ERP."),
                ],
            ),
            ExperienceItem(
                company="[Ejemplo] Consumo Masivo del Plata S.A.",
                position="[Ejemplo] Coordinador de Abastecimiento & Compras",
                start_date="2017-10",
                end_date="2021-01",
                current=False,
                location="Buenos Aires, Argentina",
                bullets=[
                    _b("Negoció contratos marco con proveedores locales e internacionales de insumos críticos con un ahorro del 12% sobre el presupuesto."),
                    _b("Implementó metodologías 5S y Kaizen en líneas de empaque logrando certificar el centro bajo normas de calidad ISO 9001."),
                    _b("Desarrolló modelos de pronóstico de demanda estacional reduciendo excesos de inventario en un 18%."),
                ],
            ),
        ],
        education=[
            EducationItem(
                institution="[Ejemplo] Universidad Tecnológica Nacional (Ficticia)",
                degree="[Ejemplo] Ingeniería Industrial",
                field_of_study="Logística, Producción y Operaciones",
                start_date="2012-03",
                end_date="2017-07",
            )
        ],
        skills=[
            SkillCategory(
                category="Gestión Operativa & Supply Chain",
                skills=["Gestión de Centros de Distribución (CD)", "Última Milla & Transporte", "Control de Inventarios (ABC)", "Compras Estratégicas", "Planificación S&OP"],
            ),
            SkillCategory(
                category="Metodologías de Mejora Continua",
                skills=["Lean Manufacturing", "Six Sigma (Green Belt)", "Metodología 5S", "Kaizen", "Gestión de Calidad ISO 9001"],
            ),
            SkillCategory(
                category="Sistemas Logísticos & Software",
                skills=["SAP WMS / EWM", "Manhattan Associates", "Excel Avanzado (Solver)", "Power BI Operativo"],
            ),
        ],
        languages=[
            LanguageItem(language="Español", proficiency="Nativo"),
            LanguageItem(language="Inglés", proficiency="B2 Profesional Intermedio"),
        ],
        certifications=[
            CertificationItem(
                name="[Ejemplo] Lean Six Sigma Green Belt Certified",
                issuer="Quality Management Institute",
                date="2022",
            )
        ],
        raw_text="Plantilla de ejemplo: Operaciones y Logística",
    )


# ------------------------------------------------------------------------------
# 6. RECURSOS HUMANOS Y GESTIÓN DE TALENTO
# ------------------------------------------------------------------------------
def get_recursos_humanos_example() -> ResumeSchema:
    return ResumeSchema(
        contact=_empty_contact(),
        summary=(
            "[Ejemplo] Especialista en Recursos Humanos y Adquisición de Talento (Talent Acquisition Specialist / HRBP) "
            "con más de 6 años de experiencia en atracción de perfiles tecnológicos y corporativos en entornos de rápido crecimiento. "
            "Experta en diseño de planes de onboarding, evaluación por competencias, clima laboral y retención de talento clave."
        ),
        experience=[
            ExperienceItem(
                company="[Ejemplo] TechTalent Global Corp",
                position="[Ejemplo] Senior Talent Acquisition Specialist",
                start_date="2021-09",
                end_date="Presente",
                current=True,
                location="Sevilla, España (Remoto)",
                bullets=[
                    _b("Gestionó el ciclo completo de selección (end-to-end) para más de 70 contrataciones técnicas y ejecutivas anuales en España y LATAM."),
                    _b("Redujo el tiempo promedio de contratación (Time-to-Hire) de 48 a 29 días optimizando las fases de filtrado y screening con ATS."),
                    _b("Diseñó un programa de Employer Branding en LinkedIn que aumentó las postulaciones orgánicas cualificadas en un 55%."),
                    _b("Lideró métricas de diversidad e inclusión (D&I) asegurando paneles de candidatos con paridad de género en posiciones de liderazgo."),
                ],
            ),
            ExperienceItem(
                company="[Ejemplo] Consultora People First",
                position="[Ejemplo] Generalista de Recursos Humanos",
                start_date="2018-04",
                end_date="2021-08",
                current=False,
                location="Sevilla, España",
                bullets=[
                    _b("Rediseñó el proceso de inducción y bienvenida (Onboarding), alcanzando un índice de satisfacción del nuevo empleado del 96% en los primeros 90 días."),
                    _b("Coordinó evaluaciones semestrales de desempeño y clima laboral (eNPS) para una plantilla de 250 colaboradores."),
                    _b("Gestionó incidencias laborales, nóminas, planes de capacitación continua y cumplimiento de normativas de prevención de riesgos laborales."),
                ],
            ),
        ],
        education=[
            EducationItem(
                institution="[Ejemplo] Universidad de Sevilla (Ficticia)",
                degree="[Ejemplo] Grado en Psicología",
                field_of_study="Psicología de las Organizaciones y del Trabajo",
                start_date="2013-09",
                end_date="2017-06",
            )
        ],
        skills=[
            SkillCategory(
                category="Atracción & Selección de Talento",
                skills=["Selección End-to-End", "Entrevistas por Competencias (STAR)", "Headhunting & Sourcing Activo", "Employer Branding", "Evaluaciones Técnicas"],
            ),
            SkillCategory(
                category="Sistemas ATS & HR Tech",
                skills=["Greenhouse ATS", "Lever", "Workday", "LinkedIn Recruiter Corporate", "BambooHR"],
            ),
            SkillCategory(
                category="Cultura & Gestión de Personas",
                skills=["Onboarding Estratégico", "Evaluaciones de Desempeño (OKRs)", "eNPS & Clima Laboral", "Planes de Retención & Carrera"],
            ),
        ],
        languages=[
            LanguageItem(language="Español", proficiency="Nativo"),
            LanguageItem(language="Inglés", proficiency="C1 Profesional Avanzado"),
        ],
        certifications=[
            CertificationItem(
                name="[Ejemplo] Strategic Human Resources Leadership Certificate",
                issuer="HR Certification Institute (HRCI)",
                date="2022",
            )
        ],
        raw_text="Plantilla de ejemplo: Recursos Humanos y Gestión de Talento",
    )


# ------------------------------------------------------------------------------
# CATÁLOGO DE EJEMPLOS SECTORIALES
# ------------------------------------------------------------------------------
SECTOR_EXAMPLES: Dict[str, Dict[str, Any]] = {
    "tecnologia": {
        "title": "Tecnología e Informática",
        "role": "Ingeniero de Software Full-Stack / Cloud",
        "icon": "💻",
        "description": "Ideal para desarrolladores, DevOps, arquitectos cloud y perfiles de infraestructura con foco en impacto técnico y escalabilidad.",
        "schema_factory": get_tecnologia_example,
    },
    "finanzas": {
        "title": "Finanzas y Contabilidad",
        "role": "Analista Financiera Senior / Contadora",
        "icon": "📊",
        "description": "Enfocado en planificación financiera (FP&A), control de costes, auditoría, normativas NIIF/IFRS y reportes ejecutivos.",
        "schema_factory": get_finanzas_example,
    },
    "ventas_b2b": {
        "title": "Ventas B2B y Cuentas Clave",
        "role": "Key Account Manager (KAM) / Ejecutivo B2B",
        "icon": "🤝",
        "description": "Especial para profesionales de desarrollo de negocio, gestión de grandes cuentas corporativas, ventas SaaS y negociación C-Level.",
        "schema_factory": get_ventas_b2b_example,
    },
    "marketing_producto": {
        "title": "Marketing y Producto",
        "role": "Product Marketing Manager / Growth Lead",
        "icon": "🚀",
        "description": "Diseñado para especialistas en Go-to-Market (GTM), Product-Led Growth, analítica digital, funnels de conversión y SEO/PPC.",
        "schema_factory": get_marketing_producto_example,
    },
    "operaciones_logistica": {
        "title": "Operaciones y Logística",
        "role": "Jefe de Operaciones / Supply Chain Lead",
        "icon": "📦",
        "description": "Estructurado para líderes de cadena de suministro, centros de distribución, última milla, compras y metodologías Lean/Six Sigma.",
        "schema_factory": get_operaciones_logistica_example,
    },
    "recursos_humanos": {
        "title": "Recursos Humanos y Gestión de Talento",
        "role": "Talent Acquisition Specialist / HRBP",
        "icon": "👥",
        "description": "Perfecto para reclutadores, generalistas de RRHH y business partners enfocados en retención, cultura y selección por competencias.",
        "schema_factory": get_recursos_humanos_example,
    },
}


def load_example_schema(example_key: str) -> ResumeSchema:
    """
    Instancia y retorna una copia limpia del ResumeSchema para el sector solicitado.
    """
    if example_key not in SECTOR_EXAMPLES:
        raise ValueError(f"Sector de ejemplo '{example_key}' no reconocido. Opciones: {list(SECTOR_EXAMPLES.keys())}")
    factory = SECTOR_EXAMPLES[example_key]["schema_factory"]
    return factory()
