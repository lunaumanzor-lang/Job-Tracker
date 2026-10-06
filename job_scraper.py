# ==============================================================================
# PROYECTO: AI Job Application Tracker
# FASE 5.2: Extractor de Contenido Web para Vacantes (job_scraper.py)
# ==============================================================================

"""
CONCEPTOS Y LIMITACIONES DEL WEB SCRAPING EN PORTALES DE EMPLEO:

1. Client-Side Rendering (SPAs - React / Vue / Angular):
   Sitios como LinkedIn, Indeed o Glassdoor son aplicaciones de una sola página.
   Cuando 'requests' descarga el HTML vía HTTP GET, el navegador aún no ha ejecutado
   el código JavaScript que renderiza el texto de la vacante. El HTML inicial
   suele venir prácticamente vacío (<div id="root"></div>).

2. Protecciones Anti-Scraping y WAF (Cloudflare, Akamai):
   Plataformas como LinkedIn detectan peticiones que no provienen de un navegador
   humano (sin huella TLS o cabeceras completas) y devuelven inmediatamente códigos
   como HTTP 403 Forbidden o HTTP 999 Request Denied.

3. Muros de Autenticación (Login Walls / Authwalls):
   La mayoría de vacantes de LinkedIn redirigen a la pantalla de 'Sign in to LinkedIn'
   si no detectan una cookie de sesión activa.

POR ESTAS RAZONES:
Esta herramienta implementa una extracción 'Best Effort' (el mejor esfuerzo posible).
Si el portal bloquea la petición o devuelve HTML vacío, la aplicación captura el evento
de forma elegante y le indica al usuario que copie y pegue el texto directamente.
"""

import logging
from typing import Tuple
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Cabeceras estándar que simulan una navegación regular desde Google Chrome en Windows
STANDARD_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en-US;q=0.8,en;q=0.7",
    "Upgrade-Insecure-Requests": "1",
}


def extract_job_text_from_url(url: str, timeout: int = 8) -> Tuple[bool, str]:
    """
    Intenta descargar y extraer el texto visible de una vacante a partir de su URL.
    
    Parámetros:
        url: La dirección web de la vacante (ej. LinkedIn, Indeed, sitio de la empresa).
        timeout: Tiempo máximo de espera en segundos antes de abortar.
        
    Retorna:
        Una tupla (éxito: bool, resultado: str).
        - Si éxito es True, 'resultado' contiene el texto limpio de la vacante.
        - Si éxito es False, 'resultado' contiene el mensaje explicativo del bloqueo.
    """
    url_limpia = url.strip()
    if not url_limpia.startswith(("http://", "https://")):
        return False, "La URL ingresada no es válida. Debe iniciar con http:// o https://"

    import re

    # Manejo especializado para LinkedIn (Guest API pública sin login-wall)
    if "linkedin.com" in url_limpia.lower():
        m_id = re.search(r'(?:/view/|currentJobId=|/jobs/|jobId=)(\d+)', url_limpia)
        if m_id:
            job_id = m_id.group(1)
            guest_url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
            try:
                resp_li = requests.get(guest_url, headers=STANDARD_HEADERS, timeout=timeout)
                if resp_li.status_code == 200 and len(resp_li.text) > 500:
                    soup_li = BeautifulSoup(resp_li.content, "html.parser")
                    for tag in soup_li(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
                        tag.decompose()
                    lineas_li = [linea.strip() for linea in soup_li.get_text(separator="\n").splitlines()]
                    texto_li = "\n".join(linea for linea in lineas_li if linea)
                    if len(texto_li) >= 200:
                        return True, texto_li
            except Exception as ex_li:
                logger.warning(f"Aviso consultando endpoint guest de LinkedIn: {ex_li}")

    try:
        custom_headers = dict(STANDARD_HEADERS)
        if "indeed.com" in url_limpia.lower():
            custom_headers["Referer"] = "https://www.google.com/"

        response = requests.get(
            url_limpia,
            headers=custom_headers,
            timeout=timeout,
            allow_redirects=True
        )
        
        # Detección de bloqueos comunes por código de estado
        if response.status_code == 403:
            return False, (
                "🔒 El sitio web denegó el acceso (HTTP 403 Forbidden). "
                "Portales como LinkedIn suelen bloquear scrapers automáticos. "
                "Por favor copia y pega el texto de la vacante manualmente en el recuadro inferior."
            )
        elif response.status_code == 999:
            return False, (
                "🔒 LinkedIn bloqueó la conexión automática (Código 999 Authwall). "
                "Por favor copia y pega el texto de la vacante en el área de texto."
            )
        elif response.status_code != 200:
            return False, (
                f"El servidor respondió con código de estado HTTP {response.status_code}. "
                "Por favor copia y pega el texto de la vacante manualmente."
            )

        # Parsear el HTML con BeautifulSoup
        soup = BeautifulSoup(response.content, "html.parser")

        # Eliminar etiquetas que contienen código, estilos, cabeceras y pies de página
        for elemento_inutil in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
            elemento_inutil.decompose()

        # Extraer texto legible
        lineas = [linea.strip() for linea in soup.get_text(separator="\n").splitlines()]
        # Filtrar líneas vacías
        texto_limpio = "\n".join(linea for linea in lineas if linea)

        # Si el texto es sospechosamente corto (< 150 caracteres), probablemente cayó en un login wall
        if len(texto_limpio) < 150:
            return False, (
                "⚠️ La página no devolvió suficiente contenido de texto "
                "(es posible que requiera inicio de sesión o use renderizado JavaScript en el cliente). "
                "Por favor copia y pega el texto de la vacante en el área de texto."
            )

        return True, texto_limpio

    except requests.exceptions.Timeout:
        return False, "⏱️ Tiempo de espera agotado al intentar conectar con el portal de empleo."
    except requests.exceptions.RequestException as e:
        logger.warning(f"Error al descargar URL {url_limpia}: {e}")
        return False, f"Error de conexión: {str(e)}"
