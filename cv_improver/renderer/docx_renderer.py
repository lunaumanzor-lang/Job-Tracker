"""
Renderizador y exportador de CV a documento Word (.docx) utilizando python-docx.
Mantiene la estructura profesional y jerarquía de estilos para ATS.
"""

import io
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from ..schema import ResumeSchema


def render_cv_to_docx(
    resume: ResumeSchema,
    accent_hex: str = "#1E3A8A",
    language: str = "es"
) -> bytes:
    """
    Construye un documento DOCX estilizado a partir de ResumeSchema con soporte para inglés o español.
    Retorna los bytes del archivo en memoria.
    """
    doc = Document()
    is_en = (language == "en")

    # Configuración de márgenes estándar (0.75 pulgadas)
    for section in doc.sections:
        section.top_margin = Inches(0.6)
        section.bottom_margin = Inches(0.6)
        section.left_margin = Inches(0.7)
        section.right_margin = Inches(0.7)

    # Convertir color de acento hexadecimal a RGB
    clean_hex = accent_hex.lstrip("#")
    if len(clean_hex) == 6:
        r = int(clean_hex[0:2], 16)
        g = int(clean_hex[2:4], 16)
        b = int(clean_hex[4:6], 16)
    else:
        r, g, b = 30, 58, 138  # Azul marino por defecto

    accent_rgb = RGBColor(r, g, b)

    # 1. ENCABEZADO Y NOMBRE
    p_name = doc.add_paragraph()
    p_name.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_name = p_name.add_run(resume.contact.name)
    run_name.font.size = Pt(20)
    run_name.font.bold = True
    run_name.font.color.rgb = accent_rgb

    # 2. CONTACTO
    contact_parts = []
    if resume.contact.email:
        contact_parts.append(resume.contact.email)
    if resume.contact.phone:
        contact_parts.append(resume.contact.phone)
    if resume.contact.location:
        contact_parts.append(resume.contact.location)
    if resume.contact.linkedin:
        contact_parts.append(resume.contact.linkedin)
    if resume.contact.github:
        contact_parts.append(resume.contact.github)

    if contact_parts:
        p_contact = doc.add_paragraph(" | ".join(contact_parts))
        p_contact.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_contact.paragraph_format.space_after = Pt(12)
        for r_item in p_contact.runs:
            r_item.font.size = Pt(9.5)
            r_item.font.color.rgb = RGBColor(100, 116, 139)

    # Función auxiliar para encabezados de sección
    def add_section_header(title: str):
        p_sec = doc.add_paragraph()
        p_sec.paragraph_format.space_before = Pt(10)
        p_sec.paragraph_format.space_after = Pt(4)
        run_sec = p_sec.add_run(title.upper())
        run_sec.font.size = Pt(11)
        run_sec.font.bold = True
        run_sec.font.color.rgb = accent_rgb

    # 3. RESUMEN PROFESIONAL
    final_summary = resume.summary_improved or resume.summary
    if final_summary:
        add_section_header("Professional Summary" if is_en else "Perfil Profesional")
        p_sum = doc.add_paragraph(final_summary)
        p_sum.paragraph_format.space_after = Pt(8)
        p_sum.paragraph_format.line_spacing = 1.15
        for r_sum in p_sum.runs:
            r_sum.font.size = Pt(10)

    # 4. EXPERIENCIA LABORAL
    if resume.experience:
        add_section_header("Work Experience" if is_en else "Experiencia Laboral")
        for exp in resume.experience:
            p_exp = doc.add_paragraph()
            p_exp.paragraph_format.space_before = Pt(4)
            p_exp.paragraph_format.space_after = Pt(2)
            
            run_pos = p_exp.add_run(exp.position)
            run_pos.font.bold = True
            run_pos.font.size = Pt(10)
            
            p_exp.add_run(f" — {exp.company} ")
            
            dates_part = ""
            if exp.start_date or exp.end_date or exp.current:
                present_label = 'Present' if is_en else 'Presente'
                end_lbl = present_label if exp.current else (exp.end_date or '')
                if exp.start_date and end_lbl:
                    dates_part = f"({exp.start_date} – {end_lbl})"
                elif exp.start_date:
                    dates_part = f"({exp.start_date})"
                elif end_lbl:
                    dates_part = f"({end_lbl})"

            if dates_part:
                run_date = p_exp.add_run(f" {dates_part}")
                run_date.font.italic = True
                run_date.font.size = Pt(9)
                run_date.font.color.rgb = RGBColor(100, 116, 139)

            for b in exp.bullets:
                text_bullet = b.improved or b.original
                p_bullet = doc.add_paragraph(text_bullet, style="List Bullet")
                p_bullet.paragraph_format.space_after = Pt(2)
                p_bullet.paragraph_format.line_spacing = 1.15
                for r_b in p_bullet.runs:
                    r_b.font.size = Pt(9.5)

    # 5. EDUCACIÓN
    if resume.education:
        add_section_header("Education" if is_en else "Educación")
        for edu in resume.education:
            p_edu = doc.add_paragraph()
            p_edu.paragraph_format.space_before = Pt(3)
            p_edu.paragraph_format.space_after = Pt(2)

            run_deg = p_edu.add_run(edu.degree)
            run_deg.font.bold = True
            run_deg.font.size = Pt(10)

            if edu.field_of_study:
                prep = " in " if is_en else " en "
                p_edu.add_run(f"{prep}{edu.field_of_study}")
            p_edu.add_run(f" — {edu.institution} ")

            edu_dates_part = ""
            if edu.start_date and edu.end_date:
                edu_dates_part = f"({edu.start_date} – {edu.end_date})"
            elif edu.start_date or edu.end_date:
                edu_dates_part = f"({edu.start_date or edu.end_date})"

            if edu_dates_part:
                run_date = p_edu.add_run(edu_dates_part)
                run_date.font.italic = True
                run_date.font.size = Pt(9)
                run_date.font.color.rgb = RGBColor(100, 116, 139)

    # 6. HABILIDADES
    if resume.skills:
        add_section_header("Skills & Competencies" if is_en else "Habilidades")
        for sc in resume.skills:
            p_sk = doc.add_paragraph()
            p_sk.paragraph_format.space_after = Pt(2)
            run_cat = p_sk.add_run(f"{sc.category}: ")
            run_cat.font.bold = True
            run_cat.font.size = Pt(9.5)
            run_cat.font.color.rgb = accent_rgb
            run_items = p_sk.add_run(", ".join(sc.skills))
            run_items.font.size = Pt(9.5)

    # 7. CERTIFICACIONES E IDIOMAS
    if resume.certifications or resume.languages:
        add_section_header("Certifications & Languages" if is_en else "Certificaciones e Idiomas")
        for cert in resume.certifications:
            p_c = doc.add_paragraph(style="List Bullet")
            p_c.paragraph_format.space_after = Pt(2)
            default_cert = 'Certificate' if is_en else 'Certificado'
            r_c = p_c.add_run(f"{cert.name} ({cert.issuer or default_cert})")
            r_c.font.size = Pt(9.5)

        for lang in resume.languages:
            p_l = doc.add_paragraph(style="List Bullet")
            p_l.paragraph_format.space_after = Pt(2)
            r_l = p_l.add_run(f"{lang.language}: {lang.proficiency or ('Fluent' if is_en else 'Fluido')}")
            r_l.font.size = Pt(9.5)

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
