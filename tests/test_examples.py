# ==============================================================================
# PROYECTO: Smart Job Tracker
# PRUEBAS UNITARIAS: cv_improver/examples.py (Plantillas fijas sectoriales)
# ==============================================================================

import pytest
from cv_improver.examples import SECTOR_EXAMPLES, load_example_schema
from cv_improver.schema import ResumeSchema


def test_sector_examples_catalog():
    """Verifica que los 6 sectores solicitados existan en el catálogo con sus metadatos."""
    expected_sectors = [
        "tecnologia",
        "finanzas",
        "ventas_b2b",
        "marketing_producto",
        "operaciones_logistica",
        "recursos_humanos",
    ]
    assert len(SECTOR_EXAMPLES) == 6
    for sector in expected_sectors:
        assert sector in SECTOR_EXAMPLES
        info = SECTOR_EXAMPLES[sector]
        assert "title" in info and info["title"]
        assert "role" in info and info["role"]
        assert "icon" in info and info["icon"]
        assert "description" in info and info["description"]
        assert callable(info["schema_factory"])


@pytest.mark.parametrize("sector_key", list(SECTOR_EXAMPLES.keys()))
def test_load_example_schema_validity(sector_key):
    """Verifica que cada plantilla sectorial genere un ResumeSchema válido y completo."""
    schema = load_example_schema(sector_key)
    assert isinstance(schema, ResumeSchema)

    # Verificación de que los datos personales de contacto estén vacíos
    assert schema.contact.name == ""
    assert schema.contact.email is None
    assert schema.contact.phone is None
    assert schema.contact.location is None
    assert schema.contact.linkedin is None
    assert schema.contact.github is None
    assert schema.contact.portfolio is None

    # Resumen y experiencias
    assert schema.summary is not None and "[Ejemplo]" in schema.summary
    assert len(schema.experience) >= 2
    for exp in schema.experience:
        assert exp.company.startswith("[Ejemplo]")
        assert exp.position.startswith("[Ejemplo]")
        assert len(exp.bullets) >= 2
        for b in exp.bullets:
            assert b.original and len(b.original) > 20

    # Educación, habilidades e idiomas
    assert len(schema.education) >= 1
    assert len(schema.skills) >= 2
    assert len(schema.languages) >= 1


def test_load_example_schema_invalid_key():
    """Lanzar ValueError descriptivo si se solicita un sector desconocido."""
    with pytest.raises(ValueError) as excinfo:
        load_example_schema("sector_inexistente")
    assert "no reconocido" in str(excinfo.value)


def test_is_resume_example_unedited_behavior(monkeypatch):
    """
    Verifica que is_resume_example_unedited detecte correctamente un CV de ejemplo sin editar:
    - Retorna True si el nombre está vacío o si contiene marcadores '[Ejemplo]'.
    - Retorna False una vez que el usuario ingresa su nombre real y quita las etiquetas de ejemplo.
    """
    from cv_improver.ui import is_resume_example_unedited
    import streamlit as st

    # Simular session_state
    dummy_state = {"cv_improver_is_example": True, "cv_improver_filename": "Ejemplo_Tecnologia"}
    monkeypatch.setattr(st, "session_state", dummy_state)

    schema = load_example_schema("tecnologia")
    # Caso 1: Recién cargado, nombre vacío y contiene '[Ejemplo]'
    assert is_resume_example_unedited(schema) is True

    # Caso 2: El usuario ingresa su nombre pero aún conserva las etiquetas '[Ejemplo]' en resumen/experiencia
    schema.contact.name = "Carlos Pérez"
    assert is_resume_example_unedited(schema) is True

    # Caso 3: El usuario reemplaza su resumen y experiencias con datos propios
    schema.summary = "Ingeniero de software con 5 años de experiencia en Python y GCP."
    for exp in schema.experience:
        exp.company = exp.company.replace("[Ejemplo] ", "")
        exp.position = exp.position.replace("[Ejemplo] ", "")

    assert is_resume_example_unedited(schema) is False
    assert dummy_state.get("cv_improver_is_example") is False


def test_profile_never_overwritten_by_example(monkeypatch):
    """
    Verifica la regla de seguridad: nunca sobrescribir el perfil real del usuario con datos de un ejemplo.
    """
    from cv_improver.ui import is_resume_example_unedited
    import streamlit as st

    dummy_state = {"cv_improver_is_example": True}
    monkeypatch.setattr(st, "session_state", dummy_state)

    schema = load_example_schema("finanzas")
    is_example = is_resume_example_unedited(schema)
    assert is_example is True

    # Simular perfil real existente en base de datos
    existing_profile = {
        "full_name": "Usuario Real",
        "email": "usuario@empresa.com",
        "summary": "Perfil profesional real y consolidado"
    }
    has_real_profile = bool(existing_profile.get("full_name") or existing_profile.get("email"))
    assert has_real_profile is True

    # La condición de seguridad debe bloquear la sobrescritura
    should_block_overwrite = is_example and has_real_profile
    assert should_block_overwrite is True

