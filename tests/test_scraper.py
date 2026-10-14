# ==============================================================================
# PROYECTO: AI Job Application Tracker
# PRUEBAS UNITARIAS: job_scraper.py (Seguridad SSRF, streaming y límites)
# ==============================================================================

import socket
from unittest.mock import MagicMock, patch

import pytest
import requests

from job_scraper import (
    DEFAULT_TIMEOUT,
    MAX_CONTENT_BYTES,
    MAX_REDIRECTS,
    extract_job_text_from_url,
    is_safe_ip,
    validate_url_safety,
)


# ------------------------------------------------------------------------------
# 1. PRUEBAS DE VALIDACIÓN DE SEGURIDAD (SSRF & ESQUEMAS)
# ------------------------------------------------------------------------------

def test_scheme_validation():
    """Solo se permiten esquemas http:// y https://."""
    bad_urls = [
        "ftp://example.com/job",
        "file:///etc/passwd",
        "gopher://example.com/",
        "data:text/html,<h1>Hola</h1>",
        "javascript:alert(1)",
        "not_a_url",
        "",
        None,
    ]
    for url in bad_urls:
        ok, msg = extract_job_text_from_url(url)
        assert not ok
        assert "http://" in msg.lower() or "no es válida" in msg.lower()


def test_block_localhost():
    """Bloquea localhost y subdominios de localhost sin peticiones de red."""
    targets = [
        "http://localhost/job",
        "http://localhost:8080/vacante",
        "https://localhost/api",
        "http://sub.localhost/job",
    ]
    for url in targets:
        ok, msg = extract_job_text_from_url(url)
        assert not ok
        assert "localhost" in msg.lower() or "no permitida" in msg.lower()


def test_block_loopback_127_0_0_1():
    """Bloquea 127.0.0.1 y rango completo 127.0.0.0/8."""
    targets = [
        "http://127.0.0.1/vacante",
        "http://127.0.0.1:3000/api",
        "http://127.0.1.1/test",
    ]
    for url in targets:
        ok, msg = extract_job_text_from_url(url)
        assert not ok
        assert "no está permitida" in msg.lower() or "interna o privada" in msg.lower()


def test_block_cloud_metadata_169_254_169_254():
    """Bloquea explícitamente 169.254.169.254 (Metadata service) y link-local."""
    targets = [
        "http://169.254.169.254/latest/meta-data/",
        "http://169.254.169.254/computeMetadata/v1/",
        "http://169.254.1.1/internal",
    ]
    for url in targets:
        ok, msg = extract_job_text_from_url(url)
        assert not ok
        assert "no está permitida" in msg.lower() or "interna o privada" in msg.lower()


def test_block_private_networks_rfc1918():
    """Bloquea redes privadas 192.168.x.x, 10.x.x.x y 172.16-31.x.x."""
    targets = [
        "http://192.168.1.1/job",
        "http://192.168.0.254:8080/portal",
        "http://10.0.0.1/vacante",
        "http://10.255.255.255/api",
        "http://172.16.0.1/trabajo",
        "http://172.31.255.255/admin",
    ]
    for url in targets:
        ok, msg = extract_job_text_from_url(url)
        assert not ok
        assert "no está permitida" in msg.lower() or "interna o privada" in msg.lower()


def test_block_0_0_0_0():
    """Bloquea 0.0.0.0 y rango 0.0.0.0/8."""
    targets = [
        "http://0.0.0.0:8000/job",
        "http://0.0.0.0/vacante",
    ]
    for url in targets:
        ok, msg = extract_job_text_from_url(url)
        assert not ok
        assert "no permitida" in msg.lower() or "localhost" in msg.lower() or "no está permitida" in msg.lower()


def test_block_ipv6_equivalents():
    """Bloquea loopback IPv6 (::1), link-local (fe80::) y privadas (fc00::)."""
    targets = [
        "http://[::1]:8080/job",
        "http://[fe80::1]/vacante",
        "http://[fc00::1]/internal",
    ]
    for url in targets:
        ok, msg = extract_job_text_from_url(url)
        assert not ok
        assert "no está permitida" in msg.lower() or "interna o privada" in msg.lower()


def test_block_dns_resolution_to_private_ip():
    """Si un dominio público resuelve a una IP interna, debe bloquearse."""
    # Simulamos que internal-careers.example.com resuelve a 192.168.1.50
    mock_addrinfo = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('192.168.1.50', 80))
    ]
    with patch("socket.getaddrinfo", return_value=mock_addrinfo):
        ok, msg = extract_job_text_from_url("https://internal-careers.example.com/job")
        assert not ok
        assert "no está permitida" in msg.lower() or "interna o privada" in msg.lower()


# ------------------------------------------------------------------------------
# 2. PRUEBAS DE REDIRECCIONES Y REDIRECCIÓN A IPS PRIVADAS
# ------------------------------------------------------------------------------

def test_redirect_to_private_ip_is_blocked():
    """Una URL aparentemente pública que redirige a una IP privada debe ser bloqueada."""
    # 1. El dominio inicial resuelve a IP pública segura
    public_addrinfo = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 80))
    ]

    mock_resp_redirect = MagicMock()
    mock_resp_redirect.status_code = 302
    mock_resp_redirect.headers = {"Location": "http://192.168.1.1/secret/job"}

    with patch("socket.getaddrinfo", return_value=public_addrinfo):
        with patch("requests.Session.get", return_value=mock_resp_redirect):
            ok, msg = extract_job_text_from_url("https://legit-jobs.example.com/posting")
            assert not ok
            assert "no está permitida" in msg.lower() or "interna o privada" in msg.lower()


def test_max_redirects_exceeded():
    """Más de 3 redirecciones deben abortar la petición."""
    public_addrinfo = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 80))
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 302
    mock_resp.headers = {"Location": "https://legit-jobs.example.com/step"}

    with patch("socket.getaddrinfo", return_value=public_addrinfo):
        with patch("requests.Session.get", return_value=mock_resp):
            ok, msg = extract_job_text_from_url("https://legit-jobs.example.com/start")
            assert not ok
            assert "redirecciones" in msg.lower()


# ------------------------------------------------------------------------------
# 3. PRUEBAS DE LÍMITE DE TAMAÑO (2 MB) Y STREAMING
# ------------------------------------------------------------------------------

def test_response_exceeds_2mb_via_content_length():
    """Rechaza peticiones con cabecera Content-Length mayor a 2 MB sin descargar."""
    public_addrinfo = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 80))
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {
        "Content-Type": "text/html; charset=utf-8",
        "Content-Length": str(2 * 1024 * 1024 + 1),  # 2MB + 1 byte
    }

    with patch("socket.getaddrinfo", return_value=public_addrinfo):
        with patch("requests.Session.get", return_value=mock_resp):
            ok, msg = extract_job_text_from_url("https://legit-jobs.example.com/huge-page")
            assert not ok
            assert "supera el límite" in msg.lower()
            assert "2 mb" in msg.lower()
            mock_resp.iter_content.assert_not_called()


def test_response_exceeds_2mb_via_streaming_chunks():
    """Interrumpe la descarga si los bloques acumulados superan los 2 MB."""
    public_addrinfo = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 80))
    ]

    # Simulamos chunks que superan 2 MB
    chunk_1mb = b"A" * (1024 * 1024)
    chunk_1mb_plus = b"B" * (1024 * 1024 + 10)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Type": "text/html; charset=utf-8"}
    mock_resp.iter_content.return_value = [chunk_1mb, chunk_1mb_plus]

    with patch("socket.getaddrinfo", return_value=public_addrinfo):
        with patch("requests.Session.get", return_value=mock_resp):
            ok, msg = extract_job_text_from_url("https://legit-jobs.example.com/streaming-huge")
            assert not ok
            assert "supera el límite" in msg.lower()
            assert "2 mb" in msg.lower()
            mock_resp.close.assert_called()


# ------------------------------------------------------------------------------
# 4. PRUEBAS DE TIPO DE CONTENIDO (Content-Type)
# ------------------------------------------------------------------------------

def test_invalid_content_type_rejected():
    """Rechaza tipos de contenido incompatibles como PDF, imágenes o binarios."""
    public_addrinfo = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 80))
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Type": "application/pdf"}

    with patch("socket.getaddrinfo", return_value=public_addrinfo):
        with patch("requests.Session.get", return_value=mock_resp):
            ok, msg = extract_job_text_from_url("https://legit-jobs.example.com/job.pdf")
            assert not ok
            assert "no es compatible" in msg.lower()
            assert "texto o html" in msg.lower()


# ------------------------------------------------------------------------------
# 5. PRUEBAS DE ÉXITO Y CASO ESPECIAL DE LINKEDIN
# ------------------------------------------------------------------------------

def test_successful_scraping_mocked():
    """Descarga y extrae texto limpio de un HTML válido mayor a 150 caracteres."""
    public_addrinfo = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 80))
    ]

    html_content = """
    <html>
      <head><title>Vacante Desarrollador</title><style>body { color: red; }</style></head>
      <body>
        <nav><a href='/'>Inicio</a></nav>
        <main>
          <h1>Desarrollador Senior Python</h1>
          <p>Buscamos un Ingeniero de Software con experiencia sólida en Python, FastAPI, Docker y PostgreSQL.</p>
          <p>Responsabilidades: Diseñar arquitecturas escalables, implementar APIs robustas y colaborar en metodologías ágiles.</p>
          <p>Requisitos: Mínimo 4 años de experiencia en desarrollo backend con pruebas unitarias y CI/CD continuo.</p>
        </main>
        <footer>Pie de página corporativo</footer>
        <script>console.log("tracking");</script>
      </body>
    </html>
    """.encode("utf-8")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Type": "text/html; charset=utf-8"}
    mock_resp.encoding = "utf-8"
    mock_resp.iter_content.return_value = [html_content]

    with patch("socket.getaddrinfo", return_value=public_addrinfo):
        with patch("requests.Session.get", return_value=mock_resp):
            ok, text = extract_job_text_from_url("https://careers.example.com/jobs/python-dev")
            assert ok
            assert "Desarrollador Senior Python" in text
            assert "FastAPI" in text
            assert "Inicio" not in text  # <nav> fue eliminado
            assert "tracking" not in text  # <script> fue eliminado
            assert "color: red" not in text  # <style> fue eliminado


def test_linkedin_guest_api_success():
    """El caso especial de LinkedIn usa la guest API pública cuando hay jobId."""
    public_addrinfo = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('13.107.42.14', 443))
    ]

    html_linkedin = (
        "<div><h1>Tech Lead</h1>"
        "<p>Experiencia liderando equipos de desarrollo de software y entrega de productos de alto impacto global.</p>"
        "<p>Requisitos indispensables: Arquitecturas en la nube, microservicios, mentoring y metodologias agiles SCRUM.</p>"
        "<p>Beneficios: Trabajo remoto, seguro medico integral, presupuesto de formacion continua anual.</p></div>"
    ).encode("utf-8")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Type": "text/html; charset=utf-8"}
    mock_resp.encoding = "utf-8"
    mock_resp.iter_content.return_value = [html_linkedin]

    with patch("socket.getaddrinfo", return_value=public_addrinfo):
        with patch("requests.Session.get", return_value=mock_resp):
            ok, text = extract_job_text_from_url("https://www.linkedin.com/jobs/view/3891234567")
            assert ok
            assert "Tech Lead" in text
            assert "microservicios" in text


def test_linkedin_special_errors_403_and_999():
    """LinkedIn devuelve mensajes descriptivos ante HTTP 403 y 999 sin trazas."""
    public_addrinfo = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('13.107.42.14', 443))
    ]

    # Caso 403
    mock_403 = MagicMock()
    mock_403.status_code = 403
    mock_403.headers = {"Content-Type": "text/html"}

    with patch("socket.getaddrinfo", return_value=public_addrinfo):
        with patch("requests.Session.get", return_value=mock_403):
            ok, msg = extract_job_text_from_url("https://www.linkedin.com/jobs/view/11111")
            assert not ok
            assert "403" in msg or "bloqueó" in msg.lower() or "denegó el acceso" in msg.lower()
            assert "Traceback" not in msg

    # Caso 999 Authwall
    mock_999 = MagicMock()
    mock_999.status_code = 999
    mock_999.headers = {"Content-Type": "text/html"}

    with patch("socket.getaddrinfo", return_value=public_addrinfo):
        with patch("requests.Session.get", return_value=mock_999):
            ok, msg = extract_job_text_from_url("https://www.linkedin.com/jobs/view/22222")
            assert not ok
            assert "999" in msg or "authwall" in msg.lower()
            assert "Traceback" not in msg


# ------------------------------------------------------------------------------
# 6. PRUEBAS DE EXCEPCIONES DE RED SIN TRAZAS TÉCNICAS
# ------------------------------------------------------------------------------

def test_network_timeout_friendly_error():
    """Un timeout de red devuelve un mensaje amigable sin trazas."""
    public_addrinfo = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 80))
    ]

    with patch("socket.getaddrinfo", return_value=public_addrinfo):
        with patch("requests.Session.get", side_effect=requests.exceptions.Timeout("Read timed out")):
            ok, msg = extract_job_text_from_url("https://careers.slowsite.com/job")
            assert not ok
            assert "tiempo de espera agotado" in msg.lower()
            assert "Traceback" not in msg
            assert "Read timed out" not in msg


def test_connection_error_friendly_error():
    """Un error de conexión devuelve mensaje amigable sin exponer socket errors."""
    public_addrinfo = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 80))
    ]

    with patch("socket.getaddrinfo", return_value=public_addrinfo):
        with patch("requests.Session.get", side_effect=requests.exceptions.ConnectionError("Connection refused [Errno 111]")):
            ok, msg = extract_job_text_from_url("https://careers.unreachablesite.com/job")
            assert not ok
            assert "no se pudo establecer conexión" in msg.lower() or "error" in msg.lower()
            assert "Traceback" not in msg
            assert "Errno 111" not in msg
