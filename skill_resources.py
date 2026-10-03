"""
skill_resources.py

Resuelve una sugerencia de estudio gratuita para una skill faltante,
SIN depender de que un LLM genere o alucine una URL.

El LLM solo debe devolver: skill, importance, context, category.
Este modulo se encarga de traducir "category" a una plataforma real
y verificada por ti.
"""

import requests

# -----------------------------------------------------------------
# Tabla curada: categoria -> plataforma gratuita de confianza.
# Cada entrada usa la URL HOME o de categoria/tema de la plataforma,
# no un patron de busqueda adivinado. Esto es lo que tu verificas
# una vez, manualmente, y queda estable.
# -----------------------------------------------------------------
FREE_LEARNING_PLATFORMS = {
    "Operating Systems": {
        "name": "Linux Foundation - Training (free courses)",
        "url": "https://training.linuxfoundation.org/free-courses/",
    },
    "Cloud & Virtualization": {
        "name": "AWS Skill Builder (free tier)",
        "url": "https://skillbuilder.aws/",
    },
    "CI/CD & DevOps": {
        "name": "HashiCorp Developer (Terraform, Vault, etc. - free)",
        "url": "https://developer.hashicorp.com/tutorials/library",
    },
    "Databases": {
        "name": "PostgreSQL Tutorial (free)",
        "url": "https://www.postgresqltutorial.com/",
    },
    "Security": {
        "name": "TryHackMe (free rooms)",
        "url": "https://tryhackme.com/hacktivities",
    },
    "Identity & Access Management": {
        "name": "Okta Developer (free docs & guides)",
        "url": "https://developer.okta.com/docs/",
    },
    "Programming & Scripting": {
        "name": "freeCodeCamp curriculum",
        "url": "https://www.freecodecamp.org/learn/",
    },
    "Monitoring": {
        "name": "Grafana Labs Learning Hub (free)",
        "url": "https://grafana.com/tutorials/",
    },
    "Collaboration & ITSM": {
        "name": "Atlassian University (free courses)",
        "url": "https://university.atlassian.com/",
    },
    "Business/Soft Skills": {
        "name": "Alison (free courses)",
        "url": "https://alison.com/",
    },
}

# Fallback universal: YouTube tiene un patron de busqueda estable y
# documentado (no adivinado), util cuando ninguna categoria curada
# aplica bien.
YOUTUBE_SEARCH_BASE = "https://www.youtube.com/results?search_query="


def recommend_resource(skill: str, category: str) -> dict:
    """
    Devuelve una sugerencia de estudio confiable para una skill.
    No inventa URLs: usa la tabla curada, o un fallback de busqueda
    en una plataforma con patron de URL verificado (YouTube).
    """
    platform = FREE_LEARNING_PLATFORMS.get(category)

    if platform:
        return {
            "skill": skill,
            "platform": platform["name"],
            "url": platform["url"],
            "source": "curated",
        }

    # Fallback: busqueda en YouTube (patron estable y documentado)
    query = skill.replace(" ", "+")
    return {
        "skill": skill,
        "platform": "YouTube (busqueda)",
        "url": f"{YOUTUBE_SEARCH_BASE}{query}+tutorial+free",
        "source": "fallback_search",
    }


def recommend_from_ms_learn_catalog(skill: str) -> dict | None:
    """
    Para skills de stack Microsoft/Azure, consulta la API OFICIAL
    de Microsoft Learn (documentada, no adivinada) y devuelve un
    link real a un modulo de entrenamiento existente.

    Docs: https://learn.microsoft.com/en-us/training/support/catalog-api
    """
    try:
        response = requests.get(
            "https://learn.microsoft.com/api/catalog/",
            params={"type": "modules", "q": skill},
            timeout=5,
        )
        response.raise_for_status()
        data = response.json()
        modules = data.get("modules", [])
        if not modules:
            return None

        first = modules[0]
        return {
            "skill": skill,
            "platform": "Microsoft Learn",
            "url": first.get("url"),
            "title": first.get("title"),
            "source": "ms_learn_catalog_api",
        }
    except (requests.RequestException, ValueError):
        # Si la API falla o cambia, no rompemos el flujo: devolvemos
        # None y dejamos que el llamador use el fallback curado.
        return None


if __name__ == "__main__":
    # Ejemplos de uso
    print(recommend_resource("Kubernetes", "CI/CD & DevOps"))
    print(recommend_resource("Terraform", "CI/CD & DevOps"))
    print(recommend_resource("Negotiation", "Business/Soft Skills"))
    print(recommend_from_ms_learn_catalog("Azure Functions"))
