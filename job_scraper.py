# ==============================================================================
# PROYECTO: Smart Job Tracker
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

4. Medidas de Seguridad y Prevención de SSRF:
   - Solo se permiten esquemas http:// y https://.
   - Se bloquean direcciones de loopback (localhost, 127.0.0.0/8, ::1),
     redes privadas (RFC 1918), link-local (169.254.169.254), no especificadas (0.0.0.0),
     multicast, reservadas y sus equivalentes en IPv6.
   - Se resuelven y verifican todas las direcciones IP asociadas al dominio.
   - Cada redirección HTTP es validada individualmente con las mismas reglas (máx 3).
   - Descarga con stream=True en bloques de 8 KB y tope estricto de 2 MB.
   - Validación de Content-Type (text/html o text/plain).
   - Timeout estricto de 8 segundos sin exposición de trazas técnicas al usuario.
"""

import ipaddress
import logging
import re
import socket
import urllib.parse
from typing import Set, Tuple, Union

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

# Constantes de seguridad y descarga
MAX_CONTENT_BYTES = 2 * 1024 * 1024  # 2 MB tope estricto
CHUNK_SIZE = 8192                    # Bloques de 8 KB
MAX_REDIRECTS = 3                    # Máximo 3 redirecciones validadas
DEFAULT_TIMEOUT = 8                  # 8 segundos


def is_safe_ip(ip_obj: Union[ipaddress.IPv4Address, ipaddress.IPv6Address]) -> bool:
    """
    Verifica si una dirección IP es pública y segura para conectarse.
    Bloquea loopback, direcciones privadas, link-local, multicast, reservadas,
    no especificadas, carrier-grade NAT e IPv4 mapeadas en IPv6.
    """
    # Si es IPv6 con mapeo a IPv4 (ej. ::ffff:127.0.0.1)
    if getattr(ip_obj, "ipv4_mapped", None):
        if not is_safe_ip(ip_obj.ipv4_mapped):
            return False

    if (
        ip_obj.is_loopback
        or ip_obj.is_private
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_reserved
        or ip_obj.is_unspecified
    ):
        return False

    if isinstance(ip_obj, ipaddress.IPv4Address):
        # 0.0.0.0/8 (red local del host)
        if ip_obj in ipaddress.ip_network("0.0.0.0/8"):
            return False
        # 100.64.0.0/10 (Carrier-Grade NAT / Shared Space RFC 6598)
        if ip_obj in ipaddress.ip_network("100.64.0.0/10"):
            return False
        # 169.254.169.254 explícita (Cloud Instance Metadata Service AWS/GCP/Azure)
        if ip_obj == ipaddress.ip_address("169.254.169.254"):
            return False

    return True


def validate_url_safety(url: str) -> Tuple[bool, str]:
    """
    Valida que una URL sea segura para consultar (prevención de SSRF).
    
    Reglas:
    1. Esquema http o https únicamente.
    2. Hostname presente y válido.
    3. Bloqueo de localhost, 0.0.0.0, direcciones privadas, loopback, link-local
       (incluida 169.254.169.254) e IPv6 equivalentes, resolviendo todas las IPs del host.
    """
    if not url or not isinstance(url, str):
        return False, "La URL ingresada no es válida. Debe ser una cadena de texto no vacía."

    url_limpia = url.strip()
    try:
        parsed = urllib.parse.urlparse(url_limpia)
    except Exception:
        return False, "La URL ingresada tiene un formato no válido."

    if parsed.scheme.lower() not in ("http", "https"):
        return False, "La URL ingresada no es válida. Solo se admiten direcciones con http:// o https://"

    hostname = parsed.hostname
    if not hostname:
        return False, "La URL ingresada no contiene un nombre de host válido."

    host_lower = hostname.lower()
    if host_lower in ("localhost", "0.0.0.0") or host_lower.endswith(".localhost"):
        return False, "Acceso denegado: no se permiten direcciones locales (localhost)."

    # Si es numérico entero (ej. IP en formato decimal 2130706433)
    if hostname.isdigit():
        try:
            ip_num = ipaddress.ip_address(int(hostname))
            if not is_safe_ip(ip_num):
                return False, "Acceso denegado: la dirección IP ingresada no está permitida (red interna o privada)."
        except ValueError:
            return False, "La dirección numérica del host no es válida."

    # Si el hostname ya es directamente una IP literal (IPv4 o IPv6)
    try:
        ip_direct = ipaddress.ip_address(hostname)
        if not is_safe_ip(ip_direct):
            return False, "Acceso denegado: la dirección IP ingresada no está permitida (red interna o privada)."
    except ValueError:
        pass  # Es un nombre de dominio estándar

    # Resolver todas las IPs del host vía DNS (IPv4 e IPv6)
    try:
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False, "No se pudo resolver el nombre de dominio de la URL."
    except Exception:
        return False, "Error al resolver la dirección de la URL."

    resolved_ips: Set[str] = set()
    for entry in addr_info:
        sockaddr = entry[4]
        if sockaddr and len(sockaddr) > 0:
            resolved_ips.add(sockaddr[0])

    if not resolved_ips:
        return False, "No se encontraron direcciones IP para el host de la URL."

    for ip_str in resolved_ips:
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError:
            return False, f"Dirección IP no válida detectada: {ip_str}"

        if not is_safe_ip(ip_obj):
            return False, "Acceso denegado: la dirección IP resuelta no está permitida (red interna o privada)."

    return True, ""


def _safe_fetch(
    url: str,
    custom_headers: dict = None,
    timeout: int = DEFAULT_TIMEOUT,
    session: requests.Session = None
) -> Tuple[bool, str, int]:
    """
    Descarga el contenido de una URL aplicando validaciones de seguridad:
    - Validación SSRF en URL inicial y en cada salto de redirección (máx 3).
    - stream=True con límite estricto de 2 MB leído en bloques.
    - Validación de Content-Type (text/html o text/plain).
    - Manejo seguro de errores sin exponer trazas técnicas.
    
    Retorna:
        (éxito: bool, contenido_o_error: str, status_code: int)
    """
    current_url = url
    redirect_count = 0
    http_session = session or requests.Session()

    while True:
        # 1. Validar seguridad SSRF de la URL actual
        es_segura, motivo_error = validate_url_safety(current_url)
        if not es_segura:
            return False, motivo_error, 0

        # Preparar cabeceras para la petición
        headers = dict(custom_headers) if custom_headers else dict(STANDARD_HEADERS)
        if "indeed.com" in current_url.lower():
            headers["Referer"] = "https://www.google.com/"

        try:
            response = http_session.get(
                current_url,
                headers=headers,
                timeout=timeout,
                allow_redirects=False,
                stream=True
            )
        except requests.exceptions.Timeout:
            return False, "⏱️ Tiempo de espera agotado al intentar conectar con el portal de empleo.", 0
        except requests.exceptions.SSLError:
            return False, "Error de seguridad SSL al intentar conectar con el portal de empleo.", 0
        except requests.exceptions.ConnectionError:
            return False, "No se pudo establecer conexión con el servidor de la vacante.", 0
        except requests.exceptions.RequestException:
            return False, "Ocurrió un error de red al intentar descargar la vacante.", 0
        except Exception as e:
            logger.warning(f"Error inesperado al conectar con {current_url}: {e}")
            return False, "No fue posible acceder a la URL especificada.", 0

        # 2. Gestionar redirecciones manualmente y validar destino
        if response.status_code in (301, 302, 303, 307, 308):
            redirect_count += 1
            location = response.headers.get("Location")
            response.close()

            if redirect_count > MAX_REDIRECTS:
                return False, f"Se superó el límite máximo de redirecciones permitidas ({MAX_REDIRECTS}).", response.status_code

            if not location:
                return False, "La respuesta de redirección no incluye la dirección de destino.", response.status_code

            current_url = urllib.parse.urljoin(current_url, location)
            continue

        # 3. Validar código de estado
        status_code = response.status_code
        if status_code == 403:
            response.close()
            return False, (
                "🔒 El sitio web denegó el acceso (HTTP 403 Forbidden). "
                "Portales como LinkedIn suelen bloquear scrapers automáticos. "
                "Por favor copia y pega el texto de la vacante manualmente en el recuadro inferior."
            ), status_code
        elif status_code == 999:
            response.close()
            return False, (
                "🔒 LinkedIn bloqueó la conexión automática (Código 999 Authwall). "
                "Por favor copia y pega el texto de la vacante en el área de texto."
            ), status_code
        elif status_code != 200:
            response.close()
            return False, (
                f"El servidor respondió con código de estado HTTP {status_code}. "
                "Por favor copia y pega el texto de la vacante manualmente."
            ), status_code

        # 4. Validar Content-Type
        content_type = response.headers.get("Content-Type", "").lower()
        if not any(valid_type in content_type for valid_type in ("text/html", "text/plain", "application/xhtml+xml")):
            response.close()
            return False, "El tipo de contenido recibido no es compatible (solo se admite texto o HTML).", status_code

        # 5. Validar Content-Length previo si existe en cabeceras
        content_length = response.headers.get("Content-Length")
        if content_length and content_length.strip().isdigit():
            if int(content_length.strip()) > MAX_CONTENT_BYTES:
                response.close()
                return False, "El tamaño del contenido supera el límite máximo permitido de 2 MB.", status_code

        # 6. Descargar en bloques con límite estricto de 2 MB
        downloaded_chunks = []
        total_bytes = 0
        try:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    total_bytes += len(chunk)
                    if total_bytes > MAX_CONTENT_BYTES:
                        response.close()
                        return False, "El tamaño del contenido supera el límite máximo permitido de 2 MB.", status_code
                    downloaded_chunks.append(chunk)
        except requests.exceptions.Timeout:
            return False, "⏱️ Tiempo de espera agotado al descargar el contenido de la vacante.", status_code
        except requests.exceptions.RequestException:
            return False, "Ocurrió un error de red durante la descarga de la vacante.", status_code
        except Exception as e:
            logger.warning(f"Error al descargar contenido de {current_url}: {e}")
            return False, "No fue posible completar la descarga de la vacante.", status_code
        finally:
            response.close()

        raw_bytes = b"".join(downloaded_chunks)
        encoding = response.encoding or "utf-8"
        try:
            html_text = raw_bytes.decode(encoding, errors="replace")
        except Exception:
            html_text = raw_bytes.decode("utf-8", errors="replace")

        return True, html_text, status_code


def extract_job_text_from_url(url: str, timeout: int = DEFAULT_TIMEOUT) -> Tuple[bool, str]:
    """
    Intenta descargar y extraer el texto visible de una vacante a partir de su URL.
    
    Parámetros:
        url: La dirección web de la vacante (ej. LinkedIn, Indeed, sitio de la empresa).
        timeout: Tiempo máximo de espera en segundos antes de abortar (default: 8s).
        
    Retorna:
        Una tupla (éxito: bool, resultado: str).
        - Si éxito es True, 'resultado' contiene el texto limpio de la vacante.
        - Si éxito es False, 'resultado' contiene el mensaje explicativo del bloqueo.
    """
    if not url or not isinstance(url, str):
        return False, "La URL ingresada no es válida. Debe iniciar con http:// o https://"

    url_limpia = url.strip()
    if not url_limpia.startswith(("http://", "https://")):
        return False, "La URL ingresada no es válida. Debe iniciar con http:// o https://"

    # 1. Validación de seguridad previa (bloqueo temprano de SSRF)
    es_segura, motivo_error = validate_url_safety(url_limpia)
    if not es_segura:
        return False, motivo_error

    # 2. Manejo especializado para LinkedIn (Guest API pública sin login-wall)
    if "linkedin.com" in url_limpia.lower():
        m_id = re.search(r'(?:/view/|currentJobId=|/jobs/|jobId=)(\d+)', url_limpia)
        if m_id:
            job_id = m_id.group(1)
            guest_url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
            try:
                ok_li, html_li, _ = _safe_fetch(guest_url, custom_headers=STANDARD_HEADERS, timeout=timeout)
                if ok_li and len(html_li) > 500:
                    soup_li = BeautifulSoup(html_li, "html.parser")
                    for tag in soup_li(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
                        tag.decompose()
                    lineas_li = [linea.strip() for linea in soup_li.get_text(separator="\n").splitlines()]
                    texto_li = "\n".join(linea for linea in lineas_li if linea)
                    if len(texto_li) >= 200:
                        return True, texto_li
            except Exception as ex_li:
                logger.warning(f"Aviso consultando endpoint guest de LinkedIn: {ex_li}")

    # 3. Descarga segura estándar
    ok_fetch, content_or_err, _ = _safe_fetch(url_limpia, timeout=timeout)
    if not ok_fetch:
        return False, content_or_err

    # 4. Parsear el HTML con BeautifulSoup
    soup = BeautifulSoup(content_or_err, "html.parser")

    # Eliminar etiquetas que contienen código, estilos, cabeceras y pies de página
    for elemento_inutil in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
        elemento_inutil.decompose()

    # Extraer texto legible
    lineas = [linea.strip() for linea in soup.get_text(separator="\n").splitlines()]
    texto_limpio = "\n".join(linea for linea in lineas if linea)

    # Si el texto es sospechosamente corto (< 150 caracteres), probablemente cayó en un login wall
    if len(texto_limpio) < 150:
        return False, (
            "⚠️ La página no devolvió suficiente contenido de texto "
            "(es posible que requiera inicio de sesión o use renderizado JavaScript en el cliente). "
            "Por favor copia y pega el texto de la vacante en el área de texto."
        )

    return True, texto_limpio
