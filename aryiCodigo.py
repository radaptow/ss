#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ARYI / Syntax Sanctuary - Orquestador Maestro Unificado v8.1 (Blindado contra Copy-Paste)
Fusion de:
  - aryiCodigo.py (Orquestador CLI, Parser XML/Markdown, Bash/BG, Escritura Atomica)
  - aryiTelegram.py (Agente Autonomo Telegram, Cola GPU, Whisper/TTS/SD, Auto-Evolucion AST)
  - Navegador Web Integrado (Busqueda DuckDuckGo + Lector/Extractor de paginas y enlaces)
  - Selector de Modelo Pre-Peticion + Tutorial Interactivo del Framework PHP (v2.php)
"""

from __future__ import annotations

import ast
import base64
import difflib
import hashlib
import html as html_lib
import json
import mimetypes
import os
import re
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.styles import Style
    PROMPT_TOOLKIT_OK = True
except Exception:
    PromptSession = None  # type: ignore
    Style = None  # type: ignore
    PROMPT_TOOLKIT_OK = False

# Constante para evitar triples backticks literales que rompen el copiado en web
BT = "`" * 3


# =============================================================================
# 1. CONFIGURACION GLOBAL, CREDENCIALES Y ENDPOINTS
# =============================================================================
def _env_int(nombre: str, defecto: int) -> int:
    try:
        return int(os.getenv(nombre, "").strip() or defecto)
    except ValueError:
        return defecto


TELEGRAM_BOT_TOKEN = os.getenv("ARYI_TG_TOKEN", "8449908090:AAFS8OqY-a5D1lejzhIN4bGcutO_AzCYEC0")
TELEGRAM_CHAT_ID   = os.getenv("ARYI_TG_CHAT_ID", "8933548802")

DOCKER_IP         = os.getenv("ARYI_WINDOWS_GPU_IP", "100.115.1.71")
DEFAULT_LLM_MODEL = os.getenv("ARYI_DEFAULT_MODEL", "qwen2.5-coder:0.5b")

NODOS_OLLAMA: Dict[str, Dict[str, str]] = {
    "1": {"nombre": "Local / Contenedor (ollama:11434)", "url": "http://ollama:11434/api", "host": "ollama"},
    "2": {"nombre": f"Remoto GPU ({DOCKER_IP}:11434)", "url": f"http://{DOCKER_IP}:11434/api", "host": DOCKER_IP},
}

SERVICIOS_IA = {
    "stt": f"http://{DOCKER_IP}:8000/v1/audio/transcriptions",
    "tts": f"http://{DOCKER_IP}:5050/tts",
    "sd":  f"http://{DOCKER_IP}:7860/sdapi/v1/txt2img",
}

LIMITES_CONTEXTO: Dict[str, int] = {
    "qwen2.5-coder:0.5b": 32768,
    "virtuanista/lfm2.5-8b-a1b-uncensored:q8_0": 16384,
}
CONTEXTO_POR_DEFECTO = 8192
RESERVA_CONTEXTO = 0.72

AGENT_FILE = Path(__file__).resolve()
PYTHON_DIR = AGENT_FILE.parent

if os.getenv("ARYI_WORKSPACE_ROOT"):
    WORKSPACE_ROOT = Path(os.environ["ARYI_WORKSPACE_ROOT"]).expanduser().resolve()
elif PYTHON_DIR.name.lower() == "python":
    WORKSPACE_ROOT = PYTHON_DIR.parent
elif (PYTHON_DIR / "workspace").is_dir():
    WORKSPACE_ROOT = (PYTHON_DIR / "workspace").resolve()
else:
    WORKSPACE_ROOT = Path.cwd().resolve()

STATE_FILE     = PYTHON_DIR / "agent_state.json"
BACKUP_DIR     = PYTHON_DIR / "backups"
REPORTS_DIR    = PYTHON_DIR / "reports"
TEMP_DIR       = PYTHON_DIR / "tmp"
PHP_QUEUE_FILE = Path(tempfile.gettempdir()) / "aryi_queue_telemetry_v5.json"

SKIP_DIRECTORIES = {
    ".git", "__pycache__", "node_modules", "vendor",
    "backups", "reports", "tmp", ".idea", ".vscode", ".aryi_logs"
}

READ_ONLY_FILES = {
    "chat_db.json",
    "agent_state.json",
    "aryi_queue_telemetry_v5.json",
    "aryi_queue_telemetry_v4.json",
    "aryi_queue_telemetry_v3.json",
    "aryi_neural_telemetry_v2.json",
}

BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".mp3", ".wav",
    ".ogg", ".oga", ".mp4", ".webm", ".avi", ".mov", ".zip", ".tar", ".gz",
    ".7z", ".rar", ".exe", ".dll", ".so", ".dylib", ".bin", ".pyc", ".pyd",
    ".ttf", ".otf", ".woff", ".woff2", ".eot", ".pdf", ".sqlite", ".db", ".o", ".out"
}

MAX_ARCHIVO_LEER   = 1_000_000
MAX_REF_PHP        = 14_000
MAX_SALIDA_CONSOLA = 2_500
MAX_FEEDBACK       = _env_int("ARYI_MAX_FEEDBACK", 6_000)
TIMEOUT_BASH       = _env_int("ARYI_TIMEOUT_BASH", 120)
TIMEOUT_HTTP_CONN  = 8
TIMEOUT_HTTP_READ  = _env_int("ARYI_HTTP_READ", 300)
PASOS_MAXIMOS      = max(1, _env_int("ARYI_PASOS_MAXIMOS", 4))
PAUSA_ARRANQUE_BG  = 1.5
CHUNK_SIZE_CHARS   = 12_000

FILE_LANGS   = {"file", "archivo", "create_file", "write_file"}
BASH_LANGS   = {"bash", "sh", "shell", "zsh"}
BG_LANGS     = {"bash_bg", "bg", "background", "daemon", "servicio"}
SEARCH_LANGS = {"web_search", "search", "buscar"}
OPEN_LANGS   = {"web_open", "open_url", "navegar"}


def _calcular_raices_permitidas() -> List[Path]:
    raices = [WORKSPACE_ROOT, PYTHON_DIR]
    for bruto in os.getenv("ARYI_ALLOWED_ROOTS", "").split(os.pathsep):
        bruto = bruto.strip()
        if not bruto:
            continue
        try:
            raiz = Path(bruto).expanduser().resolve()
            if raiz not in raices:
                raices.append(raiz)
        except (OSError, RuntimeError):
            continue
    return raices


RAICES_PERMITIDAS = _calcular_raices_permitidas()


def _leer_umask() -> int:
    actual = os.umask(0)
    os.umask(actual)
    return actual


_UMASK = _leer_umask()


# =============================================================================
# 2. LOGGER, UTILIDADES Y COLA COOPERATIVA DE GPU
# =============================================================================
def log_console(tag: str, message: str) -> None:
    now_str = datetime.now().strftime("%H:%M:%S")
    print(f"[{now_str}] [{tag}] {message}", flush=True)


def check_tcp_port(ip: str, port: int, timeout_sec: float = 4.0) -> Tuple[bool, float, str]:
    t0 = time.time()
    try:
        with socket.create_connection((ip, port), timeout=timeout_sec):
            ms = round((time.time() - t0) * 1000, 1)
            return True, ms, "OK"
    except Exception as e:
        ms = round((time.time() - t0) * 1000, 1)
        return False, ms, str(e)


def recortar(texto: Any, limite: int = MAX_FEEDBACK, proporcion_cola: float = 0.7) -> str:
    texto = str(texto)
    if limite <= 0 or len(texto) <= limite:
        return texto
    marcador = f"\n... [{len(texto) - limite} caracteres omitidos] ...\n"
    util = max(0, limite - len(marcador))
    n_cola = int(util * proporcion_cola)
    n_ini = util - n_cola
    return texto[:n_ini] + marcador + (texto[-n_cola:] if n_cola else "")


def estimar_tokens(texto: str) -> int:
    return max(1, int(len(texto) / 3.5)) if texto else 0


def obtener_limite_contexto(modelo: str) -> int:
    if modelo in LIMITES_CONTEXTO:
        return LIMITES_CONTEXTO[modelo]
    base = modelo.split(":", 1)[0]
    for clave, valor in LIMITES_CONTEXTO.items():
        if clave.split(":", 1)[0] == base:
            return valor
    return CONTEXTO_POR_DEFECTO


def describir_entorno() -> str:
    try:
        es_root = os.geteuid() == 0  # type: ignore[attr-defined]
    except AttributeError:
        es_root = False
    docker = " dentro de un contenedor Docker" if Path("/.dockerenv").exists() else ""
    if es_root:
        return (
            f"Corres en Linux{docker} como usuario 'root'. NUNCA uses 'sudo'. "
            "Para paquetes del sistema usa directamente 'apt-get update && apt-get install -y paquete'."
        )
    return (
        f"Corres{docker} como un usuario SIN privilegios. NO tienes sudo: si falta un paquete del "
        "sistema, diselo al operador en lugar de intentar instalarlo."
    )


class CooperativeGpuTurn:
    """Sincroniza el uso de GPU con el monolito PHP y otros procesos locales."""
    def __init__(self, task_type: str = "ollama"):
        self.task_type = task_type
        self.ticket_id = f"py_unified_{uuid.uuid4().hex[:8]}"

    def _mutate_queue(self, callback: Callable[[dict, float], bool]) -> bool:
        try:
            with open(PHP_QUEUE_FILE, "a+", encoding="utf-8") as fp:
                if HAS_FCNTL:
                    fcntl.flock(fp.fileno(), fcntl.LOCK_EX)
                fp.seek(0)
                raw = fp.read()
                try:
                    state = json.loads(raw) if raw.strip() else None
                except Exception:
                    state = None

                if not isinstance(state, dict) or "queue" not in state:
                    state = {"queue": {}, "metrics": {}}

                now = time.time()
                for tid, item in list(state["queue"].items()):
                    last_beat = float(item.get("updated_at", now))
                    timeout = 25.0 if item.get("status") == "processing" else 10.0
                    if (now - last_beat) > timeout:
                        del state["queue"][tid]

                res = callback(state, now)

                fp.seek(0)
                fp.truncate(0)
                fp.write(json.dumps(state, ensure_ascii=False))
                fp.flush()
                if HAS_FCNTL:
                    fcntl.flock(fp.fileno(), fcntl.LOCK_UN)
                return res
        except Exception:
            return True

    def __enter__(self) -> "CooperativeGpuTurn":
        notified_wait = False
        while True:
            can_start = True

            def _try_acquire(state: dict, now: float) -> bool:
                nonlocal can_start
                q = state["queue"]
                other_tickets = [k for k in q.keys() if k != self.ticket_id]
                if not other_tickets:
                    q[self.ticket_id] = {
                        "id": self.ticket_id,
                        "operator_id": "aryi_unified_orchestrator",
                        "task": self.task_type,
                        "status": "processing",
                        "created_at": now,
                        "started_at": now,
                        "updated_at": now,
                    }
                    can_start = True
                else:
                    can_start = False
                return can_start

            self._mutate_queue(_try_acquire)
            if can_start:
                break
            if not notified_wait:
                log_console("COLA_GPU", "Otro proceso usa la GPU. Esperando turno...")
                notified_wait = True
            time.sleep(1.5)
        return self

    def heartbeat(self) -> None:
        def _touch(state: dict, now: float) -> bool:
            if self.ticket_id in state["queue"]:
                state["queue"][self.ticket_id]["updated_at"] = now
            return True
        self._mutate_queue(_touch)

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        def _release(state: dict, now: float) -> bool:
            state["queue"].pop(self.ticket_id, None)
            return True
        self._mutate_queue(_release)


# =============================================================================
# 3. NAVEGADOR WEB INTEGRADO (BUSQUEDA + LECTOR DE PAGINAS Y ENLACES)
# =============================================================================
class _HTMLTextExtractor(HTMLParser):
    """Convierte HTML crudo en texto limpio y extrae la lista de enlaces navegables."""
    IGNORAR_TAGS = {"script", "style", "noscript", "svg", "head", "iframe", "template"}
    BLOQUE_TAGS = {
        "p", "div", "section", "article", "header", "footer", "main", "aside",
        "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "br", "pre", "blockquote"
    }

    def __init__(self, base_url: str = "") -> None:
        super().__init__()
        self.base_url = base_url
        self._ignore_depth = 0
        self.title: str = ""
        self._in_title = False
        self.chunks: List[str] = []
        self.links: List[Tuple[str, str]] = []
        self._current_href: Optional[str] = None
        self._current_link_text: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        t = tag.lower()
        if t in self.IGNORAR_TAGS:
            self._ignore_depth += 1
            return
        if self._ignore_depth > 0:
            return
        if t == "title":
            self._in_title = True
        if t in self.BLOQUE_TAGS:
            self.chunks.append("\n")
        if t in {"h1", "h2", "h3"}:
            self.chunks.append("\n## ")
        elif t == "li":
            self.chunks.append("\n  * ")
        elif t == "a":
            attr_map = dict(attrs)
            href = (attr_map.get("href") or "").strip()
            if href and not href.startswith(("javascript:", "mailto:", "tel:", "#")):
                self._current_href = urllib.parse.urljoin(self.base_url, href)
                self._current_link_text = []

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in self.IGNORAR_TAGS and self._ignore_depth > 0:
            self._ignore_depth -= 1
            return
        if self._ignore_depth > 0:
            return
        if t == "title":
            self._in_title = False
        if t == "a" and self._current_href:
            label = " ".join("".join(self._current_link_text).split()).strip()
            if label and len(self.links) < 40:
                self.links.append((label[:80], self._current_href))
            self._current_href = None
            self._current_link_text = []
        if t in self.BLOQUE_TAGS:
            self.chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._in_title and not self.title:
            self.title = " ".join(data.split()).strip()
        if self._ignore_depth > 0:
            return
        cleaned = re.sub(r"[ \t\r\f\v]+", " ", data)
        if cleaned.strip():
            self.chunks.append(cleaned)
            if self._current_href is not None:
                self._current_link_text.append(cleaned)

    def get_formatted_page(self, max_chars: int = 7000) -> str:
        raw_text = "".join(self.chunks)
        lines = [line.strip() for line in raw_text.splitlines()]
        compact_lines: List[str] = []
        blank_streak = 0
        for line in lines:
            if not line:
                blank_streak += 1
                if blank_streak <= 1:
                    compact_lines.append("")
            else:
                blank_streak = 0
                compact_lines.append(line)
        body = "\n".join(compact_lines).strip()
        body = recortar(body, max_chars, proporcion_cola=0.4)

        header = f"TITULO: {self.title or '(Sin titulo)'}\nURL: {self.base_url}\n"
        links_section = ""
        if self.links:
            seen = set()
            unique_links = []
            for txt, url in self.links:
                if url not in seen:
                    seen.add(url)
                    unique_links.append(f"  [{len(unique_links)+1}] {txt} -> {url}")
                if len(unique_links) >= 15:
                    break
            links_section = "\n\nENLACES DETECTADOS EN LA PAGINA:\n" + "\n".join(unique_links)

        return f"{header}{'='*50}\n{body}{links_section}"


class NavegadorWebIA:
    """Navegador web ligero sin dependencias externas para el Orquestador y la IA."""
    USER_AGENT = (
        "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
    )

    def __init__(self) -> None:
        self.historial_urls: List[str] = []
        self.ultima_pagina_links: List[Tuple[str, str]] = []

    def buscar(self, query: str, max_results: int = 6) -> str:
        query = query.strip()
        if not query:
            return "Consulta de busqueda vacia."
        log_console("WEB_SEARCH", f"Buscando en Internet: '{query}'...")
        url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
        headers = {"User-Agent": self.USER_AGENT, "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"}

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw_html = resp.read().decode("utf-8", errors="ignore")

            bloques = re.findall(
                r'<a rel="nofollow" class="result__a" href="([^"]+)"[^>]*>(.*?)</a>.*?'
                r'<a class="result__snippet[^>]*>(.*?)</a>',
                raw_html,
                re.DOTALL,
            )

            resultados: List[str] = []
            self.ultima_pagina_links.clear()

            for idx, (raw_href, raw_title, raw_snippet) in enumerate(bloques[:max_results], start=1):
                parsed_href = urllib.parse.urlparse(raw_href)
                qs = urllib.parse.parse_qs(parsed_href.query)
                real_url = qs.get("uddg", [raw_href])[0]
                real_url = html_lib.unescape(real_url)

                titulo = html_lib.unescape(re.sub(r"<[^>]+>", "", raw_title)).strip()
                snippet = html_lib.unescape(re.sub(r"<[^>]+>", "", raw_snippet)).strip()

                self.ultima_pagina_links.append((titulo, real_url))
                resultados.append(
                    f"[{idx}] {titulo}\n"
                    f"    URL: {real_url}\n"
                    f"    Resumen: {snippet}"
                )

            if not resultados:
                return "No se encontraron resultados para esa busqueda."

            log_console("WEB_DONE", f"{len(resultados)} resultados obtenidos.")
            return (
                f"RESULTADOS DE BUSQUEDA PARA: '{query}'\n"
                + "\n\n".join(resultados)
                + '\n\n(La IA puede abrir cualquiera de estas URLs usando <web_open url="..."/>)'
            )
        except Exception as exc:
            log_console("WEB_WARN", f"Error en busqueda web: {exc}")
            return f"Error al buscar en Internet: {exc}"

    def abrir_url(self, url: str, max_chars: int = 7000) -> str:
        url = url.strip().strip("\"'")
        if url.isdigit() and self.ultima_pagina_links:
            idx = int(url) - 1
            if 0 <= idx < len(self.ultima_pagina_links):
                url = self.ultima_pagina_links[idx][1]

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        log_console("WEB_OPEN", f"Abriendo URL: {url}")
        headers = {"User-Agent": self.USER_AGENT, "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"}

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=18) as resp:
                ctype = (resp.headers.get("Content-Type") or "").lower()
                raw_bytes = resp.read(600_000)

            texto_decodificado = raw_bytes.decode("utf-8", errors="replace")
            self.historial_urls.append(url)

            if "application/json" in ctype or "text/plain" in ctype:
                return f"URL: {url} ({ctype})\n{'='*50}\n{recortar(texto_decodificado, max_chars)}"

            extractor = _HTMLTextExtractor(base_url=url)
            extractor.feed(texto_decodificado)
            self.ultima_pagina_links = list(extractor.links)
            return extractor.get_formatted_page(max_chars=max_chars)
        except Exception as exc:
            log_console("WEB_ERR", f"No se pudo abrir {url}: {exc}")
            return f"Error al abrir la URL '{url}': {exc}"


NAVEGADOR = NavegadorWebIA()


# =============================================================================
# 4. REFERENCIA EMBEBIDA Y TUTORIAL INTERACTIVO DEL FRAMEWORK PHP (v2.php)
# =============================================================================
V2_PHP_FALLBACK_REF = (
    "<?php\n"
    "declare(strict_types=1);\n\n"
    "// 1. CONSTANTES DEL FRAMEWORK (HTML Y OLLAMA)\n"
    'define("P", "principal");   # h1\n'
    'define("S", "secundario");  # h2\n'
    'define("M", "mediano");     # h3\n'
    'define("MI", "minusculo");  # h4\n'
    'define("MIN", "miniatura"); # h5\n'
    'define("D", "diminuto");    # h6\n'
    "define('INI', false);       # inicio de etiqueta (<tag>)\n"
    "define('FIN', true);        # cierre de etiqueta (</tag>)\n\n"
    "define('OLLAMA_HOST', 'http://100.115.1.71:11434');\n"
    "define('MOD_QWEN', 'qwen2.5-coder:0.5b');\n"
    "define('MOD_LFM', 'virtuanista/lfm2.5-8b-a1b-uncensored:q8_0');\n\n"
    "define('RES_TEXTO', 'texto');   # Extrae solo el string generado\n"
    "define('RES_ARRAY', 'array');   # Devuelve el array completo decodificado\n"
    "define('RES_ESTADO', 'estado'); # Devuelve metricas de conexion y validacion\n\n"
    "// 2. FUNCIONES DE ESTRUCTURA Y TEXTO HTML\n"
    "// encabezado(string $texto = 'default', string $tamano = 'default') -> h1..h6 segun P, S, M, MI, MIN, D\n"
    "// parrafo(array $texto = [], string $atributos = '') -> <p ...>linea1<br>linea2<br></p>\n"
    "// estructura(string $nombre = 'default', bool $barra_diagonal = INI)\n"
    "//   Tags validos: header, footer, nav, main, section, article, aside, div, !DOCTYPE, html, head, meta, body, title, style, span, pre, code\n"
    "// meta(string $atributos = 'name=\"viewport\" content=\"width=device-width, initial-scale=1.0\"')\n"
    "// enlace(array $enlaces = [], string $modo = 'default') -> asociativo ['Texto' => 'https://...'], modo 'string' o array\n"
    "// lista(array $items = [], string $tipo = '') -> $tipo='ordenada' (<ol>) o '' (<ul>)\n\n"
    "// 3. FUNCIONES DE COMPONENTES UI Y CODIGO\n"
    "// bloque_codigo(mixed $contenido = 'default') -> <pre> escapado para codigo o print_r de arrays\n"
    "// etiqueta_ui(string $texto = 'default', string $clase = '') -> <span class=\"...\">texto</span>\n"
    "// estilo_css(string $reglas = 'default') -> <style>reglas</style>\n\n"
    "// 4. FUNCIONES FRAGMENTADAS DE OLLAMA\n"
    "// ollama_payload(array $prompt = [], string $modelo = MOD_QWEN): array -> prepara endpoint (/api/chat o /api/generate) y payload\n"
    "// ollama_peticion(array $datosPreparados = [], string $host = OLLAMA_HOST): array -> ejecuta cURL a Ollama\n"
    "// ollama_procesar(array $respuesta = [], string $modo = RES_TEXTO): mixed -> filtra segun RES_TEXTO, RES_ESTADO o RES_ARRAY\n"
    "// ollama_test(string $titulo = 'default', array $prompt = [], string $modelo = MOD_QWEN): array -> ejecuta ciclo completo con cronometro\n"
)


def cargar_referencia_php(max_chars: int = MAX_REF_PHP) -> Tuple[str, Optional[Path]]:
    candidatas: List[Path] = []
    if os.getenv("ARYI_PHP_API"):
        candidatas.append(Path(os.environ["ARYI_PHP_API"]).expanduser())
    candidatas += [
        WORKSPACE_ROOT / "v2.php",
        WORKSPACE_ROOT / "funciones.php",
        WORKSPACE_ROOT / "web/api/html.php",
        PYTHON_DIR / "v2.php",
        Path("v2.php"),
        Path("funciones.php"),
    ]
    for ruta in candidatas:
        try:
            if ruta.is_file():
                contenido = ruta.read_text(encoding="utf-8", errors="replace")
                if len(contenido) > max_chars:
                    contenido = contenido[:max_chars] + "\n/* [REFERENCIA TRUNCADA POR LIMITE DE CONTEXTO] */"
                return contenido, ruta
        except OSError:
            continue
    return V2_PHP_FALLBACK_REF[:max_chars], None


LECCIONES_TUTORIAL_V2: List[Dict[str, str]] = [
    {
        "titulo": "Modulo 1: Filosofia Declarativa, Constantes y Estructura HTML",
        "explicacion": (
            "En el framework v2.php (HtmlFrameWork) NUNCA se escriben etiquetas HTML crudas como <div> o <h1>.\n"
            "Todo documento se construye llamando a funciones PHP e imprimiendolas con <?= ... ?>.\n\n"
            "* estructura($nombre, $cierre):\n"
            "  - Usa la constante INI (o dejalo vacio) para abrir una etiqueta.\n"
            "  - Usa la constante FIN para cerrarla.\n"
            "  - Soporta atributos separados por el primer espacio: estructura('div class=\"contenedor\"').\n"
            "  - Etiquetas validas: !DOCTYPE, html, head, meta, body, title, style, header, footer,\n"
            "    nav, main, section, article, aside, div, span, pre, code.\n"
            "* meta($atributos): Genera etiquetas <meta>. Sin parametros inserta el viewport responsive."
        ),
        "ejemplo": (
            "<?php require_once 'v2.php'; ?>\n"
            "<?= estructura('!DOCTYPE html'); ?>\n"
            "<?= estructura('html lang=\"es\"'); ?>\n"
            "    <?= estructura('head'); ?>\n"
            "        <?= meta('charset=\"UTF-8\"'); ?>\n"
            "        <?= meta(); ?>\n"
            "        <?= estructura('title'); ?>Mi App<?= estructura('title', FIN); ?>\n"
            "    <?= estructura('head', FIN); ?>\n"
            "    <?= estructura('body'); ?>\n"
            "        <?= estructura('div class=\"caja\"'); ?>\n"
            "            Contenido aqui\n"
            "        <?= estructura('div', FIN); ?>\n"
            "    <?= estructura('body', FIN); ?>\n"
            "<?= estructura('html', FIN); ?>"
        ),
        "reto": "Escribe en una linea como abririas y cerrarias una etiqueta <main class=\"panel\"> usando estructura().",
        "pista": "Recuerda pasar 'main class=\"panel\"' al abrir y 'main', FIN al cerrar.",
    },
    {
        "titulo": "Modulo 2: Tipografia, Parrafos, Listas y Enlaces",
        "explicacion": (
            "Para insertar contenido textual seguro (con htmlspecialchars automatico):\n\n"
            "1. encabezado($texto, $tamano):\n"
            "   Usa las constantes de tamano:\n"
            "   - P (h1 - principal)   | S (h2 - secundario) | M (h3 - mediano)\n"
            "   - MI (h4 - minusculo)  | MIN (h5 - miniatura) | D (h6 - diminuto)\n\n"
            "2. parrafo(array $lineas, string $atributos = ''):\n"
            "   Recibe un array indexado de lineas y las une con <br> dentro de <p>.\n\n"
            "3. lista(array $items, string $tipo = ''):\n"
            "   Si $tipo === 'ordenada' genera <ol>, de lo contrario genera <ul>.\n\n"
            "4. enlace(array $enlaces, string $modo = 'default'):\n"
            "   Recibe un array asociativo ['Nombre' => 'https://...']. Usa 'string' en $modo para concatenarlos."
        ),
        "ejemplo": (
            "<?= encabezado('Panel de Control', P); ?>\n"
            "<?= encabezado('Metricas del Servidor', S); ?>\n"
            "<?= parrafo(['Linea 1 del reporte.', 'Linea 2 del reporte.'], 'class=\"subtitulo\"'); ?>\n"
            "<?= lista(['CPU: OK', 'RAM: OK', 'Tailscale: Activo'], 'ordenada'); ?>\n"
            "<?= enlace(['Ir a Ollama' => 'http://100.115.1.71:11434'], 'string'); ?>"
        ),
        "reto": "Como generarias un encabezado <h2> que diga 'Resultados' y un parrafo con clase 'info' usando v2.php?",
        "pista": "Usa encabezado('Resultados', S) y parrafo(['tu texto'], 'class=\"info\"').",
    },
    {
        "titulo": "Modulo 3: Componentes de Interfaz y Codigo (UI Helpers)",
        "explicacion": (
            "v2.php incorpora 3 funciones especializadas para interfaces modernas y depuracion:\n\n"
            "* estilo_css(string $reglas):\n"
            "  Envuelve tus reglas CSS dentro de <style>...</style> en el <head>.\n"
            "* etiqueta_ui(string $texto, string $clase = ''):\n"
            "  Genera un <span class=\"...\"> escapado. Ideal para badges de estado (PASS, OK, 0.45 s).\n"
            "* bloque_codigo(mixed $contenido):\n"
            "  Si le pasas un string (como HTML devuelto por la IA) o un array, lo convierte automaticamente\n"
            "  con print_r y htmlspecialchars dentro de <pre>...</pre>."
        ),
        "ejemplo": (
            "<?= estilo_css('.badge-ok { background: #dcfce7; color: #166534; padding: 4px 8px; }'); ?>\n"
            "<?= etiqueta_ui('Conexion: OK', 'badge-ok'); ?>\n"
            "<?= bloque_codigo(['modelo' => MOD_QWEN, 'estado' => 'activo']); ?>"
        ),
        "reto": "Muestra como imprimirias un array $respuesta dentro de una etiqueta <pre> y un badge de error usando las funciones de v2.php.",
        "pista": "Usa bloque_codigo($respuesta) y etiqueta_ui('ERROR', 'badge-error').",
    },
    {
        "titulo": "Modulo 4: Pipeline Fragmentado de Comunicacion con Ollama",
        "explicacion": (
            "En v2.php, la antigua clase monolitica p_plmht se fragmento en 4 funciones puras:\n\n"
            "1. ollama_payload(array $prompt, string $modelo = MOD_QWEN): array\n"
            "   Detecta automaticamente si $prompt tiene la clave 'messages' (usa /api/chat) o si es un\n"
            "   prompt directo/array de lineas (usa /api/generate).\n\n"
            "2. ollama_peticion(array $datosPreparados, string $host = OLLAMA_HOST): array\n"
            "   Ejecuta la llamada cURL a http://100.115.1.71:11434 y decodifica el JSON.\n\n"
            "3. ollama_procesar(array $respuesta, string $modo = RES_TEXTO): mixed\n"
            "   - Con RES_TEXTO: devuelve unicamente el texto generado por el modelo.\n"
            "   - Con RES_ESTADO: devuelve ['es_array' => bool, 'conexion_ok' => bool, 'error_msg' => ...].\n"
            "   - Con RES_ARRAY: devuelve la respuesta cruda completa.\n\n"
            "4. ollama_test(string $titulo, array $prompt, string $modelo = MOD_QWEN): array\n"
            "   Ejecuta los 3 pasos anteriores midiendo el tiempo en segundos (duracion_seg)."
        ),
        "ejemplo": (
            "<?php\n"
            "// Uso paso a paso:\n"
            "$prep = ollama_payload(['prompt' => 'Genera un h1 Hola Mundo'], MOD_QWEN);\n"
            "$raw  = ollama_peticion($prep, OLLAMA_HOST);\n"
            "$txt  = ollama_procesar($raw, RES_TEXTO);\n\n"
            "// O en un solo paso con cronometro:\n"
            "$test = ollama_test('Prueba Rapida', ['Crea un boton HTML5'], MOD_LFM);\n"
            "echo bloque_codigo($test['texto_generado']);"
        ),
        "reto": "Escribe las 3 lineas de codigo PHP para enviar un chat con 'messages' al modelo MOD_LFM y obtener solo el texto de respuesta.",
        "pista": "Llama a ollama_payload(['messages' => ...], MOD_LFM), luego ollama_peticion() y finalmente ollama_procesar(..., RES_TEXTO).",
    },
    {
        "titulo": "Modulo 5: Integracion Completa (Vista HTML + Ollama en v2.php)",
        "explicacion": (
            "Cuando combinas las funciones de Ollama con las funciones de renderizado HTML de v2.php,\n"
            "obtienes aplicaciones completas sin una sola etiqueta HTML suelta.\n"
            "En este ultimo paso puedes pedirle al tutorial que genere un archivo demo_tutorial_v2.php\n"
            "en tu workspace o practicar con el evaluador de IA."
        ),
        "ejemplo": (
            "<?php\n"
            "require_once 'v2.php';\n"
            "$res = ollama_test('Test UI', ['prompt' => 'Dame un consejo de Linux'], MOD_QWEN);\n"
            "?>\n"
            "<?= estructura('!DOCTYPE html'); ?>\n"
            "<?= estructura('html lang=\"es\"'); ?>\n"
            "<?= estructura('body'); ?>\n"
            "    <?= encabezado($res['titulo'], P); ?>\n"
            "    <?= etiqueta_ui($res['duracion_seg'] . ' s', 'badge'); ?>\n"
            "    <?= bloque_codigo($res['texto_generado']); ?>\n"
            "<?= estructura('body', FIN); ?>\n"
            "<?= estructura('html', FIN); ?>"
        ),
        "reto": "Escribe un pequeno fragmento que combine encabezado(), ollama_test() y bloque_codigo().",
        "pista": "Guarda el retorno de ollama_test() en $r y pasale $r['texto_generado'] a bloque_codigo().",
    },
]


def ejecutar_tutorial_interactivo(api_base: str, modelo_actual: str) -> None:
    """Guia interactiva paso a paso por consola sobre el framework v2.php."""
    print("\n" + "=" * 68)
    print(" TUTORIAL INTERACTIVO - FRAMEWORK PHP + OLLAMA (v2.php)")
    print("=" * 68)
    print("Aprende a dominar las constantes y funciones declarativas de v2.php.")
    print("Comandos dentro del tutorial: [Enter] Siguiente | [p] Pista | [g] Generar demo | [q] Salir\n")

    for idx, leccion in enumerate(LECCIONES_TUTORIAL_V2, start=1):
        print("\n" + "-" * 68)
        print(f"[{idx}/{len(LECCIONES_TUTORIAL_V2)}] {leccion['titulo']}")
        print("-" * 68)
        print(leccion["explicacion"])
        print("\nEJEMPLO DE CODIGO:")
        print("+" + "-" * 66)
        for line in leccion["ejemplo"].splitlines():
            print("| " + line)
        print("+" + "-" * 66)
        print(f"\nMICRO-RETO: {leccion['reto']}")

        while True:
            try:
                resp = input(
                    "\nEscribe tu codigo PHP para que la IA lo revise, [p] pista, [g] crear demo, o [Enter] para avanzar:\n> "
                ).strip()
            except (EOFError, KeyboardInterrupt):
                print("\n[TUTORIAL] Saliendo del tutorial.")
                return

            if not resp:
                break
            if resp.lower() in {"q", "salir", "exit"}:
                print("[TUTORIAL] Tutorial finalizado.")
                return
            if resp.lower() == "p":
                print(f"PISTA: {leccion['pista']}")
                continue
            if resp.lower() == "g":
                ruta_demo = WORKSPACE_ROOT / "demo_tutorial_v2.php"
                codigo_demo = leccion["ejemplo"] + "\n"
                if confirmar(f"Guardar ejemplo practico en {ruta_demo}?"):
                    escribir_archivo_atomico(ruta_demo, codigo_demo)
                    print(f"[EXITO] Plantilla guardada en: {ruta_demo}")
                continue

            modelo_eval, ctx_eval = confirmar_o_cambiar_modelo_pre_peticion(api_base, modelo_actual)
            modelo_actual = modelo_eval
            prompt_eval = [
                {
                    "role": "system",
                    "content": (
                        "Eres el instructor oficial del framework v2.php de Syntax Sanctuary.\n"
                        "Evalua brevemente (maximo 6 lineas) si la respuesta del alumno cumple el reto "
                        "usando unicamente las funciones de v2.php (sin HTML crudo).\n\n"
                        f"Referencia v2.php:\n{V2_PHP_FALLBACK_REF}"
                    ),
                },
                {
                    "role": "user",
                    "content": f"Reto: {leccion['reto']}\nRespuesta del alumno:\n{resp}",
                },
            ]
            print("\n[INSTRUCTOR IA]:\n", end="", flush=True)
            try:
                solicitar_a_ollama_stream(api_base, modelo_eval, prompt_eval, ctx_eval)
            except Exception as e:
                print(f"\n[AVISO] No se pudo conectar a Ollama para evaluar ({e}).")
                print(f"Solucion sugerida: {leccion['pista']}")
            break

    print("\nFelicidades! Has completado los 5 modulos del tutorial de v2.php.")


def obtener_resumen_tutorial_telegram() -> str:
    partes = ["TUTORIAL RAPIDO DEL FRAMEWORK v2.php\n"]
    for idx, lec in enumerate(LECCIONES_TUTORIAL_V2, start=1):
        partes.append(
            f"{idx}. {lec['titulo']}\n{lec['explicacion']}\n\n"
            f"Ejemplo:\n{BT}php\n{lec['ejemplo']}\n{BT}\n"
        )
    return "\n".join(partes)


# =============================================================================
# 5. SYSTEM PROMPT CON NAVEGADOR WEB Y MODO ESTRICTO v2.php
# =============================================================================
INSTRUCCIONES_BASE = (
    "ERES EL ORQUESTADOR MAESTRO AUTONOMO DE SYNTAX SANCTUARY (v8.1).\n"
    "Tienes acceso al sistema operativo y a un NAVEGADOR WEB integrado mediante etiquetas de accion.\n"
    "El operador autorizara las escrituras y comandos delicados. No inventes resultados antes de recibirlos.\n\n"
    "HERRAMIENTAS DISPONIBLES (cada etiqueta de apertura debe ir al inicio de una linea):\n\n"
    "1) Crear o actualizar un archivo:\n"
    '<file path="ruta/del/archivo.ext">\n'
    "contenido integro del archivo\n"
    "</file>\n\n"
    "2) Ejecutar comando Bash sincrono:\n"
    "<bash>\n"
    "comando de shell\n"
    "</bash>\n\n"
    "3) Lanzar servicio en segundo plano:\n"
    "<bash_bg>\n"
    "comando de servidor o demonio\n"
    "</bash_bg>\n\n"
    "4) Buscar en Internet con el navegador integrado (DuckDuckGo):\n"
    "<web_search>\n"
    "consulta precisa de busqueda\n"
    "</web_search>\n\n"
    "5) Abrir y leer el contenido completo + enlaces de una pagina web:\n"
    '<web_open url="https://ejemplo.com/documentacion">\n'
    "</web_open>\n\n"
    f"FORMATO MARKDOWN EQUIVALENTE (si el archivo contiene cierres XML):\n"
    f'{BT}file path="ruta/del/archivo.ext"\n'
    f"...\n"
    f"{BT}\n"
    f"{BT}bash\n"
    f"...\n"
    f"{BT}\n"
    f"{BT}web_search\n"
    f"consulta de busqueda\n"
    f"{BT}\n"
    f'{BT}web_open url="https://ejemplo.com"\n'
    f"{BT}\n\n"
    "REGLAS CRITICAS:\n"
    "- Una sola accion por bloque. Nunca pongas bloques de accion como mero ejemplo decorativo.\n"
    "- Cuando necesites informacion actualizada de Internet, documentacion o resolver dudas externas,\n"
    '  emite primero <web_search> o <web_open url="..."/> y espera el resultado del sistema.\n'
    "- Workspace permitido: {WORKSPACE}\n"
    "- {ENTORNO}\n"
)


def generar_system_prompt(modo: str = "estricto", limite_tokens: int = CONTEXTO_POR_DEFECTO) -> str:
    base = INSTRUCCIONES_BASE.replace("{WORKSPACE}", str(WORKSPACE_ROOT)).replace("{ENTORNO}", describir_entorno())

    if modo == "libre":
        return base + "\nMODO ACTUAL: LIBRE. Puedes usar cualquier framework o lenguaje.\n"

    presupuesto = max(2_500, min(MAX_REF_PHP, int(limite_tokens * 3.5 * 0.28)))
    referencia, ruta_ref = cargar_referencia_php(presupuesto)
    origen = str(ruta_ref) if ruta_ref else "v2.php (referencia integrada)"
    return (
        base
        + f"\nMODO ACTUAL: ESTRICTO (FRAMEWORK PHP v2.php cargado desde {origen}).\n"
        + "Cuando escribas vistas o conectores en PHP, utiliza EXCLUSIVAMENTE las constantes y funciones "
        + "definidas en v2.php. NUNCA escribas etiquetas HTML crudas.\n\n"
        + "<api_reference_v2_php>\n"
        + referencia
        + "\n</api_reference_v2_php>\n\n"
        + "Reglas del Framework v2.php:\n"
        + "1. Usa estructura('tag atributos', INI/FIN) para todas las etiquetas estructurales.\n"
        + "2. Usa encabezado($texto, P|S|M|MI|MIN|D), parrafo($array, $attr), lista($items, $tipo) y enlace($assoc, 'string').\n"
        + "3. Usa estilo_css($css), etiqueta_ui($texto, $clase) y bloque_codigo($contenido).\n"
        + "4. Para comunicarte con Ollama en PHP usa las funciones fragmentadas: "
        + "ollama_payload(), ollama_peticion(), ollama_procesar() y ollama_test().\n"
    )


# =============================================================================
# 6. PARSER HIBRIDO XML + MARKDOWN (INCLUYE <web_search> Y <web_open>)
# =============================================================================
@dataclass
class Accion:
    tipo: str
    valor: str
    contenido: str = ""
    inicio: int = 0
    fin: int = 0
    fuente: str = "XML"


@dataclass
class ResultadoParseo:
    acciones: List[Accion]
    avisos: List[str]


@dataclass
class _Fence:
    inicio: int
    fin: int
    info: str
    cuerpo_ini: int
    cuerpo_fin: int


XML_ACCION_RE = re.compile(
    r"^[ \t]*<(?P<tag>file|bash_bg|bash|web_search|web_open)\b(?P<attrs>[^>\n]*?)(?:>(?P<body>.*?)</(?P=tag)\s*>|/\s*>)",
    re.IGNORECASE | re.DOTALL | re.MULTILINE,
)
XML_APERTURA_RE = re.compile(
    r"^[ \t]*<(?P<tag>file|bash_bg|bash|web_search|web_open)\b[^>\n]*>",
    re.IGNORECASE | re.MULTILINE,
)
FENCE_ABRE_RE = re.compile(r"^[ \t]*(?P<fence>`{3,}|~{3,})[ \t]*(?P<info>[^`\r\n]*)$")
FENCE_CIERRA_RE = re.compile(r"^[ \t]*(?P<fence>`{3,}|~{3,})[ \t]*$")
ATTR_RUTA_RE = re.compile(
    r'(?:^|\s)(?:path|ruta|archivo|file|url|href|query|q)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s/>]+))',
    re.IGNORECASE,
)


def extraer_attr_valor(attrs: str) -> str:
    m = ATTR_RUTA_RE.search(attrs or "")
    if not m:
        return ""
    return next((g for g in m.groups() if g is not None), "").strip()


def _enmascarar(texto: str, spans: List[Tuple[int, int]]) -> str:
    if not spans:
        return texto
    caracteres = list(texto)
    for ini, fin in spans:
        for i in range(ini, fin):
            if caracteres[i] != "\n":
                caracteres[i] = " "
    return "".join(caracteres)


def _escanear_fences(texto: str) -> Tuple[List[_Fence], Optional[Tuple[int, str]]]:
    fences: List[_Fence] = []
    abierta: Optional[Tuple[str, int, int, str, int]] = None
    pos = 0
    for linea in texto.split("\n"):
        limpia = linea.rstrip("\r")
        if abierta is None:
            m = FENCE_ABRE_RE.match(limpia)
            if m:
                f = m.group("fence")
                abierta = (f[0], len(f), pos, m.group("info").strip(), pos + len(linea) + 1)
        else:
            m = FENCE_CIERRA_RE.match(limpia)
            if m and m.group("fence")[0] == abierta[0] and len(m.group("fence")) >= abierta[1]:
                fences.append(_Fence(abierta[2], pos + len(limpia), abierta[3], abierta[4], pos))
                abierta = None
        pos += len(linea) + 1
    return fences, ((abierta[2], abierta[3]) if abierta else None)


def _clasificar_fence(info: str) -> Tuple[Optional[str], str, Optional[str]]:
    texto = (info or "").strip()
    if not texto:
        return None, "", None
    explicito = False
    m = re.match(r"(?i)^action\s*:\s*(.*)$", texto)
    if m:
        explicito, texto = True, m.group(1).strip()
    partes = texto.split(None, 1)
    if not partes:
        return None, "", "Fence action: sin tipo; se ignoro."
    lang = partes[0].lower().replace("-", "_")
    resto = partes[1] if len(partes) > 1 else ""
    if lang in FILE_LANGS:
        ruta = extraer_attr_valor(resto) or resto.strip().strip("\"'")
        return "file", ruta, None
    if lang in BASH_LANGS:
        return "bash", "", None
    if lang in BG_LANGS:
        return "bash_bg", "", None
    if lang in SEARCH_LANGS:
        q = extraer_attr_valor(resto) or resto.strip().strip("\"'")
        return "web_search", q, None
    if lang in OPEN_LANGS:
        u = extraer_attr_valor(resto) or resto.strip().strip("\"'")
        return "web_open", u, None
    if explicito:
        return None, "", f"Fence action:{lang} desconocida; se ignoro."
    return None, "", None


def _es_envoltorio_xml(info: str) -> bool:
    partes = (info or "").strip().lower().split(None, 1)
    return bool(partes) and partes[0] in {"xml", "actions", "acciones"}


def _normalizar_cuerpo(cuerpo: str) -> str:
    cuerpo = (cuerpo or "").replace("\r\n", "\n")
    cuerpo = re.sub(r"\A[ \t]*\n", "", cuerpo, count=1)
    cuerpo = re.sub(r"\n[ \t]*\Z", "", cuerpo, count=1)
    return cuerpo


def _quitar_fence_envolvente(texto: str) -> str:
    lineas = texto.split("\n")
    i, j = 0, len(lineas) - 1
    while i <= j and not lineas[i].strip():
        i += 1
    while j >= i and not lineas[j].strip():
        j -= 1
    if j <= i:
        return texto
    a, c = FENCE_ABRE_RE.match(lineas[i]), FENCE_CIERRA_RE.match(lineas[j])
    if a and c and a.group("fence")[0] == c.group("fence")[0] and len(c.group("fence")) >= len(a.group("fence")):
        return "\n".join(lineas[i + 1 : j])
    return texto


def _preparar_contenido_xml(ruta: str, cuerpo: str) -> str:
    contenido = _normalizar_cuerpo(cuerpo)
    if not ruta.lower().endswith((".md", ".markdown", ".mdx")):
        contenido = _quitar_fence_envolvente(contenido)
    return contenido


def preparar_comando(comando: str) -> str:
    comando = _quitar_fence_envolvente(_normalizar_cuerpo(comando)).strip()
    lineas = [l for l in comando.split("\n") if l.strip()]
    if lineas and all(re.match(r"^[ \t]*\$[ \t]+", l) for l in lineas):
        comando = re.sub(r"^[ \t]*\$[ \t]+", "", comando, flags=re.MULTILINE)
    return comando.strip()


def parsear_acciones(texto: str) -> ResultadoParseo:
    avisos: List[str] = []
    xml_matches = list(XML_ACCION_RE.finditer(texto))
    spans_xml = [m.span() for m in xml_matches]
    fences, fence_abierta = _escanear_fences(_enmascarar(texto, spans_xml))

    candidatos: List[Accion] = []
    opacos: List[Tuple[int, int]] = []

    for f in fences:
        tipo, meta_val, aviso = _clasificar_fence(f.info)
        if aviso:
            avisos.append(aviso)
        if tipo is None:
            if not _es_envoltorio_xml(f.info):
                opacos.append((f.inicio, f.fin))
            continue
        cuerpo = texto[f.cuerpo_ini : f.cuerpo_fin].replace("\r\n", "\n")
        if cuerpo.endswith("\n"):
            cuerpo = cuerpo[:-1]

        if tipo == "file":
            if not meta_val:
                avisos.append(f'Fence de archivo ignorada: usa {BT}file path="ruta".')
                continue
            candidatos.append(Accion("file", meta_val, cuerpo, f.inicio, f.fin, "Markdown"))
        elif tipo in {"web_search", "web_open"}:
            objetivo = meta_val or preparar_comando(cuerpo)
            if not objetivo:
                avisos.append(f"Fence {tipo} sin consulta/URL; se ignoro.")
                continue
            candidatos.append(Accion(tipo, objetivo, "", f.inicio, f.fin, "Markdown"))
        else:
            comando = preparar_comando(cuerpo)
            if not comando:
                avisos.append(f"Fence {tipo} vacia; se ignoro.")
                continue
            candidatos.append(Accion(tipo, comando, "", f.inicio, f.fin, "Markdown"))

    for m in xml_matches:
        if any(ini <= m.start() < fin for ini, fin in opacos):
            continue
        tag = m.group("tag").lower()
        attrs = m.group("attrs") or ""
        body = m.group("body") or ""

        if tag == "file":
            ruta = extraer_attr_valor(attrs)
            if not ruta:
                avisos.append("Bloque <file> ignorado: falta el atributo path.")
                continue
            candidatos.append(Accion("file", ruta, _preparar_contenido_xml(ruta, body), m.start(), m.end(), "XML"))
        elif tag in {"web_search", "web_open"}:
            objetivo = extraer_attr_valor(attrs) or preparar_comando(body)
            if not objetivo:
                avisos.append(f"Bloque <{tag}> vacio; falta consulta o URL.")
                continue
            candidatos.append(Accion(tag, objetivo, "", m.start(), m.end(), "XML"))
        else:
            comando = preparar_comando(body)
            if not comando:
                avisos.append(f"Bloque <{tag}> vacio; se ignoro.")
                continue
            candidatos.append(Accion(tag, comando, "", m.start(), m.end(), "XML"))

    candidatos.sort(key=lambda a: (a.inicio, -(a.fin - a.inicio)))
    acciones: List[Accion] = []
    ultimo_fin = -1
    for a in candidatos:
        if a.inicio >= ultimo_fin:
            acciones.append(a)
            ultimo_fin = a.fin

    cubiertos = spans_xml + [(f.inicio, f.fin) for f in fences]
    for m in XML_APERTURA_RE.finditer(texto):
        if not any(ini <= m.start() < fin for ini, fin in cubiertos):
            avisos.append(f"Etiqueta <{m.group('tag').lower()}> sin cierre valido; no se ejecuto ese bloque.")
    if fence_abierta and _clasificar_fence(fence_abierta[1])[0]:
        avisos.append("Bloque Markdown de accion sin cierre; no se ejecuto ese bloque.")

    return ResultadoParseo(acciones, avisos)


# =============================================================================
# 7. SEGURIDAD, ARCHIVOS ATOMICOS, BASH Y PROCESOS DE FONDO
# =============================================================================
def ruta_permitida(ruta_bruta: str) -> Path:
    limpia = (ruta_bruta or "").strip().strip("\"'")
    if not limpia or "\x00" in limpia:
        raise ValueError("Ruta vacia o invalida.")
    candidata = Path(limpia).expanduser()
    if not candidata.is_absolute():
        candidata = WORKSPACE_ROOT / candidata
    candidata = candidata.resolve(strict=False)
    for raiz in RAICES_PERMITIDAS:
        try:
            candidata.relative_to(raiz)
            return candidata
        except ValueError:
            continue
    permitidas = ", ".join(str(r) for r in RAICES_PERMITIDAS)
    raise PermissionError(f"Ruta fuera de las raices permitidas ({permitidas}): {candidata}")


def confirmar(pregunta: str) -> bool:
    try:
        respuesta = input(f"{pregunta}\nAutorizar? [s/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n[ORQUESTADOR] Accion cancelada.")
        return False
    return respuesta in {"s", "si", "y", "yes"}


PATRONES_PELIGROSOS: List[Tuple[str, "re.Pattern[str]"]] = [
    (nombre, re.compile(patron, re.IGNORECASE))
    for nombre, patron in [
        ("borrado recursivo (rm -r)", r"\brm\s+(?:[^\n;&|]*\s)?(?:-[a-zA-Z]*[rR][a-zA-Z]*|--recursive)(?:\s|$)"),
        ("formateo o particionado de discos", r"\b(?:mkfs(?:\.[\w-]+)?|fdisk|sfdisk|parted|wipefs)\b"),
        ("escritura directa sobre dispositivos", r"\bdd\b[^\n]*\bof\s*=\s*/dev/|>\s*/dev/(?:sd|nvme|hd|vd|mmcblk)"),
        ("apagado o reinicio del sistema", r"\b(?:shutdown|reboot|poweroff|halt)\b|\binit\s+[06]\b"),
        ("fork bomb", r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:"),
        ("cambio recursivo de permisos/propietario", r"\b(?:chmod|chown|chgrp)\s+(?:[^\n;&|]*\s)?-[a-zA-Z]*R[a-zA-Z]*\b"),
        ("descarga y ejecucion remota (curl | sh)", r"\b(?:curl|wget)\b[^\n|]*\|\s*(?:sudo\s+)?(?:ba|z|da)?sh\b"),
        ("elevacion de privilegios", r"(?:^|[\n;&|(])\s*(?:sudo|doas)\b"),
        ("escritura en directorios del sistema", r">\s*/(?:etc|boot|usr|bin|sbin|lib|lib64|sys|proc)\b"),
        ("terminacion masiva de procesos", r"\b(?:killall|pkill)\b|\bkill\s+(?:-\w+\s+)?-1\b"),
        ("operacion git destructiva", r"\bgit\s+(?:reset\s+--hard|clean\s+-[a-zA-Z]*f|push\s+(?:[^\n;&|]*\s)?(?:--force\b|-f\b))"),
        ("SQL destructivo", r"\b(?:drop\s+(?:database|table|schema)|truncate\s+table)\b"),
        ("limpieza destructiva de Docker", r"\bdocker\s+(?:system|volume|image|container)\s+prune\b|\bdocker\s+rm\s+-f"),
    ]
]


def detectar_peligros(comando: str) -> List[str]:
    return [nombre for nombre, patron in PATRONES_PELIGROSOS if patron.search(comando)]


def autorizar_comando(comando: str, pregunta: str) -> bool:
    peligros = detectar_peligros(comando)
    if peligros:
        print("\n[ALERTA] Posible operacion destructiva detectada: " + "; ".join(peligros))
    if not confirmar(pregunta):
        return False
    if peligros:
        try:
            segunda = input("Para autorizar esta operacion escribe exactamente PELIGRO: ").strip()
        except (EOFError, KeyboardInterrupt):
            segunda = ""
        if segunda != "PELIGRO":
            print("[ORQUESTADOR] Operacion destructiva cancelada.")
            return False
    return True


def _carpeta_logs() -> Path:
    carpeta = WORKSPACE_ROOT / ".aryi_logs"
    carpeta.mkdir(parents=True, exist_ok=True)
    return ruta_permitida(str(carpeta))


def auditar(evento: str, detalle: str, resultado: str) -> None:
    try:
        registro = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "evento": evento,
            "detalle": detalle[:500],
            "resultado": resultado,
        }
        with open(_carpeta_logs() / "auditoria.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
    except Exception:
        pass


def escribir_archivo_atomico(ruta: Path, contenido: str) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta = ruta_permitida(str(ruta))
    modo = stat.S_IMODE(ruta.stat().st_mode) if ruta.exists() else (0o666 & ~_UMASK)
    fd, temporal = tempfile.mkstemp(prefix=".aryi_tmp_", dir=str(ruta.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as archivo:
            archivo.write(contenido)
            if contenido and not contenido.endswith("\n"):
                archivo.write("\n")
            archivo.flush()
            os.fsync(archivo.fileno())
        os.chmod(temporal, modo)
        os.replace(temporal, ruta)
    except BaseException:
        try:
            os.unlink(temporal)
        except OSError:
            pass
        raise


def _exigir_posix() -> None:
    if os.name != "posix":
        raise RuntimeError("La ejecucion de Bash requiere Linux/Unix o un contenedor Linux.")


def _shell() -> str:
    return shutil.which("bash") or "/bin/sh"


def _terminar_grupo(proc: "subprocess.Popen[Any]", senal: int = signal.SIGKILL) -> None:
    try:
        os.killpg(proc.pid, senal)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.kill()
        except Exception:
            pass


def ejecutar_bash(comando: str) -> Tuple[int, str, str]:
    _exigir_posix()
    proc = subprocess.Popen(
        comando,
        shell=True,
        executable=_shell(),
        cwd=str(WORKSPACE_ROOT),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        start_new_session=True,
    )
    estado = "ok"
    try:
        salida, _ = proc.communicate(timeout=TIMEOUT_BASH)
    except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
        estado = "timeout" if isinstance(exc, subprocess.TimeoutExpired) else "interrumpido"
        _terminar_grupo(proc)
        try:
            salida, _ = proc.communicate(timeout=5)
        except Exception:
            salida = ""
    return proc.returncode if proc.returncode is not None else -1, (salida or "").strip() or "(sin salida)", estado


@dataclass
class ProcesoFondo:
    pid: int
    comando: str
    log: Path
    popen: "subprocess.Popen[Any]"
    inicio: float


PROCESOS_FONDO: Dict[int, ProcesoFondo] = {}


def leer_cola(ruta: Path, max_bytes: int = 2_000) -> str:
    try:
        with open(ruta, "rb") as f:
            f.seek(0, os.SEEK_END)
            tam = f.tell()
            f.seek(max(0, tam - max_bytes))
            return f.read().decode("utf-8", "replace").strip()
    except OSError:
        return ""


def iniciar_bash_fondo(comando: str) -> ProcesoFondo:
    _exigir_posix()
    log_path = _carpeta_logs() / f"bg_{time.strftime('%Y%m%d_%H%M%S')}_{time.time_ns()}.log"
    with open(log_path, "ab") as log:
        proc = subprocess.Popen(
            comando,
            shell=True,
            executable=_shell(),
            cwd=str(WORKSPACE_ROOT),
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )
    info = ProcesoFondo(proc.pid, comando, log_path, proc, time.time())
    PROCESOS_FONDO[proc.pid] = info
    return info


def detener_proceso(pid: int) -> str:
    info = PROCESOS_FONDO.get(pid)
    if not info:
        return f"PID {pid} no es un proceso lanzado por este orquestador."
    if info.popen.poll() is not None:
        return f"PID {pid} ya habia terminado (codigo {info.popen.returncode})."
    _terminar_grupo(info.popen, signal.SIGTERM)
    try:
        info.popen.wait(timeout=5)
    except subprocess.TimeoutExpired:
        _terminar_grupo(info.popen, signal.SIGKILL)
    return f"PID {pid} detenido."


def listar_procesos() -> str:
    if not PROCESOS_FONDO:
        return "No hay procesos de fondo lanzados en esta sesion."
    filas = []
    for p in PROCESOS_FONDO.values():
        codigo = p.popen.poll()
        estado = "ACTIVO" if codigo is None else f"terminado ({codigo})"
        filas.append(f"  PID {p.pid:<7} {estado:<16} $ {p.comando[:60]}\n              log: {p.log}")
    return "\n".join(filas)


# =============================================================================
# 8. EJECUTOR DE ACCIONES DEL AGENTE (ARCHIVOS, BASH Y NAVEGADOR WEB)
# =============================================================================
@dataclass
class ResultadoAcciones:
    feedback: str = ""
    hubo_directivas: bool = False
    ejecutadas: int = 0
    rechazadas: int = 0
    errores: int = 0


def _vista_previa(texto: str, lineas: int = 10, ancho: int = 110) -> None:
    filas = texto.split("\n")
    for fila in filas[:lineas]:
        print("   | " + fila[:ancho] + ("..." if len(fila) > ancho else ""))
    if len(filas) > lineas:
        print(f"   | ... (+{len(filas) - lineas} lineas)")


def _accion_archivo(a: Accion, res: ResultadoAcciones) -> str:
    ruta = ruta_permitida(a.valor)
    if ruta.is_dir():
        raise IsADirectoryError(f"La ruta es un directorio: {ruta}")
    print(f"\n[ORQUESTADOR - {a.fuente}] Archivo propuesto: {ruta}")
    print(f"Contenido: {len(a.contenido)} caracteres")
    _vista_previa(a.contenido)
    if ruta.exists():
        print("[AVISO] El archivo ya existe y sera reemplazado si autorizas.")
    if not confirmar(f"Escribir archivo: {ruta}"):
        res.rechazadas += 1
        auditar("file", str(ruta), "rechazado")
        return f"Sistema: escritura rechazada por el operador: {ruta}. No reintentes sin cambiar la propuesta."
    escribir_archivo_atomico(ruta, a.contenido)
    print(f"[EXITO] Archivo guardado: {ruta}")
    res.ejecutadas += 1
    auditar("file", str(ruta), f"escrito ({len(a.contenido)} caracteres)")
    return f"Sistema: archivo guardado: {ruta} ({len(a.contenido)} caracteres)."


def _accion_bash(a: Accion, res: ResultadoAcciones) -> str:
    print(f"\n[ORQUESTADOR - {a.fuente}] Comando Bash propuesto:\n$ {a.valor}")
    if not autorizar_comando(a.valor, f"Se ejecutara con tus permisos, en {WORKSPACE_ROOT}"):
        res.rechazadas += 1
        auditar("bash", a.valor, "rechazado")
        return f"Sistema: comando rechazado por el operador: {recortar(a.valor, 300)}. No lo repitas sin una nueva instruccion."
    print("[Ejecutando...]")
    codigo, salida, estado = ejecutar_bash(a.valor)
    print(f"[RESULTADO Bash - codigo {codigo}]\n{recortar(salida, MAX_SALIDA_CONSOLA)}")
    res.ejecutadas += 1
    auditar("bash", a.valor, f"exit={codigo} estado={estado}")
    nota = {
        "timeout": f" Se agoto el limite de {TIMEOUT_BASH} s y se termino el proceso.",
        "interrumpido": " El operador lo interrumpio con Ctrl+C.",
    }.get(estado, "")
    return f"Sistema: comando terminado (exit={codigo}).{nota}\nComando: {a.valor}\nSalida:\n{recortar(salida)}"


def _accion_bash_bg(a: Accion, res: ResultadoAcciones) -> str:
    print(f"\n[ORQUESTADOR - {a.fuente}] Servicio de fondo propuesto:\n$ {a.valor}")
    if not autorizar_comando(a.valor, "El proceso seguira corriendo despues de que el agente termine"):
        res.rechazadas += 1
        auditar("bash_bg", a.valor, "rechazado")
        return f"Sistema: inicio de proceso rechazado por el operador: {recortar(a.valor, 300)}."
    info = iniciar_bash_fondo(a.valor)
    time.sleep(PAUSA_ARRANQUE_BG)
    codigo = info.popen.poll()
    cola = leer_cola(info.log)
    res.ejecutadas += 1
    if codigo is not None:
        print(f"[FALLO] El proceso termino de inmediato (codigo {codigo}). Log: {info.log}")
        auditar("bash_bg", a.valor, f"murio exit={codigo}")
        return (
            f"Sistema: el servicio se lanzo (PID {info.pid}) pero termino enseguida con codigo {codigo}. "
            f"Log: {info.log}\nUltimas lineas:\n{recortar(cola or '(log vacio)', 1500)}"
        )
    print(f"[INICIADO] PID {info.pid} - log: {info.log}")
    auditar("bash_bg", a.valor, f"pid={info.pid}")
    return (
        f"Sistema: servicio en segundo plano activo. PID={info.pid}. Log: {info.log}."
        + (f"\nSalida inicial:\n{recortar(cola, 1000)}" if cola else "")
    )


def _accion_web_search(a: Accion, res: ResultadoAcciones) -> str:
    print(f"\n[NAVEGADOR IA - {a.fuente}] Busqueda web solicitada por el agente: {a.valor!r}")
    salida = NAVEGADOR.buscar(a.valor, max_results=6)
    print(recortar(salida, MAX_SALIDA_CONSOLA))
    res.ejecutadas += 1
    auditar("web_search", a.valor, f"{len(salida)} chars")
    return f"Sistema (Navegador Web - Busqueda):\n{recortar(salida, MAX_FEEDBACK)}"


def _accion_web_open(a: Accion, res: ResultadoAcciones) -> str:
    print(f"\n[NAVEGADOR IA - {a.fuente}] Lectura de URL solicitada por el agente: {a.valor!r}")
    salida = NAVEGADOR.abrir_url(a.valor, max_chars=MAX_FEEDBACK)
    print(recortar(salida, MAX_SALIDA_CONSOLA))
    res.ejecutadas += 1
    auditar("web_open", a.valor, f"{len(salida)} chars")
    return f"Sistema (Navegador Web - Contenido de pagina):\n{recortar(salida, MAX_FEEDBACK)}"


def procesar_acciones_agente(texto_ia: str) -> ResultadoAcciones:
    parseo = parsear_acciones(texto_ia)
    res = ResultadoAcciones(hubo_directivas=bool(parseo.acciones or parseo.avisos))
    mensajes: List[str] = []

    for aviso in parseo.avisos:
        print(f"\n[AVISO DEL PARSER] {aviso}")
        mensajes.append(f"Parser: {aviso} Reenvia la accion con el formato exacto.")
        res.errores += 1

    manejadores: Dict[str, Callable[[Accion, ResultadoAcciones], str]] = {
        "file":       _accion_archivo,
        "bash":       _accion_bash,
        "bash_bg":    _accion_bash_bg,
        "web_search": _accion_web_search,
        "web_open":   _accion_web_open,
    }
    for accion in parseo.acciones:
        try:
            mensajes.append(manejadores[accion.tipo](accion, res))
        except Exception as exc:
            res.errores += 1
            detalle = f"Sistema: fallo al procesar la accion {accion.tipo} ({recortar(accion.valor, 200)!r}): {type(exc).__name__}: {exc}"
            print(f"\n[ERROR DE ACCION] {detalle}")
            auditar(accion.tipo, accion.valor, f"error {type(exc).__name__}: {exc}")
            mensajes.append(detalle)

    res.feedback = recortar("\n\n".join(mensajes), MAX_FEEDBACK * 2)
    return res


# =============================================================================
# 9. CLIENTE OLLAMA UNIFICADO + SELECTOR DE MODELO ANTES DE CADA PETICION
# =============================================================================
class GeneracionInterrumpida(Exception):
    """El operador corto la generacion con Ctrl+C."""


def listar_modelos_ollama(api_base: str) -> List[str]:
    url = f"{api_base.rstrip('/')}/tags"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            modelos = [m["name"] for m in data.get("models", []) if isinstance(m, dict) and m.get("name")]
            return modelos
    except Exception as exc:
        log_console("OLLAMA_TAGS", f"No se pudieron consultar los modelos en {url}: {exc}")
        return []


def seleccionar_modelo_interactivo(api_base: str, modelo_actual: Optional[str] = None) -> Tuple[Optional[str], int]:
    modelos = listar_modelos_ollama(api_base)
    if not modelos:
        fallback = modelo_actual or DEFAULT_LLM_MODEL
        print(f"[AVISO] Usando modelo por defecto: {fallback}")
        return fallback, obtener_limite_contexto(fallback)

    print("\nModelos disponibles en Ollama:")
    for i, nombre in enumerate(modelos, 1):
        marca = "  <-- [ACTUAL]" if nombre == modelo_actual else ""
        print(f"  [{i}] {nombre}{marca}")

    defecto = modelo_actual if (modelo_actual in modelos) else modelos[0]
    while True:
        try:
            valor = input(f"\nSelecciona el modelo (numero o nombre; Enter = {defecto}): ").strip()
        except (EOFError, KeyboardInterrupt):
            return None, CONTEXTO_POR_DEFECTO
        if not valor:
            elegido = defecto
            break
        if valor.isdigit() and 1 <= int(valor) <= len(modelos):
            elegido = modelos[int(valor) - 1]
            break
        if valor in modelos:
            elegido = valor
            break
        print("Seleccion invalida; escribe uno de los numeros de la lista.")

    limite = obtener_limite_contexto(elegido)
    print(f"[INFO] Modelo activo: {elegido} - contexto: {limite} tokens")
    return elegido, limite


def confirmar_o_cambiar_modelo_pre_peticion(
    api_base: str,
    modelo_actual: str,
    preguntar: bool = True,
) -> Tuple[str, int]:
    """Permite elegir el modelo justo antes de enviar cada peticion a Ollama."""
    if not preguntar or not sys.stdin.isatty():
        return modelo_actual, obtener_limite_contexto(modelo_actual)

    modelos = listar_modelos_ollama(api_base)
    if not modelos:
        return modelo_actual, obtener_limite_contexto(modelo_actual)

    resumen = " | ".join(f"[{i}] {m}" for i, m in enumerate(modelos, 1))
    print("\n+-- Selector de Modelo Pre-Peticion --------------------------------")
    print(f"| Disponibles: {resumen}")
    try:
        eleccion = input(f"+-- Modelo para esta peticion [Enter = mantener '{modelo_actual}' / numero]: ").strip()
    except (EOFError, KeyboardInterrupt):
        return modelo_actual, obtener_limite_contexto(modelo_actual)

    if not eleccion:
        return modelo_actual, obtener_limite_contexto(modelo_actual)
    if eleccion.isdigit() and 1 <= int(eleccion) <= len(modelos):
        nuevo = modelos[int(eleccion) - 1]
        print(f"[MODELO] Cambiado a '{nuevo}' para esta peticion.")
        return nuevo, obtener_limite_contexto(nuevo)
    if eleccion in modelos:
        return eleccion, obtener_limite_contexto(eleccion)

    print(f"[AVISO] Opcion no reconocida; se mantiene '{modelo_actual}'.")
    return modelo_actual, obtener_limite_contexto(modelo_actual)


def free_ollama_vram(api_base: str, model_hint: str = DEFAULT_LLM_MODEL) -> List[str]:
    base = api_base.rstrip("/")
    models_to_unload: List[str] = []
    try:
        with urllib.request.urlopen(f"{base}/ps", timeout=5) as resp:
            ps_data = json.loads(resp.read().decode("utf-8"))
            for m in ps_data.get("models", []):
                if m.get("name"):
                    models_to_unload.append(m["name"])
    except Exception:
        pass

    if model_hint and model_hint not in models_to_unload:
        models_to_unload.append(model_hint)

    for m_name in models_to_unload:
        try:
            payload = json.dumps({"model": m_name, "keep_alive": 0}).encode("utf-8")
            req = urllib.request.Request(
                f"{base}/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as _:
                pass
        except Exception:
            pass
    if models_to_unload:
        log_console("VRAM", f"VRAM liberada (keep_alive: 0) para: {', '.join(models_to_unload)}")
    return models_to_unload


def solicitar_a_ollama_stream(
    api_base: str,
    modelo: str,
    historial: List[Dict[str, str]],
    limite_tokens: int,
    temperature: float = 0.15,
) -> str:
    """Peticion streaming a /api/chat sincronizada con CooperativeGpuTurn."""
    url = f"{api_base.rstrip('/')}/chat"
    payload = {
        "model": modelo,
        "messages": historial,
        "stream": True,
        "options": {"temperature": temperature, "num_ctx": limite_tokens},
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")

    partes: List[str] = []
    recibio_evento = False
    truncada = False
    last_beat = time.time()

    with CooperativeGpuTurn("ollama") as turn:
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_HTTP_READ) as resp:
                for raw_line in resp:
                    now = time.time()
                    if (now - last_beat) >= 2.0:
                        turn.heartbeat()
                        last_beat = now

                    linea = raw_line.decode("utf-8", errors="replace").strip()
                    if not linea:
                        continue
                    recibio_evento = True
                    try:
                        evento = json.loads(linea)
                    except (ValueError, TypeError):
                        continue
                    if evento.get("error"):
                        raise RuntimeError(f"Ollama informo un error: {evento['error']}")
                    fragmento = (evento.get("message") or {}).get("content", "")
                    if fragmento:
                        print(fragmento, end="", flush=True)
                        partes.append(fragmento)
                    if evento.get("done"):
                        truncada = evento.get("done_reason") == "length"
                        break
        except KeyboardInterrupt:
            print("\n[INTERRUMPIDO] Generacion cancelada por el operador.")
            raise GeneracionInterrumpida() from None

    print("\n" + "=" * 60)
    if truncada:
        print("[AVISO] La respuesta se corto por limite de longitud/contexto; los bloques incompletos no se ejecutaran.")
    texto = "".join(partes)
    if not recibio_evento:
        raise RuntimeError("Ollama cerro la respuesta sin enviar eventos.")
    if not texto.strip():
        raise RuntimeError("Ollama no devolvio texto; revisa el modelo y el endpoint /api/chat.")
    return texto


def ai_ollama_generate(
    api_base: str,
    prompt: str,
    model: str = DEFAULT_LLM_MODEL,
    system: str = "",
    temperature: float = 0.25,
    num_ctx: int = 4096,
    task_label: str = "Inferencia LLM",
    notify_telegram: bool = False,
) -> str:
    """Generacion por /api/generate con streaming en consola y latidos opcionales a Telegram."""
    url = f"{api_base.rstrip('/')}/generate"
    log_console("OLLAMA", f"Tarea: {task_label} | Modelo: {model} | Endpoint: {url}")

    with CooperativeGpuTurn("ollama") as turn:
        body_dict: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "keep_alive": "15m",
            "options": {"temperature": temperature, "num_ctx": num_ctx},
        }
        if system:
            body_dict["system"] = system

        data = json.dumps(body_dict, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")

        collected: List[str] = []
        token_count = 0
        t_start = time.time()
        last_beat = t_start
        last_tg_ping = t_start
        first_token_received = False

        try:
            with urllib.request.urlopen(req, timeout=None) as resp:
                for raw_line in resp:
                    now = time.time()
                    if (now - last_beat) >= 2.0:
                        turn.heartbeat()
                        last_beat = now

                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    try:
                        pkt = json.loads(line)
                    except Exception:
                        continue

                    if "error" in pkt:
                        return f"[ERROR_OLLAMA]: {pkt['error']}"

                    if "response" in pkt:
                        tok = pkt["response"]
                        if not first_token_received:
                            first_token_received = True
                            print("   >>> ", end="", flush=True)
                        collected.append(tok)
                        token_count += 1
                        print(tok, end="", flush=True)

                    if notify_telegram and (now - last_tg_ping) >= 60.0:
                        last_tg_ping = now
                        elapsed_s = int(now - t_start)
                        speed = round(token_count / max(1.0, now - t_start), 1)
                        tg_send_text(
                            f"Sigo procesando ({task_label})...\n"
                            f"- Modelo: {model}\n"
                            f"- Tiempo activo: {elapsed_s}s | {token_count} tokens ({speed} tok/s)"
                        )

                    if pkt.get("done"):
                        break

            print("\n", flush=True)
            return "".join(collected).strip()
        except Exception as e:
            print("\n", flush=True)
            log_console("OLLAMA_EXC", f"Excepcion durante generacion: {e}")
            return f"[ERROR_OLLAMA]: {e}"


# =============================================================================
# 10. HISTORIAL DE CONVERSACION Y GESTION DE CONTEXTO
# =============================================================================
def total_tokens(historial: List[Dict[str, str]]) -> int:
    return sum(estimar_tokens(m.get("content", "")) for m in historial)


def agregar_mensaje(historial: List[Dict[str, str]], rol: str, contenido: str) -> None:
    if rol == "user" and len(historial) > 1 and historial[-1]["role"] == "user":
        historial[-1]["content"] += "\n\n" + contenido
    else:
        historial.append({"role": rol, "content": contenido})


def podar_historial(historial: List[Dict[str, str]], limite_tokens: int) -> None:
    objetivo = max(1024, int(limite_tokens * RESERVA_CONTEXTO))

    while len(historial) > 2 and total_tokens(historial) > objetivo:
        historial.pop(1)
        while len(historial) > 2 and historial[1]["role"] == "assistant":
            historial.pop(1)

    if len(historial) >= 2 and total_tokens(historial) > objetivo:
        otros = total_tokens(historial[:-1])
        presupuesto_chars = max(256, objetivo - otros) * 3
        ultimo = historial[-1]
        if len(ultimo["content"]) > presupuesto_chars:
            marcador = "\n[CONTENIDO RECORTADO PARA CABER EN EL CONTEXTO DEL MODELO]\n"
            disponibles = max(0, presupuesto_chars - len(marcador))
            n_ini = int(disponibles * 0.7)
            n_fin = disponibles - n_ini
            ultimo["content"] = ultimo["content"][:n_ini] + marcador + (ultimo["content"][-n_fin:] if n_fin else "")


# =============================================================================
# 11. CLIENTES TELEGRAM, WHISPER STT, TTS, STABLE DIFFUSION Y AUTO-EVOLUCION
# =============================================================================
def ensure_environment() -> None:
    for directory in (PYTHON_DIR, BACKUP_DIR, REPORTS_DIR, TEMP_DIR):
        directory.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(directory, 0o775)
        except Exception:
            pass


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception as e:
            log_console("WARN", f"No se pudo leer agent_state.json, creando nuevo: {e}")
    return {
        "evolution_version": 1,
        "model": DEFAULT_LLM_MODEL,
        "ask_model_each_request": True,
        "last_update_id": 0,
        "analyzed_files": {},
        "evolution_history": [],
        "last_backup_map": {},
        "auto_free_vram": True,
        "created_at": datetime.now().isoformat(),
    }


def save_state(state: dict) -> None:
    ensure_environment()
    tmp_path = STATE_FILE.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(STATE_FILE)


def compute_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def is_probably_binary(file_path: Path) -> bool:
    if file_path.suffix.lower() in BINARY_EXTENSIONS:
        return True
    try:
        with file_path.open("rb") as f:
            sample = f.read(4096)
        if b"\x00" in sample:
            return True
    except Exception:
        return True
    return False


def create_backup(target_path: Path, state: dict) -> Path:
    ensure_environment()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    try:
        rel_str = str(target_path.relative_to(WORKSPACE_ROOT))
    except ValueError:
        rel_str = target_path.name
    safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", rel_str)
    backup_path = BACKUP_DIR / f"{timestamp}__{safe_name}.bak"
    shutil.copy2(target_path, backup_path)
    state.setdefault("last_backup_map", {})[rel_str] = str(backup_path)
    save_state(state)
    log_console("BACKUP", f"Respaldo creado en: {backup_path.name}")
    return backup_path


def generate_unified_diff(old_text: str, new_text: str, filename: str) -> str:
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{filename} (Original)",
        tofile=f"b/{filename} (Propuesto por Aryi)",
        lineterm="",
    )
    return "".join(diff)


def build_multipart_request(fields: dict, files: dict) -> Tuple[bytes, str]:
    boundary = f"----AryiBoundary{uuid.uuid4().hex}"
    body = bytearray()

    for name, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        body.extend(f"{value}\r\n".encode("utf-8"))

    for field_name, file_info in files.items():
        filename, file_bytes, content_type = file_info
        if not content_type:
            content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(
            f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode("utf-8")
        )
        body.extend(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
        body.extend(file_bytes)
        body.extend(b"\r\n")

    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def tg_send_text(text: str) -> bool:
    if not text:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    chunks = [text[i : i + 3800] for i in range(0, len(text), 3800)]
    for chunk in chunks:
        payload = urllib.parse.urlencode({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": chunk,
            "disable_web_page_preview": "true",
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                if resp.status != 200:
                    return False
        except Exception as e:
            log_console("TG_ERROR", f"Fallo al enviar mensaje a Telegram: {e}")
            return False
    return True


def tg_send_document(filename: str, content_bytes: bytes, caption: str = "") -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
    fields = {"chat_id": TELEGRAM_CHAT_ID}
    if caption:
        fields["caption"] = caption[:950]
    files = {"document": (filename, content_bytes, "text/plain; charset=utf-8")}
    body, content_type = build_multipart_request(fields, files)
    req = urllib.request.Request(url, data=body, headers={"Content-Type": content_type}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return resp.status == 200
    except Exception as e:
        log_console("TG_DOC_ERR", str(e))
        return False


def tg_send_audio(filename: str, audio_bytes: bytes, caption: str = "") -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendAudio"
    fields = {"chat_id": TELEGRAM_CHAT_ID}
    if caption:
        fields["caption"] = caption[:950]
    files = {"audio": (filename, audio_bytes, "audio/wav")}
    body, content_type = build_multipart_request(fields, files)
    req = urllib.request.Request(url, data=body, headers={"Content-Type": content_type}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status == 200
    except Exception as e:
        log_console("TG_AUD_ERR", str(e))
        return False


def tg_send_photo(filename: str, image_bytes: bytes, caption: str = "") -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    fields = {"chat_id": TELEGRAM_CHAT_ID}
    if caption:
        fields["caption"] = caption[:950]
    files = {"photo": (filename, image_bytes, "image/png")}
    body, content_type = build_multipart_request(fields, files)
    req = urllib.request.Request(url, data=body, headers={"Content-Type": content_type}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status == 200
    except Exception as e:
        log_console("TG_IMG_ERR", str(e))
        return False


def tg_download_file(file_id: str) -> Tuple[bytes, str]:
    info_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile?file_id={urllib.parse.quote(file_id)}"
    with urllib.request.urlopen(info_url, timeout=20) as resp:
        info = json.loads(resp.read().decode("utf-8"))
    file_path = info["result"]["file_path"]
    dl_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
    with urllib.request.urlopen(dl_url, timeout=60) as resp:
        return resp.read(), Path(file_path).name


def tg_get_updates(offset: int, timeout_sec: int = 10) -> list:
    params = urllib.parse.urlencode({"offset": offset, "timeout": timeout_sec})
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates?{params}"
    try:
        with urllib.request.urlopen(url, timeout=timeout_sec + 8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok"):
                return data.get("result", [])
    except Exception as e:
        log_console("TG_POLL_WARN", f"Reintentando conexion con Telegram: {e}")
        time.sleep(2)
    return []


def ai_whisper_transcribe(audio_bytes: bytes, filename: str = "voice.ogg") -> str:
    with CooperativeGpuTurn("stt"):
        files = {"file": (filename, audio_bytes, "audio/ogg")}
        body, content_type = build_multipart_request({}, files)
        req = urllib.request.Request(
            SERVICIOS_IA["stt"],
            data=body,
            headers={"Content-Type": content_type},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=None) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
                return (data.get("text") or "").strip()
        except Exception as e:
            return f"[ERROR_STT]: {e}"


def ai_tts_synthesize(text: str) -> bytes:
    clean_text = re.sub(r"[*_`#~>-]+", " ", text)
    clean_text = re.sub(r"\s+", " ", clean_text).strip()[:1500]
    with CooperativeGpuTurn("tts"):
        payload = json.dumps({"texto": clean_text}, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            SERVICIOS_IA["tts"],
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=None) as resp:
            return resp.read()


def ai_sd_generate_image(api_base: str, prompt: str, model_hint: str = DEFAULT_LLM_MODEL, steps: int = 20) -> bytes:
    free_ollama_vram(api_base, model_hint)
    with CooperativeGpuTurn("sd"):
        payload = json.dumps({
            "prompt": prompt,
            "negative_prompt": "blurry, low quality, deformed, watermark, text",
            "steps": steps,
            "width": 512,
            "height": 512,
        }).encode("utf-8")
        req = urllib.request.Request(
            SERVICIOS_IA["sd"],
            data=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=None) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return base64.b64decode(data["images"][0])


# =============================================================================
# 12. MOTOR DE AUDITORIA PROFUNDA Y AUTO-EVOLUCION (DE aryiTelegram.py)
# =============================================================================
def extract_json_object(raw_text: str) -> dict:
    if not raw_text:
        return {}
    pattern = BT + r"(?:json)?\s*(\{[\s\S]*?\})\s*" + BT
    fenced = re.search(pattern, raw_text)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except Exception:
            pass
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw_text[start : end + 1])
        except Exception:
            pass
    return {}


def extract_code_block(raw_text: str) -> str:
    pattern = BT + r"(?:\w+)?\n([\s\S]*?)" + BT
    matches = re.findall(pattern, raw_text)
    if matches:
        return max(matches, key=len).strip()
    return ""


def deep_analyze_workspace_file(api_base: str, file_path: Path, state: dict) -> dict:
    rel_path = str(file_path.relative_to(WORKSPACE_ROOT))
    model = state.get("model", DEFAULT_LLM_MODEL)
    file_size = file_path.stat().st_size
    ext = file_path.suffix.lower() or "(sin extension)"
    is_readonly = file_path.name in READ_ONLY_FILES

    if is_probably_binary(file_path):
        return {
            "archivo": rel_path,
            "extension": ext,
            "tamano_bytes": file_size,
            "es_binario": True,
            "solo_lectura": True,
            "investigacion_web": "No requerida (archivo binario).",
            "resumen_profundo": f"Archivo binario ({ext}) de {file_size} bytes en {rel_path}.",
            "features_para_agente": "Registrar ruta en inventario.",
            "mejoras_para_proyecto": "Mantener codigo fuente sincronizado.",
            "prioridad": "baja",
        }

    raw_content = file_path.read_text(encoding="utf-8", errors="replace")
    synthesized_source = raw_content[:CHUNK_SIZE_CHARS]

    search_decision_prompt = (
        f"Archivo: {rel_path} ({ext})\n"
        f"Extracto:\n{synthesized_source[:2000]}\n\n"
        "Si necesitas buscar en internet alguna libreria u optimizacion para este codigo, "
        "escribe SOLO una consulta corta (maximo 6 palabras). Si no, responde exactamente: NO_WEB"
    )
    query_idea = ai_ollama_generate(
        api_base,
        search_decision_prompt,
        model=model,
        temperature=0.2,
        num_ctx=2048,
        task_label=f"Evaluacion Web ({rel_path})",
    )

    web_findings = "No fue necesaria busqueda externa."
    if query_idea and "NO_WEB" not in query_idea.upper() and not query_idea.startswith("[ERROR"):
        clean_query = query_idea.splitlines()[0].strip(" \"'`")
        if 3 < len(clean_query) < 80:
            web_findings = NAVEGADOR.buscar(clean_query, max_results=3)

    agent_source = AGENT_FILE.read_text(encoding="utf-8", errors="replace")
    agent_functions = re.findall(r"^def\s+([a-zA-Z0-9_]+)\s*\(", agent_source, flags=re.MULTILINE)

    system_prompt = (
        "Eres Aryi, arquitecto de software autonomo de Syntax Sanctuary. "
        "Si el archivo es PHP, evalua su compatibilidad con las funciones declarativas de v2.php. "
        "Devuelve unicamente un objeto JSON valido en espanol."
    )
    final_analysis_prompt = (
        f"Audita tecnicamente el archivo {rel_path} ({file_size} bytes):\n"
        f"Funciones actuales del agente Python: {', '.join(agent_functions[:40])}\n\n"
        f"Investigacion Web:\n{web_findings}\n\n"
        f"Contenido:\n{BT}\n{synthesized_source[:10000]}\n{BT}\n\n"
        "Responde UNICAMENTE con un JSON valido con las claves: "
        '"resumen_profundo", "features_para_agente", "mejoras_para_proyecto", "prioridad".'
    )

    llm_raw = ai_ollama_generate(
        api_base,
        final_analysis_prompt,
        model=model,
        system=system_prompt,
        temperature=0.25,
        num_ctx=4096,
        task_label=f"Auditoria Profunda ({rel_path})",
        notify_telegram=True,
    )
    parsed = extract_json_object(llm_raw) or {
        "resumen_profundo": "Analisis completado en formato libre.",
        "features_para_agente": "Ver detalles en mejoras.",
        "mejoras_para_proyecto": llm_raw[:2200],
        "prioridad": "media",
    }
    parsed.update({
        "archivo": rel_path,
        "extension": ext,
        "tamano_bytes": file_size,
        "es_binario": False,
        "solo_lectura": is_readonly,
        "investigacion_web": web_findings,
        "fecha_analisis": datetime.now().isoformat(),
    })
    return parsed


def build_proposed_project_file(api_base: str, file_path: Path, report: dict, extra_instructions: str, state: dict) -> str:
    original_code = file_path.read_text(encoding="utf-8", errors="replace")
    model = state.get("model", DEFAULT_LLM_MODEL)
    extra = extra_instructions or "Manten compatibilidad total y no elimines funcionalidades existentes."
    prompt = (
        f"Genera la version mejorada de {file_path.name}.\n"
        f"Mejoras:\n{report.get('mejoras_para_proyecto', '')}\n"
        f"Instrucciones:\n{extra}\n\n"
        f"Codigo original:\n{BT}\n{original_code}\n{BT}\n\n"
        f"Devuelve UNICAMENTE el codigo completo actualizado dentro de {BT} ... {BT}."
    )
    raw_resp = ai_ollama_generate(
        api_base, prompt, model=model, temperature=0.2, num_ctx=8192, task_label=f"Reescritura de {file_path.name}"
    )
    return extract_code_block(raw_resp)


def build_proposed_agent_evolution(api_base: str, report: dict, extra_instructions: str, state: dict) -> Tuple[bool, str, str]:
    current_agent_code = AGENT_FILE.read_text(encoding="utf-8", errors="replace")
    model = state.get("model", DEFAULT_LLM_MODEL)
    feature_desc = report.get("features_para_agente", "")
    extra = extra_instructions or "Usa solo libreria estandar de Python 3."

    prompt = (
        f"Escribe una funcion auxiliar en Python 3 que implemente la capacidad aprendida de {report.get('archivo', '')}:\n"
        f"{feature_desc}\nReglas: {extra}\n"
        f"Devuelve UNICAMENTE el codigo dentro de {BT}python ... {BT}."
    )
    raw_resp = ai_ollama_generate(
        api_base, prompt, model=model, temperature=0.2, num_ctx=4096, task_label="Generando Auto-Evolucion Python"
    )
    plugin_code = extract_code_block(raw_resp)
    if not plugin_code:
        return False, "", "El modelo no devolvio un bloque Python valido."

    try:
        ast.parse(plugin_code)
    except SyntaxError as e:
        return False, "", f"Error de sintaxis en el nuevo modulo (linea {e.lineno}): {e.msg}"

    marker = "# [EVOLUTION_PLUGINS_ANCHOR]"
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    wrapped_plugin = f"\n\n# --- Evolucion integrada el {stamp} ---\n{plugin_code}\n{marker}"

    updated_agent_code = (
        current_agent_code.replace(marker, wrapped_plugin, 1)
        if marker in current_agent_code
        else current_agent_code + "\n" + wrapped_plugin
    )

    try:
        ast.parse(updated_agent_code)
    except SyntaxError as e:
        return False, "", f"Validacion AST global fallida en linea {e.lineno}: {e.msg}"

    return True, updated_agent_code, "Codigo validado con AST correctamente."


# =============================================================================
# 13. MODO BOT AUTONOMO DE TELEGRAM (CON SELECTOR DE MODELO, WEB Y TUTORIAL)
# =============================================================================
def extract_incoming_telegram_command(message: dict) -> Tuple[str, bool]:
    if "text" in message and message["text"]:
        return message["text"].strip(), False
    voice_obj = message.get("voice") or message.get("audio")
    if voice_obj and "file_id" in voice_obj:
        try:
            tg_send_text("Nota de voz recibida. Transcribiendo con Whisper STT...")
            audio_bytes, fname = tg_download_file(voice_obj["file_id"])
            transcription = ai_whisper_transcribe(audio_bytes, fname)
            if transcription and not transcription.startswith("[ERROR"):
                tg_send_text(f'Transcripcion: "{transcription}"')
                return transcription.strip(), True
        except Exception as e:
            tg_send_text(f"Error procesando nota de voz: {e}")
    return "", False


def procesar_comandos_rapidos_telegram(api_base: str, raw_cmd: str, state: dict) -> bool:
    cmd_lower = raw_cmd.lower().strip()

    if cmd_lower == "/modelos":
        mods = listar_modelos_ollama(api_base) or [DEFAULT_LLM_MODEL]
        tg_send_text(
            "Modelos disponibles en Ollama:\n"
            + "\n".join(f"- {m}" for m in mods)
            + f"\n\nModelo activo para la proxima peticion: {state.get('model')}\n"
            "Usa /modelo <nombre> antes de tu peticion para cambiarlo."
        )
        return True

    if cmd_lower.startswith("/modelo "):
        chosen = raw_cmd[8:].strip()
        if chosen:
            state["model"] = chosen
            save_state(state)
            tg_send_text(f"Modelo seleccionado para las siguientes peticiones: {chosen}")
        return True

    if cmd_lower in ("/tutorial", "tutorial", "/v2"):
        tg_send_text(obtener_resumen_tutorial_telegram())
        return True

    if cmd_lower.startswith("/buscar ") or cmd_lower.startswith("/investigar "):
        partes = raw_cmd.split(None, 1)
        topic = partes[1].strip() if len(partes) > 1 else ""
        tg_send_text(f"Buscando en Internet con el navegador integrado: '{topic}'...")
        raw_search = NAVEGADOR.buscar(topic, max_results=5)
        summary = ai_ollama_generate(
            api_base,
            f"Sintetiza tecnicamente estos resultados sobre '{topic}':\n\n{raw_search}",
            model=state.get("model", DEFAULT_LLM_MODEL),
            task_label=f"Investigacion ({topic})",
        )
        tg_send_text(f"Sintesis ({state.get('model')}):\n\n{summary}\n\nResultados:\n{raw_search}")
        return True

    if cmd_lower.startswith("/navegar ") or cmd_lower.startswith("/abrir "):
        partes = raw_cmd.split(None, 1)
        url = partes[1].strip() if len(partes) > 1 else ""
        tg_send_text(f"Abriendo pagina web: {url}...")
        contenido = NAVEGADOR.abrir_url(url, max_chars=3500)
        tg_send_text(contenido)
        return True

    if cmd_lower.startswith("/imagen "):
        img_prompt = raw_cmd[8:].strip()
        tg_send_text(f"Renderizando en Stable Diffusion: '{img_prompt}'...")
        try:
            png_bytes = ai_sd_generate_image(api_base, img_prompt, state.get("model", DEFAULT_LLM_MODEL))
            tg_send_photo("aryi_sd.png", png_bytes, caption=f"Prompt: {img_prompt}")
        except Exception as e:
            tg_send_text(f"Error en Stable Diffusion: {e}")
        return True

    if cmd_lower == "/liberar_vram":
        unloaded = free_ollama_vram(api_base, state.get("model", DEFAULT_LLM_MODEL))
        tg_send_text(f"VRAM liberada. Modelos descargados: {', '.join(unloaded) or 'Ninguno'}")
        return True

    return False


def ejecutar_modo_telegram(api_base: str) -> None:
    """Ejecuta el ciclo autonomo de auditoria y control por Telegram."""
    ensure_environment()
    state = load_state()
    log_console("TELEGRAM_BOT", f"Iniciando Modo Autonomo Telegram - Workspace: {WORKSPACE_ROOT}")

    initial_updates = tg_get_updates(state.get("last_update_id", 0) + 1, timeout_sec=1)
    for u in initial_updates:
        state["last_update_id"] = u["update_id"]
    save_state(state)

    tg_send_text(
        f"Aryi Unificado v8.1 en linea.\n"
        f"Workspace: {WORKSPACE_ROOT}\n"
        f"Modelo actual: {state.get('model')} (cambialo antes de cada accion con /modelo <nombre> o /modelos)\n"
        f"Navegador Web: /buscar <tema> | /navegar <url>\n"
        f"Tutorial v2.php: /tutorial"
    )

    while True:
        updates = tg_get_updates(state.get("last_update_id", 0) + 1, timeout_sec=15)
        for upd in updates:
            state["last_update_id"] = upd["update_id"]
            save_state(state)

            msg = upd.get("message", {})
            if str(msg.get("chat", {}).get("id", "")) != TELEGRAM_CHAT_ID:
                continue

            raw_cmd, _ = extract_incoming_telegram_command(msg)
            if not raw_cmd:
                continue

            if procesar_comandos_rapidos_telegram(api_base, raw_cmd, state):
                continue

            if raw_cmd.lower().strip() == "/auditar":
                tg_send_text("Auditando el primer archivo pendiente del workspace...")
                for fpath in sorted(WORKSPACE_ROOT.rglob("*")):
                    if fpath.is_file() and not any(p in SKIP_DIRECTORIES for p in fpath.parts):
                        rep = deep_analyze_workspace_file(api_base, fpath, state)
                        tg_send_text(
                            f"Archivo: {rep['archivo']}\n"
                            f"Modelo usado: {state.get('model')}\n\n"
                            f"Resumen:\n{rep.get('resumen_profundo')}\n\n"
                            f"Mejoras:\n{rep.get('mejoras_para_proyecto')}"
                        )
                        break
                continue

            tg_send_text(f"Procesando con {state.get('model')} (usa /modelo <nombre> si deseas otro)...")
            respuesta = ai_ollama_generate(
                api_base,
                raw_cmd,
                model=state.get("model", DEFAULT_LLM_MODEL),
                system=generar_system_prompt("estricto", obtener_limite_contexto(state.get("model", DEFAULT_LLM_MODEL))),
                task_label="Chat Telegram",
                notify_telegram=True,
            )
            tg_send_text(respuesta)


# =============================================================================
# 14. INTERFAZ INTERACTIVA DE CONSOLA (CLI) Y BUCLE PRINCIPAL UNIFICADO
# =============================================================================
def barra_inferior() -> str:
    return (
        " [Esc]+[Enter] Enviar | /tutorial | /buscar <q> | /navegar <url> | /modelo | /pre_modelo "
        "| /modo | /leer <ruta> | /telegram | /ayuda | salir "
    )


def crear_entrada() -> Callable[[str], str]:
    if PROMPT_TOOLKIT_OK and PromptSession is not None and Style is not None and sys.stdin.isatty():
        try:
            sesion = PromptSession(
                multiline=True,
                mouse_support=False,
                wrap_lines=True,
                bottom_toolbar=barra_inferior,
                style=Style.from_dict({"bottom-toolbar": "bg:#005f87 #ffffff bold"}),
            )
            return lambda prefijo: sesion.prompt(prefijo)
        except Exception:
            pass
    print("[INFO] Modo de entrada estandar (una linea por mensaje).")
    return lambda prefijo: input(prefijo)


AYUDA_CLI = (
    "\n======================================================================\n"
    " COMANDOS DEL ORQUESTADOR MAESTRO UNIFICADO (v8.1)\n"
    "======================================================================\n"
    "  /tutorial          Inicia el Tutorial Interactivo paso a paso de v2.php.\n"
    "  /buscar <consulta> Busca en Internet (DuckDuckGo) y muestra resultados.\n"
    "  /navegar <url|N>   Abre una URL (o el numero [N] de la ultima busqueda).\n"
    "  /modelo            Muestra la lista de modelos de Ollama y cambia el activo.\n"
    "  /pre_modelo        Activa/desactiva preguntar el modelo antes de cada peticion.\n"
    "  /modo              Alterna entre modo ESTRICTO (framework v2.php) y LIBRE.\n"
    "  /leer <ruta>       Adjunta un archivo del workspace a tu siguiente consulta.\n"
    "  /auditar <ruta>    Ejecuta la auditoria profunda + investigacion web sobre un archivo.\n"
    "  /vram              Libera los 6GB de VRAM en Ollama (keep_alive: 0).\n"
    "  /procesos          Lista los servicios en segundo plano (<bash_bg>).\n"
    "  /detener <pid>     Detiene un servicio en segundo plano por su PID.\n"
    "  /telegram          Cambia al bucle autonomo de escucha en Telegram.\n"
    "  /limpiar           Limpia el historial de conversacion.\n"
    "  /estado            Muestra nodo, modelo, modo, tokens y procesos.\n"
    "  salir              Cierra el orquestador.\n"
    "======================================================================\n"
)


# [EVOLUTION_PLUGINS_ANCHOR]


def main() -> None:
    ensure_environment()
    state = load_state()

    print("=" * 70)
    print(" [Syntax Sanctuary] - ORQUESTADOR MAESTRO UNIFICADO v8.1")
    print(" CLI + Telegram + Navegador Web IA + Selector Pre-Peticion + Tutorial v2.php")
    print("=" * 70)
    print(f"Workspace: {WORKSPACE_ROOT}")

    try:
        print("\nNodos Ollama disponibles:")
        for k, info in NODOS_OLLAMA.items():
            print(f"  [{k}] {info['nombre']}")
        eleccion_nodo = input("Selecciona el Nodo Ollama [2]: ").strip() or "2"
    except (EOFError, KeyboardInterrupt):
        return

    nodo = NODOS_OLLAMA.get(eleccion_nodo, NODOS_OLLAMA["2"])
    api_base = nodo["url"].rstrip("/")
    print(f"[INFO] Conectado a: {nodo['nombre']} -> {api_base}")

    print("\nModos de operacion:")
    print("  [1] Consola Interactiva + Agente Autonomo (con Navegador Web y Selector Pre-Peticion)")
    print("  [2] Tutorial Interactivo del Framework PHP (v2.php)")
    print("  [3] Agente Autonomo de Telegram (Auditoria de Workspace, Voz Whisper/TTS, SD)")
    try:
        modo_arranque = input("Elige como iniciar [1]: ").strip() or "1"
    except (EOFError, KeyboardInterrupt):
        return

    modelo, limite_tokens = seleccionar_modelo_interactivo(api_base, state.get("model", DEFAULT_LLM_MODEL))
    if not modelo:
        sys.exit(1)
    state["model"] = modelo
    save_state(state)

    if modo_arranque == "2":
        ejecutar_tutorial_interactivo(api_base, modelo)
    elif modo_arranque == "3":
        ejecutar_modo_telegram(api_base)
        return

    modo_framework = "estricto"
    preguntar_modelo_cada_vez: bool = bool(state.get("ask_model_each_request", True))
    historial: List[Dict[str, str]] = [
        {"role": "system", "content": generar_system_prompt(modo_framework, limite_tokens)}
    ]
    leer_entrada = crear_entrada()

    print("\nEscribe /ayuda para ver todos los comandos o /tutorial para aprender v2.php.")

    while True:
        try:
            texto = leer_entrada("\nTu:\n> ").strip()
        except KeyboardInterrupt:
            print("\n[INFO] Entrada cancelada.")
            continue
        except EOFError:
            break

        if not texto:
            continue
        cmd = texto.lower().strip()

        if cmd in {"salir", "exit", "quit"}:
            break

        if cmd in {"/ayuda", "/help"}:
            print(AYUDA_CLI)
            continue

        if cmd == "/tutorial":
            ejecutar_tutorial_interactivo(api_base, modelo)
            continue

        if cmd == "/telegram":
            ejecutar_modo_telegram(api_base)
            continue

        if cmd == "/modo":
            modo_framework = "libre" if modo_framework == "estricto" else "estricto"
            historial[0]["content"] = generar_system_prompt(modo_framework, limite_tokens)
            print(f"\n[SISTEMA] Modo cambiado a: {modo_framework.upper()}")
            continue

        if cmd == "/modelo":
            nuevo, nuevo_limite = seleccionar_modelo_interactivo(api_base, modelo)
            if nuevo:
                modelo, limite_tokens = nuevo, nuevo_limite
                state["model"] = modelo
                save_state(state)
                historial[0]["content"] = generar_system_prompt(modo_framework, limite_tokens)
            continue

        if cmd == "/pre_modelo":
            preguntar_modelo_cada_vez = not preguntar_modelo_cada_vez
            state["ask_model_each_request"] = preguntar_modelo_cada_vez
            save_state(state)
            estado_txt = "ACTIVADO (te preguntara antes de cada envio)" if preguntar_modelo_cada_vez else "DESACTIVADO"
            print(f"[SISTEMA] Selector de modelo antes de cada peticion: {estado_txt}")
            continue

        if cmd == "/vram":
            free_ollama_vram(api_base, modelo)
            continue

        if cmd == "/limpiar":
            del historial[1:]
            print("[SISTEMA] Historial limpiado.")
            continue

        if cmd == "/procesos":
            print("\n" + listar_procesos())
            continue

        if cmd.startswith("/detener"):
            partes = texto.split(None, 1)
            arg = partes[1].strip() if len(partes) > 1 else ""
            print("[SISTEMA] " + (detener_proceso(int(arg)) if arg.isdigit() else "Uso: /detener <pid>"))
            continue

        if cmd == "/estado":
            print(
                f"\n[ESTADO DEL ORQUESTADOR]\n"
                f"  Nodo Ollama: {nodo['nombre']} ({api_base})\n"
                f"  Modelo activo: {modelo} ({limite_tokens} tokens)\n"
                f"  Selector pre-peticion: {'SI' if preguntar_modelo_cada_vez else 'NO'}\n"
                f"  Modo PHP: {modo_framework.upper()}\n"
                f"  Mensajes en historial: {len(historial)} (~{total_tokens(historial)} tokens)\n"
                f"  URLs visitadas en sesion: {len(NAVEGADOR.historial_urls)}\n"
                f"  Servicios de fondo activos: {sum(1 for p in PROCESOS_FONDO.values() if p.popen.poll() is None)}"
            )
            continue

        if cmd.startswith("/buscar "):
            consulta = texto.split(None, 1)[1].strip()
            res_web = NAVEGADOR.buscar(consulta, max_results=6)
            print("\n" + res_web)
            if confirmar("Deseas enviar estos resultados de busqueda al contexto de la IA?"):
                texto = f"He buscado en Internet '{consulta}'. Analiza estos resultados:\n\n{res_web}"
            else:
                continue

        elif cmd.startswith("/navegar "):
            destino = texto.split(None, 1)[1].strip()
            contenido_pag = NAVEGADOR.abrir_url(destino, max_chars=MAX_FEEDBACK)
            print("\n" + recortar(contenido_pag, MAX_SALIDA_CONSOLA))
            if confirmar("Deseas enviar el contenido de esta pagina al contexto de la IA?"):
                texto = f"Contenido extraido de la pagina '{destino}':\n\n{contenido_pag}\n\nAnalizalo."
            else:
                continue

        elif cmd.startswith("/auditar "):
            ruta_txt = texto.split(None, 1)[1].strip().strip("\"'")
            try:
                ruta_obj = ruta_permitida(ruta_txt)
                modelo, limite_tokens = confirmar_o_cambiar_modelo_pre_peticion(
                    api_base, modelo, preguntar=preguntar_modelo_cada_vez
                )
                state["model"] = modelo
                rep = deep_analyze_workspace_file(api_base, ruta_obj, state)
                print("\n" + json.dumps(rep, indent=2, ensure_ascii=False))
            except Exception as exc:
                print(f"[ERROR /auditar] {exc}")
            continue

        elif cmd == "/leer" or cmd.startswith("/leer "):
            partes = texto.split(None, 1)
            if len(partes) < 2 or not partes[1].strip():
                print("[ERROR] Uso: /leer ruta/del/archivo")
                continue
            ruta_txt = partes[1].strip().strip("\"'")
            try:
                ruta = ruta_permitida(ruta_txt)
                if not ruta.is_file():
                    raise FileNotFoundError(f"No existe un archivo regular en: {ruta}")
                if ruta.stat().st_size > MAX_ARCHIVO_LEER:
                    raise ValueError(f"Archivo demasiado grande ({ruta.stat().st_size} bytes).")
                codigo = ruta.read_text(encoding="utf-8", errors="replace")
                instruccion = leer_entrada("Instruccion para el archivo:\n> ").strip()
                instruccion = instruccion or "Analiza este archivo y propon mejoras compatibles con v2.php."
                texto = f"{instruccion}\n\nArchivo ({ruta_txt}):\n<referencia_archivo>\n{codigo}\n</referencia_archivo>"
            except Exception as exc:
                print(f"[ERROR /leer] {exc}")
                continue

        agregar_mensaje(historial, "user", texto)

        for paso in range(1, PASOS_MAXIMOS + 1):
            modelo, limite_tokens = confirmar_o_cambiar_modelo_pre_peticion(
                api_base, modelo, preguntar=preguntar_modelo_cada_vez
            )
            state["model"] = modelo
            save_state(state)
            historial[0]["content"] = generar_system_prompt(modo_framework, limite_tokens)

            podar_historial(historial, limite_tokens)
            try:
                print(f"\nAgente ({modelo}) - paso {paso}/{PASOS_MAXIMOS}:\n", end="", flush=True)
                texto_ia = solicitar_a_ollama_stream(api_base, modelo, historial, limite_tokens)
            except GeneracionInterrumpida:
                break
            except Exception as exc:
                print(f"\n[ERROR DE COMUNICACION CON OLLAMA] {exc}")
                break

            agregar_mensaje(historial, "assistant", texto_ia)

            try:
                resultado = procesar_acciones_agente(texto_ia)
            except Exception as exc:
                print(f"\n[ERROR EJECUTANDO ACCIONES] {type(exc).__name__}: {exc}")
                break

            if not resultado.hubo_directivas:
                break

            agregar_mensaje(historial, "user", "RESULTADO DE LAS ACCIONES:\n" + (resultado.feedback or "(sin detalle)"))
            if paso < PASOS_MAXIMOS:
                print(f"\n[INFO] Realimentando al agente con los resultados ({paso}/{PASOS_MAXIMOS})...")
            else:
                print("\n[INFO] Limite de pasos alcanzado; el resultado queda en el historial.")

    activos = [p for p in PROCESOS_FONDO.values() if p.popen.poll() is None]
    if activos:
        print("\n[AVISO] Siguen activos estos servicios de fondo:")
        print(listar_procesos())
    print("\n[SISTEMA] Orquestador Maestro Unificado finalizado.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[SISTEMA] Interrumpido por el usuario.")