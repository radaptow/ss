#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
 ARYI OMEGA v10.0 · MULTIMODAL GOD-TIER TERMINAL AGENT & SWARM ORCHESTRATOR
================================================================================
 Diseñado para correr de forma 100% nativa en Windows (PowerShell / CMD) y Linux,
 sin requerir librerías pesadas externas (solo Python 3.8+ y `requests`).

 CAPACIDADES MULTIMODALES Y DE SISTEMA EN v10.0:
 1. VISIÓN MULTIMODAL NATIVA (`llava-phi3:latest`, `moondream:latest`):
    - `/vision <ruta_imagen> [pregunta]` o etiqueta `<vision path="...">`: codifica la
      imagen en Base64 y la analiza con el mejor modelo `vision_specialist` de tu nodo.
    - `/screenshot [pregunta]`: captura tu pantalla de Windows en vivo usando PowerShell
      (`.NET System.Drawing`), la guarda en `.aryi_renders/` y la analiza con IA.
    - Soporte de Fotos e Imágenes en Telegram: si le envías una foto a tu bot de
      Telegram, ARYI la descarga automáticamente, la analiza con el modelo de visión y
      te responde con la descripción detallada.

 2. FLUJO DE VOZ COMPLETO EN CONSOLA (MICRÓFONO -> WHISPER STT -> OLLAMA -> TTS):
    - Captura de micrófono 100% nativa en Windows mediante la API del sistema `winmm.dll`
      (`mciSendStringW` en Python puro, sin necesitar instalar `PyAudio` ni compiladores C++).
    - Envía el audio grabado a tu contenedor **Whisper STT** (`http://100.115.1.71:8000/v1/audio/transcriptions`),
      procesa la respuesta con Ollama y la reproduce en voz mediante tu contenedor
      **Motor Voz TTS** (`http://100.115.1.71:5050/tts` + `winsound`, con fallback automático
      a la voz neural nativa de Windows `SAPI.SpVoice` si el puerto 5050 no responde).
    - También soporta recibir **Notas de Voz en Telegram** (`message['voice']`), transcribirlas
      con Whisper y responderte con texto y audio.
    - Comandos: `/voice [seg]`, `/talk` (conversación continua manos libres), `/say <texto>`, `/tts on|off`.

 3. ESTUDIO STABLE DIFFUSION EN CONSOLA Y TELEGRAM (`http://100.115.1.71:7860`):
    - `/imagine <prompt>` o etiqueta `<sd_image>`: traduce y optimiza automáticamente tu
      prompt al inglés con Ollama, libera los 6GB de VRAM (`keep_alive: 0`) para no ahogar
      la GPU, renderiza la imagen en Stable Diffusion, la guarda en `.aryi_renders/`,
      dibuja una vista previa ANSI en tu terminal, la abre en Windows y la envía a tu Telegram.

 4. ARCHIVADOR Y EDITOR INTERACTIVO COMPLETO EN TERMINAL + EDICIÓN QUIRÚRGICA:
    - Explorador y editor completo desde comandos sin salir de ARYI:
      `/files [ruta]`, `/tree [ruta]`, `/cat <archivo> [ini] [fin]`, `/edit <archivo>` (editor
      interactivo en consola o `--notepad`/`--code`), `/patch <archivo>` (reemplazo exacto),
      `/search <texto>`, `/mkdir <ruta>`, `/touch <ruta>`, `/rm <ruta>`, `/cp <a> <b>`, `/mv <a> <b>`.
    - Nueva etiqueta XML `<edit_file path="...">` con bloques `<<<<<<< SEARCH ... ======= ... >>>>>>> REPLACE`
      para que el agente edite líneas específicas de archivos grandes sin reescribirlos enteros.

 5. GESTIÓN DE 6GB VRAM Y DIAGNÓSTICO DE CONTENEDORES DOCKER (`/health`, `/vram free`):
    - Monitorea la latencia en milisegundos de tus 4 contenedores (`STT :8000`, `Ollama :11434`,
      `TTS :5050`, `Stable Diffusion :7860`) y permite vaciar la VRAM en un comando (`/vram free`).
================================================================================
"""

from __future__ import annotations

import base64
import concurrent.futures
import ctypes
import html
import json
import os
import platform
import queue
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests

# Activar secuencias ANSI en consola nativa de Windows 10/11
if platform.system() == "Windows":
    try:
        os.system("")
    except Exception:
        pass


# =============================================================================
# COLORES ANSI Y ESTÉTICA DE CONSOLA
# =============================================================================
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    MAGENTA = "\033[95m"
    BLUE = "\033[94m"


# =============================================================================
# CONFIGURACIÓN GLOBAL Y ENDPOINTS DEL CLÚSTER (100.115.1.71)
# =============================================================================
def _env_int(nombre: str, defecto: int) -> int:
    try:
        return int(os.getenv(nombre, "").strip() or defecto)
    except ValueError:
        return defecto


def _env_bool(nombre: str, defecto: bool = False) -> bool:
    val = os.getenv(nombre, "").strip().lower()
    if not val:
        return defecto
    return val in {"1", "true", "yes", "si", "sí", "on"}


IS_WINDOWS = platform.system() == "Windows"
IP_WINDOWS_GPU = os.getenv("ARYI_WINDOWS_GPU_IP", "100.115.1.71").strip()

API_STT_URL = os.getenv("ARYI_STT_URL", f"http://{IP_WINDOWS_GPU}:8000/v1/audio/transcriptions").strip()
API_TTS_URL = os.getenv("ARYI_TTS_URL", f"http://{IP_WINDOWS_GPU}:5050/tts").strip()
API_SD_URL = os.getenv("ARYI_SD_URL", f"http://{IP_WINDOWS_GPU}:7860/sdapi/v1/txt2img").strip()

ENDPOINTS: Dict[str, Dict[str, str]] = {
    "1": {"nombre": "Localhost (127.0.0.1:11434)", "url": "http://127.0.0.1:11434/api"},
    "2": {"nombre": f"Nodo GPU Remoto ({IP_WINDOWS_GPU}:11434)", "url": f"http://{IP_WINDOWS_GPU}:11434/api"},
}


def _get_default_workspace() -> Path:
    home = Path.home()
    for candidate in ("Documents", "Documentos"):
        d = home / candidate
        if d.exists():
            return d / "Laboratorio"
    return home / "Laboratorio"


SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = Path(os.getenv("ARYI_WORKSPACE_ROOT", str(SCRIPT_DIR))).expanduser().resolve()
WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)

LOGS_DIR = WORKSPACE_ROOT / ".aryi_logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

LIVE_LOG_FILE = LOGS_DIR / "aryi_live.log"
AUDIT_LOG_FILE = LOGS_DIR / "auditoria.jsonl"
TELEMETRY_FILE = LOGS_DIR / "telemetry_matrix.json"

MEMORY_DIR = WORKSPACE_ROOT / ".aryi_memory"
FRAMEWORKS_DIR = MEMORY_DIR / "frameworks"
MISSIONS_DIR = MEMORY_DIR / "missions"
RENDERS_DIR = WORKSPACE_ROOT / ".aryi_renders"
AUDIO_DIR = WORKSPACE_ROOT / ".aryi_audio"
for _d in (MEMORY_DIR, FRAMEWORKS_DIR, MISSIONS_DIR, RENDERS_DIR, AUDIO_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def _calcular_raices_permitidas() -> List[Path]:
    raices = [WORKSPACE_ROOT, SCRIPT_DIR, _get_default_workspace().resolve()]
    for bruto in os.getenv("ARYI_ALLOWED_ROOTS", "").split(os.pathsep):
        bruto = bruto.strip()
        if not bruto:
            continue
        try:
            raiz = Path(bruto).expanduser().resolve()
            if raiz not in raices:
                raices.append(raiz)
        except Exception:
            continue
    return raices


RAICES_PERMITIDAS = _calcular_raices_permitidas()
CURRENT_NAV_DIR: Path = WORKSPACE_ROOT  # Directorio actual del Archivador en consola

MAX_FEEDBACK = _env_int("ARYI_MAX_FEEDBACK", 8_000)
MAX_SALIDA_CONSOLA = 2_500
TIMEOUT_CMD = _env_int("ARYI_TIMEOUT_BASH", 180)
TIMEOUT_HTTP_CONNECT = 10
TIMEOUT_HTTP_READ = _env_int("ARYI_HTTP_READ", 360)
PASOS_MAXIMOS = max(1, _env_int("ARYI_PASOS_MAXIMOS", 10))
AUTO_APPROVE = _env_bool("ARYI_AUTO_APPROVE", False)
AUTO_TTS_SPEAK = _env_bool("ARYI_AUTO_TTS", False)  # Si es True, habla todas las respuestas por voz

DEFAULT_TG_TOKEN = "8449908090:AAFS8OqY-a5D1lejzhIN4bGcutO_AzCYEC0"
DEFAULT_TG_CHAT_ID = "8933548802"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", DEFAULT_TG_TOKEN).strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", DEFAULT_TG_CHAT_ID).strip()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()

CHAT_DB_PATH_STR = os.getenv("ARYI_CHAT_DB", str(WORKSPACE_ROOT / "chat_db.json")).strip()
CHAT_DB_FILE = Path(CHAT_DB_PATH_STR).expanduser().resolve()
ADMIN_WEB_HANDLE = os.getenv("ARYI_WEB_HANDLE", "SS-TFH").strip()

HTTP = requests.Session()
HTTP.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
})

GPU_INFERENCE_LOCK = threading.Lock()
LOG_WRITE_LOCK = threading.Lock()


# =============================================================================
# SISTEMA DE LOGS EN TIEMPO REAL ESTILO DOCKER (`aryi_live.log`)
# =============================================================================
def log_event(component: str, message: str, level: str = "INFO") -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    clean_msg = re.sub(r"\033\[[0-9;]*m", "", str(message)).replace("\r", " ").strip()
    line = f"[{ts}] [{level:<5}] [{component:<14}] {clean_msg}\n"
    with LOG_WRITE_LOCK:
        try:
            with open(LIVE_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass


def leer_ultimos_logs(lineas: int = 35) -> str:
    if not LIVE_LOG_FILE.is_file():
        return "Aún no existe el archivo de logs en vivo."
    try:
        contenido = LIVE_LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
        ultimas = contenido[-max(1, lineas):]
        return (
            f"=== ÚLTIMAS {len(ultimas)} LÍNEAS DE {LIVE_LOG_FILE} ===\n"
            + "\n".join(ultimas)
            + f"\n\n💡 Tip Docker-Style en PowerShell: Get-Content -Path \"{LIVE_LOG_FILE}\" -Wait -Tail 40"
            + "\n   (o escribe `/logs follow` para abrir un visor en vivo en otra ventana)"
        )
    except Exception as e:
        return f"Error leyendo logs: {e}"


def abrir_visor_logs_en_vivo() -> str:
    if not IS_WINDOWS:
        return f"Ejecuta en otra terminal: tail -f \"{LIVE_LOG_FILE}\""
    try:
        cmd_ps = (
            f'$Host.UI.RawUI.WindowTitle = "ARYI OMEGA - Docker Live Logs"; '
            f'Write-Host "=== ARYI OMEGA LIVE STREAM ({LIVE_LOG_FILE}) ===" -ForegroundColor Cyan; '
            f'Get-Content -Path "{LIVE_LOG_FILE}" -Wait -Tail 40'
        )
        subprocess.Popen(
            ["powershell.exe", "-NoExit", "-NoProfile", "-Command", cmd_ps],
            creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010),
        )
        log_event("LOG_VIEWER", "Ventana externa de PowerShell abierta con Get-Content -Wait", "INFO")
        return f"✅ Ventana de logs en tiempo real abierta (`Get-Content -Wait -Tail 40 \"{LIVE_LOG_FILE}\"`)."
    except Exception as e:
        return f"No se pudo abrir ventana automática ({e}). Ejecuta manualmente:\nGet-Content -Path \"{LIVE_LOG_FILE}\" -Wait -Tail 40"


# =============================================================================
# UTILIDADES DE TEXTO, SEGURIDAD Y AUDITORÍA
# =============================================================================
def recortar(texto: Any, limite: int = MAX_FEEDBACK, proporcion_cola: float = 0.65) -> str:
    texto = str(texto or "")
    if limite <= 0 or len(texto) <= limite:
        return texto
    marcador = f"\n... [{len(texto) - limite} caracteres omitidos] ...\n"
    util = max(0, limite - len(marcador))
    n_cola = int(util * proporcion_cola)
    n_ini = util - n_cola
    return texto[:n_ini] + marcador + (texto[-n_cola:] if n_cola else "")


def estimar_tokens(texto: str) -> int:
    return max(1, int(len(texto) / 3.5)) if texto else 0


def limpiar_bloques_think(texto: str) -> str:
    return re.sub(r"<think>.*?</think>", "", texto or "", flags=re.DOTALL | re.IGNORECASE).strip()


def limpiar_texto_para_voz(texto: str) -> str:
    """Limpia bloques de código, XML, URLs y markdown para que el motor TTS hable con naturalidad."""
    t = limpiar_bloques_think(texto)
    t = re.sub(r"<(file|edit_file|powershell|bash|cmd|bash_bg|git|web_search|web_fetch|learn_framework|spawn_team|vision|sd_image|speak)\b[^>]*>.*?</\1>", " He ejecutado la acción en pantalla. ", t, flags=re.DOTALL | re.IGNORECASE)
    t = re.sub(r"```[\s\S]*?```", " Te dejo el bloque de código en la consola. ", t)
    t = re.sub(r"`([^`]+)`", r"\1", t)
    t = re.sub(r"https?://\S+", " enlace ", t)
    t = re.sub(r"[*_~#>|•─═]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:900]


def ruta_permitida(ruta_bruta: str, base_dir: Optional[Path] = None) -> Path:
    limpia = (ruta_bruta or "").strip().strip("\"'")
    if not limpia or "\x00" in limpia:
        raise ValueError("Ruta vacía o inválida.")
    candidata = Path(limpia).expanduser()
    if not candidata.is_absolute():
        candidata = (base_dir or CURRENT_NAV_DIR or WORKSPACE_ROOT) / candidata
    candidata = candidata.resolve(strict=False)
    for raiz in RAICES_PERMITIDAS:
        try:
            candidata.relative_to(raiz)
            return candidata
        except ValueError:
            continue
    raise PermissionError(f"Ruta fuera de las raíces permitidas ({WORKSPACE_ROOT}): {candidata}")


def formatear_bytes(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes / (1024 * 1024):.2f} MB"


def auditar(evento: str, detalle: str, resultado: str) -> None:
    log_event(evento.upper(), f"{detalle[:200]} -> {resultado[:120]}")
    try:
        registro = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "evento": evento,
            "detalle": detalle[:600],
            "resultado": resultado[:300],
        }
        with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
    except Exception:
        pass


def escribir_archivo_atomico(ruta: Path, contenido: str) -> None:
    ruta = ruta_permitida(str(ruta))
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fd, temporal = tempfile.mkstemp(prefix=".aryi_tmp_", dir=str(ruta.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as archivo:
            archivo.write(contenido)
            if contenido and not contenido.endswith("\n"):
                archivo.write("\n")
            archivo.flush()
            os.fsync(archivo.fileno())
        os.replace(temporal, ruta)
        auditar("write_file", str(ruta), f"OK ({len(contenido)} chars)")
    except BaseException:
        try:
            os.unlink(temporal)
        except OSError:
            pass
        raise


def aplicar_edicion_quirurgica(ruta: Path, contenido_instrucciones: str, search_attr: str = "", replace_attr: str = "") -> str:
    """
    Permite editar fragmentos específicos de un archivo existente sin sobrescribirlo entero.
    Soporta:
    1) Bloques estilo Git Conflict:
       <<<<<<< SEARCH
       codigo viejo
       =======
       codigo nuevo
       >>>>>>> REPLACE
    2) Atributos XML `search="..." replace="..."`
    """
    ruta = ruta_permitida(str(ruta))
    if not ruta.is_file():
        raise FileNotFoundError(f"El archivo a editar no existe: {ruta}")

    original = ruta.read_text(encoding="utf-8", errors="replace")
    modificado = original
    reemplazos = 0

    patron_bloques = re.compile(
        r"<{5,}\s*SEARCH\s*\n(.*?)\n={5,}\s*\n(.*?)\n>{5,}\s*REPLACE",
        flags=re.DOTALL,
    )
    matches = list(patron_bloques.finditer(contenido_instrucciones))

    if matches:
        for m in matches:
            bloque_buscar = m.group(1)
            bloque_reemplazar = m.group(2)
            if bloque_buscar in modificado:
                modificado = modificado.replace(bloque_buscar, bloque_reemplazar, 1)
                reemplazos += 1
            elif bloque_buscar.strip() and bloque_buscar.strip() in modificado:
                modificado = modificado.replace(bloque_buscar.strip(), bloque_reemplazar.strip(), 1)
                reemplazos += 1
    elif search_attr:
        if search_attr in modificado:
            modificado = modificado.replace(search_attr, replace_attr, 1)
            reemplazos += 1

    if reemplazos == 0:
        raise ValueError(f"No se encontró el fragmento SEARCH exacto dentro de {ruta.name}.")

    escribir_archivo_atomico(ruta, modificado)
    return f"Archivo {ruta} editado quirúrgicamente ({reemplazos} bloque(s) actualizado(s))."


# =============================================================================
# LECTOR ÚNICO PERSISTENTE DE CONSOLA (EVITA BLOQUEO DE STDIN EN WINDOWS)
# =============================================================================
CONSOLE_LINE_QUEUE: "queue.Queue[str]" = queue.Queue()
WAITING_CONFIRMATION_EVENT = threading.Event()
CONFIRMATION_RESPONSE_QUEUE: "queue.Queue[Tuple[str, str]]" = queue.Queue()


def _console_stdin_daemon() -> None:
    while True:
        try:
            linea = sys.stdin.readline()
            if not linea:
                CONSOLE_LINE_QUEUE.put("__EOF__")
                break
            limpia = linea.rstrip("\r\n")
            if WAITING_CONFIRMATION_EVENT.is_set():
                CONFIRMATION_RESPONSE_QUEUE.put(("consola", limpia.strip()))
            else:
                CONSOLE_LINE_QUEUE.put(limpia)
        except Exception as e:
            log_event("STDIN", f"Error en lector stdin: {e}", "WARN")
            time.sleep(0.2)


STDIN_THREAD = threading.Thread(target=_console_stdin_daemon, daemon=True, name="ConsoleStdinDaemon")
STDIN_THREAD.start()


def leer_linea_consola_sincrona(prompt_txt: str = "", timeout_s: Optional[float] = None) -> str:
    """Lee una línea desde `CONSOLE_LINE_QUEUE` de forma segura para sub-menús como `/edit` o `/voice`."""
    if prompt_txt:
        print(prompt_txt, end="", flush=True)
    try:
        val = CONSOLE_LINE_QUEUE.get(timeout=timeout_s)
        return "" if val == "__EOF__" else val
    except queue.Empty:
        return ""


# =============================================================================
# DIAGNÓSTICO DE CONTENEDORES DOCKER Y GESTIÓN DE 6GB VRAM (ISPIRADO EN MVP)
# =============================================================================
def check_tcp_port(ip: str, port: int, timeout_s: float = 1.5) -> Tuple[bool, Optional[int]]:
    t0 = time.perf_counter()
    try:
        with socket.create_connection((ip, port), timeout=timeout_s):
            ms = round((time.perf_counter() - t0) * 1000)
            return True, ms
    except Exception:
        return False, None


def obtener_modelos_en_vram(api_base: str) -> List[Dict[str, Any]]:
    try:
        r = HTTP.get(f"{api_base.rstrip('/')}/ps", timeout=(3, 5))
        if r.status_code == 200:
            modelos = r.json().get("models", []) or []
            res = []
            for m in modelos:
                sz = int(m.get("size_vram") or m.get("size") or 0)
                res.append({
                    "name": m.get("name", "unknown"),
                    "vram_gb": round(sz / (1024 ** 3), 2) if sz > 0 else 0.0,
                })
            return res
    except Exception:
        pass
    return []


def liberar_vram_ollama(api_base: str, fallback_models: Optional[List[str]] = None) -> List[str]:
    """Envía `keep_alive: 0` a todos los modelos cargados en Ollama para liberar los 6GB de VRAM."""
    cargados = obtener_modelos_en_vram(api_base)
    nombres = [m["name"] for m in cargados if m.get("name")]
    if fallback_models:
        for fm in fallback_models:
            if fm and fm not in nombres:
                nombres.append(fm)

    descargados: List[str] = []
    gen_url = f"{api_base.rstrip('/')}/generate"
    for nombre in nombres:
        try:
            HTTP.post(gen_url, json={"model": nombre, "keep_alive": 0}, timeout=(3, 10))
            descargados.append(nombre)
        except Exception:
            pass
    log_event("VRAM_FREE", f"Modelos descargados de VRAM: {descargados}")
    return descargados


def reporte_salud_cluster(api_base: str) -> str:
    servicios = [
        ("👂 Oído (Whisper STT :8000)", IP_WINDOWS_GPU, 8000),
        ("🧠 Cerebro (Ollama LLM :11434)", IP_WINDOWS_GPU, 11434),
        ("🗣️ Voz (Motor TTS :5050)", IP_WINDOWS_GPU, 5050),
        ("🎨 Imagen (Stable Diffusion :7860)", IP_WINDOWS_GPU, 7860),
    ]
    lineas = [f"\n{C.BOLD}{C.CYAN}=== ESTADO DE SALUD DEL CLÚSTER MULTIMODAL ({IP_WINDOWS_GPU}) ==={C.RESET}"]
    for etiqueta, ip, puerto in servicios:
        ok, ms = check_tcp_port(ip, puerto)
        estado = f"{C.GREEN}ONLINE ({ms} ms){C.RESET}" if ok else f"{C.RED}OFFLINE{C.RESET}"
        lineas.append(f"  • {etiqueta:<36}: {estado}")

    en_vram = obtener_modelos_en_vram(api_base)
    if en_vram:
        vram_str = ", ".join(f"{m['name']} ({m['vram_gb']} GB)" for m in en_vram)
        lineas.append(f"  • 🔥 Modelos activos en VRAM         : {C.YELLOW}{vram_str}{C.RESET}")
    else:
        lineas.append(f"  • ❄️ Memoria de Video (VRAM)        : {C.GREEN}Libre (0 modelos retenidos){C.RESET}")
    return "\n".join(lineas)


# =============================================================================
# PUENTE BIDIRECCIONAL CON TELEGRAM (TEXTO + FOTOS + VOZ) Y `chat_db.json`
# =============================================================================
class WebChatDBBridge:
    def __init__(self, db_path: Path, inbox_queue: "queue.Queue[Tuple[str, str]]"):
        self.db_path = db_path
        self.inbox = inbox_queue
        self._last_seen_id: float = time.time()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self.db_path.is_file():
            try:
                items = json.loads(self.db_path.read_text(encoding="utf-8", errors="replace")) or []
                if items and isinstance(items, list):
                    self._last_seen_id = max(float(m.get("id", 0.0)) for m in items if isinstance(m, dict))
            except Exception:
                pass
        self._thread = threading.Thread(target=self._watch_loop, daemon=True, name="WebChatDBWatcher")
        self._thread.start()
        log_event("WEBCHAT_DB", f"Watcher iniciado sobre {self.db_path}")

    def post_message(self, text: str, sender: str = ADMIN_WEB_HANDLE) -> bool:
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            if not self.db_path.exists():
                self.db_path.write_text("[]", encoding="utf-8")

            raw = self.db_path.read_text(encoding="utf-8", errors="replace")
            chat = json.loads(raw) if raw.strip() else []
            if not isinstance(chat, list):
                chat = []

            msg_id = round(time.time(), 4)
            msg = {
                "id": msg_id,
                "type": "chat",
                "name": html.escape(sender),
                "message": html.escape(text),
            }
            chat.append(msg)
            if len(chat) > 60:
                chat = chat[-60:]

            self._last_seen_id = max(self._last_seen_id, msg_id)
            escribir_archivo_atomico(self.db_path, json.dumps(chat, ensure_ascii=False))
            return True
        except Exception as e:
            auditar("webchat_error", str(e), "post_failed")
            return False

    def _watch_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                if self.db_path.is_file():
                    raw = self.db_path.read_text(encoding="utf-8", errors="replace")
                    chat = json.loads(raw) if raw.strip() else []
                    if isinstance(chat, list):
                        for m in chat:
                            if not isinstance(m, dict):
                                continue
                            mid = float(m.get("id", 0.0))
                            if mid > self._last_seen_id:
                                self._last_seen_id = mid
                                sender = str(m.get("name", ""))
                                body = html.unescape(str(m.get("message", ""))).strip()
                                if sender.lower() != ADMIN_WEB_HANDLE.lower() and body:
                                    log_event("WEBCHAT_IN", f"De {sender}: {body[:120]}")
                                    if body.lower().startswith("@aryi"):
                                        clean_task = body[5:].strip()
                                        if clean_task:
                                            self.inbox.put(("webchat", f"[Visitante Web {sender}]: {clean_task}"))
            except Exception:
                pass
            time.sleep(1.0)


class TelegramBridge:
    """
    Puente bidireccional con Telegram:
    - Recibe mensajes de texto, FOTOS (`photo` -> las descarga para análisis de Visión)
      y NOTAS DE VOZ (`voice` -> las descarga para transcripción en Whisper STT).
    - Envía texto, fotos generadas por Stable Diffusion (`sendPhoto`) y audios TTS (`sendVoice`).
    """

    def __init__(self, token: str, allowed_chat_id: str, web_bridge: Optional[WebChatDBBridge] = None):
        self.token = token.strip()
        self.chat_id = str(allowed_chat_id).strip()
        self.enabled = bool(self.token)
        self.web_bridge = web_bridge
        self.inbox: "queue.Queue[Tuple[str, str]]" = queue.Queue()
        self.outbox: "queue.Queue[str]" = queue.Queue()
        self._stop_event = threading.Event()
        self._offset = 0
        self._poll_thread: Optional[threading.Thread] = None
        self._send_thread: Optional[threading.Thread] = None
        self._http_poll = requests.Session()
        self._http_send = requests.Session()

    def start(self) -> None:
        if not self.enabled:
            return
        self._send_thread = threading.Thread(target=self._send_loop, daemon=True, name="TelegramSender")
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True, name="TelegramPoller")
        self._send_thread.start()
        self._poll_thread.start()
        print(f"{C.GREEN}[TELEGRAM] Bridge Multimodal activo en segundo plano (Chat ID: {self.chat_id}).{C.RESET}")
        log_event("TELEGRAM", f"Bridge iniciado para Chat ID {self.chat_id}")
        if self.chat_id:
            self.send(
                "🤖 ARYI OMEGA v10.0 (Multimodal Terminal & Vision/Voice/SD Suite) en línea.\n"
                "Novedades:\n"
                "• Envíame una FOTO aquí y la describiré con los modelos de Visión.\n"
                "• Envíame una NOTA DE VOZ y la transcribiré con Whisper STT.\n"
                "• Usa `/imagine <prompt>` para crear imágenes con Stable Diffusion.\n"
                "• Usa `/vision <ruta>` o `/screenshot` para analizar imágenes/pantalla.\n"
                "• Usa `/files`, `/cat`, `/edit` para usar el Archivador Completo."
            )

    def stop(self) -> None:
        self._stop_event.set()

    def send(self, text: str) -> None:
        if not self.enabled or not self.chat_id or not text:
            return
        self.outbox.put(str(text))

    def send_photo(self, photo_path: Path, caption: str = "") -> bool:
        if not self.enabled or not self.chat_id or not photo_path.is_file():
            return False
        url = f"https://api.telegram.org/bot{self.token}/sendPhoto"
        try:
            with open(photo_path, "rb") as f:
                r = self._http_send.post(
                    url,
                    data={"chat_id": self.chat_id, "caption": caption[:950]},
                    files={"photo": (photo_path.name, f, "image/png")},
                    timeout=(5, 25),
                )
            log_event("TG_PHOTO_OUT", f"{photo_path.name} -> HTTP {r.status_code}")
            return r.status_code == 200
        except Exception as e:
            log_event("TG_PHOTO_ERR", str(e), "WARN")
            return False

    def send_audio(self, audio_path: Path, caption: str = "") -> bool:
        if not self.enabled or not self.chat_id or not audio_path.is_file():
            return False
        url = f"https://api.telegram.org/bot{self.token}/sendAudio"
        try:
            with open(audio_path, "rb") as f:
                r = self._http_send.post(
                    url,
                    data={"chat_id": self.chat_id, "caption": caption[:900]},
                    files={"audio": (audio_path.name, f, "audio/wav")},
                    timeout=(5, 25),
                )
            return r.status_code == 200
        except Exception:
            return False

    def _download_telegram_file(self, file_id: str, dest_dir: Path, prefix: str, default_ext: str) -> Optional[Path]:
        try:
            r_meta = self._http_poll.get(
                f"https://api.telegram.org/bot{self.token}/getFile",
                params={"file_id": file_id},
                timeout=(5, 10),
            )
            if r_meta.status_code != 200:
                return None
            file_path_tg = (r_meta.json().get("result") or {}).get("file_path", "")
            if not file_path_tg:
                return None
            ext = Path(file_path_tg).suffix or default_ext
            local_file = dest_dir / f"{prefix}_{time.strftime('%Y%m%d_%H%M%S')}{ext}"
            r_bin = self._http_poll.get(
                f"https://api.telegram.org/file/bot{self.token}/{file_path_tg}",
                timeout=(5, 30),
            )
            if r_bin.status_code == 200:
                local_file.write_bytes(r_bin.content)
                return local_file
        except Exception as e:
            log_event("TG_DL_ERR", f"Error descargando archivo de Telegram: {e}", "WARN")
        return None

    def _send_loop(self) -> None:
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        while not self._stop_event.is_set():
            try:
                text = self.outbox.get(timeout=0.5)
            except queue.Empty:
                continue
            fragmentos = [text[i : i + 3800] for i in range(0, len(text), 3800)] or [text]
            for frag in fragmentos:
                try:
                    r = self._http_send.post(
                        url,
                        json={"chat_id": self.chat_id, "text": frag},
                        timeout=(4, 8),
                    )
                    log_event("TG_OUT", f"Enviado ({len(frag)} chars) -> HTTP {r.status_code}")
                except Exception as e:
                    log_event("TG_ERR", f"Fallo al enviar mensaje a Telegram: {e}", "WARN")

    def _poll_loop(self) -> None:
        url = f"https://api.telegram.org/bot{self.token}/getUpdates"
        while not self._stop_event.is_set():
            try:
                r = self._http_poll.get(url, params={"offset": self._offset, "timeout": 15}, timeout=(5, 20))
                if r.status_code != 200:
                    time.sleep(3)
                    continue
                data = r.json()
                for item in data.get("result", []):
                    self._offset = item["update_id"] + 1
                    msg = item.get("message") or {}
                    chat = str((msg.get("chat") or {}).get("id", ""))
                    if not chat:
                        continue
                    if not self.chat_id:
                        self.chat_id = chat
                        self.send(f"✅ Chat vinculado (ID: {self.chat_id}).")
                    elif chat != self.chat_id:
                        continue

                    # 1. ¿El usuario envió una FOTO por Telegram? -> Descargar y encolar comando `/vision`
                    photos = msg.get("photo")
                    if isinstance(photos, list) and photos:
                        best_photo = photos[-1]
                        fid = best_photo.get("file_id", "")
                        caption = (msg.get("caption") or "Describe detalladamente esta imagen en español.").strip()
                        saved_img = self._download_telegram_file(fid, RENDERS_DIR, "tg_photo", ".jpg")
                        if saved_img:
                            log_event("TG_PHOTO_IN", f"Foto recibida en Telegram: {saved_img}")
                            self.inbox.put(("telegram", f"/vision \"{saved_img}\" {caption}"))
                            continue

                    # 2. ¿El usuario envió una NOTA DE VOZ o AUDIO por Telegram? -> Descargar y transcribir
                    voice_obj = msg.get("voice") or msg.get("audio")
                    if isinstance(voice_obj, dict) and voice_obj.get("file_id"):
                        saved_aud = self._download_telegram_file(voice_obj["file_id"], AUDIO_DIR, "tg_voice", ".ogg")
                        if saved_aud:
                            log_event("TG_VOICE_IN", f"Audio recibido en Telegram: {saved_aud}")
                            self.inbox.put(("telegram_voice", str(saved_aud)))
                            continue

                    texto = (msg.get("text") or "").strip()
                    if not texto:
                        continue

                    log_event("TG_IN", f"Recibido de {chat}: {texto[:150]}")
                    low = texto.lower()

                    if low.startswith("/web ") and self.web_bridge:
                        respuesta_web = texto[5:].strip()
                        if respuesta_web and self.web_bridge.post_message(respuesta_web, sender=ADMIN_WEB_HANDLE):
                            self.send(f"💬 Enviado a chat_monolitico.php ({ADMIN_WEB_HANDLE}):\n{respuesta_web}")
                        else:
                            self.send("❌ No se pudo escribir en chat_db.json.")
                        continue

                    if WAITING_CONFIRMATION_EVENT.is_set():
                        CONFIRMATION_RESPONSE_QUEUE.put(("telegram", texto))
                    else:
                        self.inbox.put(("telegram", texto))
            except Exception as e:
                log_event("TG_POLL_ERR", f"Reintentando long-polling ({e})", "DEBUG")
                time.sleep(2)


SHARED_INBOX: "queue.Queue[Tuple[str, str]]" = queue.Queue()
WEB_CHAT = WebChatDBBridge(CHAT_DB_FILE, SHARED_INBOX)
TELEGRAM = TelegramBridge(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, web_bridge=WEB_CHAT)
TELEGRAM.inbox = SHARED_INBOX


def pedir_confirmacion(pregunta: str) -> bool:
    global AUTO_APPROVE
    if AUTO_APPROVE:
        print(f"{C.GREEN}  [AUTO-APPROVE] Autorizado automáticamente.{C.RESET}")
        log_event("AUTH", f"Auto-aprobado: {pregunta[:120]}")
        return True

    while not CONFIRMATION_RESPONSE_QUEUE.empty():
        try:
            CONFIRMATION_RESPONSE_QUEUE.get_nowait()
        except queue.Empty:
            break

    WAITING_CONFIRMATION_EVENT.set()
    try:
        if TELEGRAM.enabled and TELEGRAM.chat_id:
            TELEGRAM.send(
                f"⚠️ Autorización requerida:\n{pregunta}\n\n"
                "Responde `si` (`/approve`), `no` (`/deny`) o `auto`."
            )

        print(f"{C.YELLOW}{pregunta}{C.RESET}")
        print(
            f"{C.YELLOW}¿Autorizar acción? [s/N/auto] (también puedes responder por Telegram): {C.RESET}",
            end="",
            flush=True,
        )

        while True:
            try:
                origen, raw_resp = CONFIRMATION_RESPONSE_QUEUE.get(timeout=0.2)
            except queue.Empty:
                continue

            low = raw_resp.strip().lower()
            log_event("AUTH_INPUT", f"Respuesta desde {origen}: '{low[:80]}'")

            if origen == "telegram":
                print(f"\n{C.CYAN}[TELEGRAM] Respuesta recibida: {raw_resp}{C.RESET}")

            if low in {"auto", "/auto", "/auto on"}:
                AUTO_APPROVE = True
                print(f"{C.GREEN}[SISTEMA] Modo AUTO-APPROVE activado para el resto de la sesión.{C.RESET}")
                if TELEGRAM.enabled:
                    TELEGRAM.send("✅ Modo AUTO-APPROVE activado.")
                return True

            if low in {"s", "si", "sí", "y", "yes", "ok", "/approve", "aprobar"}:
                return True

            if low in {"", "n", "no", "/deny", "cancel", "cancelar"}:
                return False

            print(
                f"\n{C.YELLOW}[SISTEMA] Entrada detectada como nuevo mensaje/comando. "
                f"Omitiendo acción pendiente y procesando tu mensaje...{C.RESET}"
            )
            SHARED_INBOX.put((origen, raw_resp))
            return False
    finally:
        WAITING_CONFIRMATION_EVENT.clear()


# =============================================================================
# 1. MOTOR DE TELEMETRÍA Y CLASIFICACIÓN CORE DE MODELOS (INCLUYE VISIÓN)
# =============================================================================
@dataclass
class ModelTelemetry:
    name: str
    size_gb: float = 0.0
    parameter_size: str = "unknown"
    quantization: str = "unknown"
    family: str = "unknown"
    context_limit: int = 8192
    load_time_s: float = 0.0
    ttft_s: float = 0.0
    tokens_per_sec: float = 0.0
    coding_score: float = 0.0
    reasoning_score: float = 0.0
    core_features: List[str] = field(default_factory=list)
    tier: str = "general"
    last_tested: str = ""


def estimar_parametros_b(name: str, param_size_str: str = "") -> float:
    combined = f"{name} {param_size_str}"
    m = re.search(r"(\d+(?:\.\d+)?)\s*[bB]\b", combined)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return 7.0


def calcular_contexto_seguro_vram(name: str, size_gb: float, param_b: float) -> int:
    if param_b >= 25.0 or size_gb >= 14.0 or "gguf" in name.lower():
        return 8192
    if param_b >= 7.0 or size_gb >= 4.5:
        return 16384
    return 16384


class TelemetryEngine:
    def __init__(self, api_base: str):
        self.api_base = api_base.rstrip("/")
        self.models: Dict[str, ModelTelemetry] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        if TELEMETRY_FILE.is_file():
            try:
                raw = json.loads(TELEMETRY_FILE.read_text(encoding="utf-8"))
                for k, v in raw.items():
                    m = ModelTelemetry(**v)
                    pb = estimar_parametros_b(m.name, m.parameter_size)
                    safe_ctx = calcular_contexto_seguro_vram(m.name, m.size_gb, pb)
                    if m.context_limit > safe_ctx:
                        m.context_limit = safe_ctx
                    self.models[k] = m
            except Exception:
                pass

    def save_cache(self) -> None:
        try:
            data = {k: asdict(v) for k, v in self.models.items()}
            escribir_archivo_atomico(TELEMETRY_FILE, json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"{C.RED}[TELEMETRÍA] Error guardando caché: {e}{C.RESET}")

    def fetch_available_models(self) -> List[Dict[str, Any]]:
        try:
            r = HTTP.get(f"{self.api_base}/tags", timeout=(TIMEOUT_HTTP_CONNECT, 15))
            r.raise_for_status()
            return r.json().get("models", [])
        except Exception as e:
            print(f"{C.RED}[ERROR OLLAMA] No se pudo conectar con {self.api_base}/tags: {e}{C.RESET}")
            return []

    def benchmark_model(self, model_meta: Dict[str, Any]) -> ModelTelemetry:
        name = model_meta.get("name", "unknown")
        size_bytes = model_meta.get("size", 0)
        size_gb = round(size_bytes / (1024 ** 3), 2) if size_bytes else 0.0
        details = model_meta.get("details", {}) or {}
        param_size = details.get("parameter_size", "unknown")
        quant = details.get("quantization_level", "unknown")
        family = details.get("family", "unknown")
        param_b = estimar_parametros_b(name, param_size)
        ctx = calcular_contexto_seguro_vram(name, size_gb, param_b)

        print(f"  {C.CYAN}⚡ Probando modelo:{C.RESET} {C.BOLD}{name}{C.RESET} ({size_gb} GB | {param_size} | safe_ctx={ctx})...")
        log_event("TELEMETRY", f"Iniciando benchmark de {name} ({size_gb} GB)")

        test_prompt = (
            "Responde UNICAMENTE con un objeto JSON válido con dos claves: "
            "\"fib\": una lista con los primeros 6 números de Fibonacci empezando en 0, y "
            "\"git_cmd\": el comando exacto de git para crear y cambiar a una rama llamada 'feat/core'."
        )
        t0 = time.perf_counter()
        ttft = 0.0
        full_resp = ""
        eval_count = 0
        eval_duration_ns = 0
        load_duration_ns = 0

        try:
            with HTTP.post(
                f"{self.api_base}/generate",
                json={
                    "model": name,
                    "prompt": test_prompt,
                    "stream": True,
                    "options": {"temperature": 0.0, "num_predict": 120, "num_ctx": 2048},
                },
                stream=True,
                timeout=(TIMEOUT_HTTP_CONNECT, 150),
            ) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line:
                        continue
                    pkt = json.loads(line)
                    chunk = pkt.get("response", "")
                    if chunk and ttft == 0.0:
                        ttft = round(time.perf_counter() - t0, 3)
                    full_resp += chunk
                    if pkt.get("done"):
                        eval_count = pkt.get("eval_count", 0)
                        eval_duration_ns = pkt.get("eval_duration", 0)
                        load_duration_ns = pkt.get("load_duration", 0)
                        break
        except Exception as e:
            print(f"    {C.RED}✗ Falló prueba en {name}: {e}{C.RESET}")
            return ModelTelemetry(
                name=name,
                size_gb=size_gb,
                parameter_size=param_size,
                quantization=quant,
                family=family,
                context_limit=4096,
                core_features=["offline_or_failed"],
                tier="offline",
                last_tested=time.strftime("%Y-%m-%d %H:%M:%S"),
            )

        total_elapsed = max(0.001, time.perf_counter() - t0)
        load_s = round(load_duration_ns / 1e9, 3) if load_duration_ns else round(ttft * 0.6, 3)
        if eval_duration_ns > 0 and eval_count > 0:
            tps = round(eval_count / (eval_duration_ns / 1e9), 2)
        else:
            tps = round(estimar_tokens(full_resp) / max(0.1, total_elapsed - load_s), 2)

        coding_score = 40.0
        reasoning_score = 40.0
        low_resp = full_resp.lower()
        if "0, 1, 1, 2, 3, 5" in low_resp or "[0,1,1,2,3,5]" in low_resp.replace(" ", ""):
            reasoning_score += 45.0
        if "checkout -b" in low_resp or "switch -c" in low_resp:
            coding_score += 45.0
        if "{" in full_resp and "}" in full_resp:
            reasoning_score += 15.0
            coding_score += 15.0

        low_name = name.lower()
        features: List[str] = []

        if any(v in low_name for v in ("vision", "llava", "minicpm", "moondream")):
            features.append("vision_multimodal")

        if any(c in low_name for c in ("coder", "codellama", "deepseek-coder", "starcoder", "qwen2.5-coder", "qwen3-coder")):
            features.append("code_generation")
            features.append("refactoring")
            coding_score = min(100.0, coding_score + 15.0)

        if param_b <= 1.5:
            reasoning_score = min(reasoning_score, 62.0)
            coding_score = min(coding_score, 68.0)

        if param_b >= 12.0 or any(k in low_name for k in ("nemotron", "deepseek-r1", "qwq", "gemma2:27b", "llama3.1:70b", "qwen3", "ornith")):
            features.extend(["system_architecture", "deep_reasoning", "team_orchestration", "god_level_analysis"])
            reasoning_score = min(100.0, reasoning_score + 15.0)
        elif param_b >= 6.0:
            features.extend(["system_architecture", "full_stack_dev", "qa_audit", "framework_learning"])
        else:
            features.extend(["fast_routing", "gitops_commits", "quick_triage"])

        if tps >= 45.0:
            features.append("ultra_fast_inference")
        elif tps >= 20.0:
            features.append("realtime_interactive")

        if "vision_multimodal" in features:
            tier = "vision_specialist"
        elif "code_generation" in features and param_b >= 3.0:
            tier = "coding_god"
        elif param_b >= 8.0 or ("system_architecture" in features and reasoning_score >= 85):
            tier = "god_architect"
        elif param_b <= 2.5 or tps >= 60.0:
            tier = "fast_git_operator"
        else:
            tier = "qa_and_research"

        telem = ModelTelemetry(
            name=name,
            size_gb=size_gb,
            parameter_size=param_size,
            quantization=quant,
            family=family,
            context_limit=ctx,
            load_time_s=load_s,
            ttft_s=ttft,
            tokens_per_sec=tps,
            coding_score=round(coding_score, 1),
            reasoning_score=round(reasoning_score, 1),
            core_features=sorted(list(set(features))),
            tier=tier,
            last_tested=time.strftime("%Y-%m-%d %H:%M:%S"),
        )
        print(
            f"    {C.GREEN}✓ Clasificado:{C.RESET} Tier={C.BOLD}{tier}{C.RESET} | "
            f"TPS={C.YELLOW}{tps} tok/s{C.RESET} | TTFT={ttft}s | "
            f"Code={coding_score:.0f}% | Reason={reasoning_score:.0f}% | "
            f"SafeCtx={ctx}"
        )
        return telem

    def run_full_telemetry(self, force: bool = False) -> Dict[str, ModelTelemetry]:
        raw_models = self.fetch_available_models()
        if not raw_models:
            return self.models

        print(f"\n{C.BOLD}{C.MAGENTA}=== INICIANDO PRUEBA TELEMÉTRICA Y CLASIFICACIÓN CORE DE MODELOS ==={C.RESET}")
        names_online = {m.get("name", "") for m in raw_models if m.get("name")}

        for m_meta in raw_models:
            name = m_meta.get("name")
            if not name:
                continue
            if not force and name in self.models and self.models[name].tier != "offline":
                cached = self.models[name]
                print(
                    f"  {C.DIM}• [Caché Telemétrica] {name:<38} -> Tier: {cached.tier:<18} "
                    f"({cached.tokens_per_sec} tok/s | safe_ctx {cached.context_limit}){C.RESET}"
                )
                continue
            self.models[name] = self.benchmark_model(m_meta)

        for k in list(self.models.keys()):
            if k not in names_online:
                del self.models[k]

        self.save_cache()
        print(f"{C.BOLD}{C.MAGENTA}=== TELEMETRÍA COMPLETADA ({len(self.models)} modelos perfilados) ==={C.RESET}\n")
        return self.models

    def rank_models_for_role(self, role: str) -> List[ModelTelemetry]:
        if role == "vision":
            vis = [m for m in self.models.values() if m.tier == "vision_specialist" and m.tokens_per_sec > 0]
            if vis:
                return sorted(vis, key=lambda m: (m.reasoning_score + m.coding_score, m.tokens_per_sec), reverse=True)
            # Fallback por nombre si aún no se probó
            return [ModelTelemetry(name="llava-phi3:latest", context_limit=4096), ModelTelemetry(name="moondream:latest", context_limit=4096)]

        valid = [m for m in self.models.values() if m.tier != "offline" and "vision" not in m.tier and m.tokens_per_sec >= 3.0]
        if not valid:
            valid = [m for m in self.models.values() if m.tier != "offline" and "vision" not in m.tier]
        if not valid:
            all_m = [m for m in self.models.values() if m.tier != "offline"]
            return all_m or [ModelTelemetry(name="qwen2.5-coder:7b", context_limit=8192)]

        if role == "coder":
            return sorted(
                valid,
                key=lambda m: (
                    1 if "code_generation" in m.core_features else 0,
                    m.coding_score,
                    m.tokens_per_sec,
                    -m.ttft_s,
                ),
                reverse=True,
            )
        if role == "architect":
            return sorted(
                valid,
                key=lambda m: (
                    m.reasoning_score + m.coding_score,
                    1 if "god_level_analysis" in m.core_features else 0,
                    m.tokens_per_sec,
                    -m.ttft_s,
                ),
                reverse=True,
            )
        if role in ("gitops", "fast"):
            return sorted(
                valid,
                key=lambda m: (
                    1 if m.coding_score >= 80 else 0,
                    m.tokens_per_sec,
                    -m.ttft_s,
                ),
                reverse=True,
            )
        if role == "qa":
            return sorted(
                valid,
                key=lambda m: (
                    1 if m.size_gb >= 2.0 else 0,
                    m.reasoning_score + m.coding_score,
                    m.tokens_per_sec,
                ),
                reverse=True,
            )
        return sorted(
            valid,
            key=lambda m: (
                1 if m.size_gb >= 2.0 else 0,
                m.reasoning_score,
                m.tokens_per_sec,
            ),
            reverse=True,
        )

    def select_best_model_for_role(self, role: str) -> Tuple[str, int]:
        ranked = self.rank_models_for_role(role)
        best = ranked[0]
        return best.name, best.context_limit

    def summary_table(self) -> str:
        if not self.models:
            return "No hay modelos registrados en telemetría."
        lines = [
            f"{'MODELO':<36} | {'TIER CORE':<18} | {'TPS':>8} | {'TTFT':>6} | {'CODE':>5} | {'REASON':>6} | {'CTX':>6}",
            "-" * 100,
        ]
        for m in self.models.values():
            lines.append(
                f"{m.name[:36]:<36} | {m.tier:<18} | {m.tokens_per_sec:>6.1f}/s | "
                f"{m.ttft_s:>5.2f}s | {m.coding_score:>4.0f}% | {m.reasoning_score:>5.0f}% | {m.context_limit:>6}"
            )
        return "\n".join(lines)


# =============================================================================
# 2. MÓDULOS MULTIMODALES: VISIÓN, STABLE DIFFUSION Y VOZ (WHISPER STT + TTS)
# =============================================================================
def _render_imagen_ansi_consola(img_path: Path, ancho_cols: int = 56) -> str:
    """
    Si Pillow (`PIL`) está instalado en el entorno, renderiza una vista previa a todo color
    en bloques ANSI de media altura (`▀`) directamente en la terminal de Windows.
    """
    try:
        from PIL import Image  # type: ignore

        with Image.open(img_path) as im:
            im = im.convert("RGB")
            w, h = im.size
            nuevo_w = max(16, min(ancho_cols, 72))
            nuevo_h = max(8, int((h / max(1, w)) * nuevo_w * 0.95))
            if nuevo_h % 2 != 0:
                nuevo_h += 1
            im = im.resize((nuevo_w, nuevo_h))
            px = im.load()
            lineas_ansi: List[str] = []
            for y in range(0, nuevo_h, 2):
                fila = ["  "]
                for x in range(nuevo_w):
                    r1, g1, b1 = px[x, y]
                    r2, g2, b2 = px[x, y + 1]
                    fila.append(f"\033[38;2;{r1};{g1};{b1}m\033[48;2;{r2};{g2};{b2}m▀")
                fila.append(C.RESET)
                lineas_ansi.append("".join(fila))
            return "\n".join(lineas_ansi)
    except Exception:
        return ""


def capturar_pantalla_windows() -> Optional[Path]:
    """Captura la pantalla principal de Windows usando PowerShell (.NET System.Drawing) sin librerías externas."""
    destino = RENDERS_DIR / f"screenshot_{time.strftime('%Y%m%d_%H%M%S')}.png"
    if not IS_WINDOWS:
        return None
    ps_script = (
        "Add-Type -AssemblyName System.Windows.Forms,System.Drawing; "
        "$b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "
        "$bmp = New-Object System.Drawing.Bitmap($b.Width, $b.Height); "
        "$g = [System.Drawing.Graphics]::FromImage($bmp); "
        "$g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size); "
        f"$bmp.Save('{str(destino)}', [System.Drawing.Imaging.ImageFormat]::Png); "
        "$g.Dispose(); $bmp.Dispose();"
    )
    rc, _, _ = ejecutar_comando_sistema(ps_script, usar_powershell=True)
    if rc == 0 and destino.is_file():
        log_event("SCREENSHOT", f"Captura guardada en {destino}")
        return destino
    return None


def describir_imagen_con_vision(
    ruta_imagen_str: str,
    pregunta: str,
    telemetry: TelemetryEngine,
) -> str:
    """
    Analiza cualquier imagen local (PNG, JPG, WEBP) usando los modelos `vision_specialist`
    de tu clúster (`llava-phi3:latest`, `moondream:latest`) con Auto-Failover.
    """
    ruta_img = ruta_permitida(ruta_imagen_str)
    if not ruta_img.is_file():
        return f"❌ No se encontró el archivo de imagen: {ruta_img}"

    img_b64 = base64.b64encode(ruta_img.read_bytes()).decode("ascii")
    candidatos_vis = [m.name for m in telemetry.rank_models_for_role("vision")]
    prompt_final = (pregunta or "Describe detalladamente todo lo que ves en esta imagen en español.").strip()

    # Mostrar miniatura ANSI en la terminal si PIL está disponible
    preview_ansi = _render_imagen_ansi_consola(ruta_img)
    if preview_ansi:
        print(f"\n{preview_ansi}")

    for modelo_vis in candidatos_vis:
        print(f"\n{C.MAGENTA}👁️ [VISIÓN MULTIMODAL · {modelo_vis}] Analizando imagen '{ruta_img.name}'...{C.RESET}")
        log_event("VISION_START", f"Analizando {ruta_img.name} con {modelo_vis}")
        t0 = time.perf_counter()
        try:
            with GPU_INFERENCE_LOCK:
                with HTTP.post(
                    f"{telemetry.api_base}/generate",
                    json={
                        "model": modelo_vis,
                        "prompt": prompt_final,
                        "images": [img_b64],
                        "stream": True,
                        "options": {"temperature": 0.2, "num_ctx": 4096},
                    },
                    stream=True,
                    timeout=(TIMEOUT_HTTP_CONNECT, 180),
                ) as r:
                    if r.status_code >= 400:
                        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
                    partes: List[str] = []
                    for linea in r.iter_lines():
                        if not linea:
                            continue
                        pkt = json.loads(linea)
                        chunk = pkt.get("response", "")
                        if chunk:
                            print(chunk, end="", flush=True)
                            partes.append(chunk)
                        if pkt.get("done"):
                            break
                    print()
                    texto_desc = "".join(partes).strip()
                    if texto_desc:
                        dur = time.perf_counter() - t0
                        auditar("vision_describe", str(ruta_img), f"OK en {dur:.1f}s con {modelo_vis}")
                        return f"👁️ [Análisis Visual con {modelo_vis} ({dur:.1f}s) · {ruta_img.name}]:\n{texto_desc}"
        except Exception as e:
            print(f"{C.YELLOW}  [AVISO VISIÓN] Falló '{modelo_vis}' ({e}). Probando siguiente modelo de visión...{C.RESET}")
            log_event("VISION_RETRY", f"Fallo en {modelo_vis}: {e}", "WARN")

    return f"❌ Ninguno de los modelos de visión ({', '.join(candidatos_vis)}) pudo procesar la imagen."


def generar_imagen_stable_diffusion(
    prompt_usuario: str,
    telemetry: TelemetryEngine,
    width: int = 512,
    height: int = 512,
    steps: int = 20,
    cfg_scale: float = 7.0,
    optimizar_ingles: bool = True,
    liberar_vram: bool = True,
    abrir_en_windows: bool = True,
) -> str:
    """
    Pipeline completo de Stable Diffusion inspirado en tu `area_privada.php`:
    1. Usa un modelo rápido de Ollama para traducir y enriquecer el prompt al inglés con tags 8k.
    2. Descarga todos los modelos de Ollama de los 6GB de VRAM (`keep_alive: 0`).
    3. Llama a `http://100.115.1.71:7860/sdapi/v1/txt2img`.
    4. Guarda el PNG en `.aryi_renders/`, muestra preview ANSI en consola, lo envía a Telegram y lo abre.
    """
    prompt_usuario = prompt_usuario.strip()
    if not prompt_usuario:
        return "❌ El prompt para Stable Diffusion está vacío."

    sd_prompt = prompt_usuario
    fast_model, _ = telemetry.select_best_model_for_role("fast")

    if optimizar_ingles:
        print(f"\n{C.CYAN}🎨 [SD PIPELINE · Paso 1/3] Optimizando prompt visual al inglés con '{fast_model}'...{C.RESET}")
        instruccion_opt = (
            "Convert the following text into a vivid, high-detail English image generation prompt for Stable Diffusion. "
            "Include visual descriptors, lighting, atmosphere, camera angle, and quality tags (masterpiece, best quality, "
            "highly detailed, 8k). Output ONLY the English prompt without quotes or explanations:\n\n"
            + prompt_usuario[:800]
        )
        try:
            with GPU_INFERENCE_LOCK:
                r_opt = HTTP.post(
                    f"{telemetry.api_base}/generate",
                    json={
                        "model": fast_model,
                        "prompt": instruccion_opt,
                        "stream": False,
                        "keep_alive": 0 if liberar_vram else "5m",
                        "options": {"temperature": 0.4, "num_ctx": 1024},
                    },
                    timeout=(TIMEOUT_HTTP_CONNECT, 60),
                )
                if r_opt.status_code == 200:
                    cand = limpiar_bloques_think(r_opt.json().get("response", "")).strip(" \t\n\r\"'")
                    if cand:
                        sd_prompt = cand
                        print(f"  {C.DIM}Prompt optimizado: {sd_prompt}{C.RESET}")
        except Exception as e:
            log_event("SD_OPT_WARN", f"No se pudo optimizar prompt ({e}), usando original", "WARN")

    if liberar_vram:
        print(f"{C.CYAN}🎨 [SD PIPELINE · Paso 2/3] Liberando 6GB VRAM de Ollama (keep_alive: 0)...{C.RESET}")
        liberar_vram_ollama(telemetry.api_base, fallback_models=[fast_model])

    print(f"{C.MAGENTA}🎨 [SD PIPELINE · Paso 3/3] Renderizando en Stable Diffusion ({width}x{height}, {steps} pasos)...{C.RESET}")
    log_event("SD_RENDER", f"POST {API_SD_URL} ({width}x{height}, steps={steps}) prompt={sd_prompt[:100]}")

    t0 = time.perf_counter()
    payload_sd = {
        "prompt": sd_prompt,
        "negative_prompt": "blurry, low quality, bad anatomy, deformed, ugly, watermark, text, signature, cropped",
        "steps": max(10, min(50, int(steps))),
        "cfg_scale": float(cfg_scale),
        "width": max(256, min(1024, int(width))),
        "height": max(256, min(1024, int(height))),
    }

    try:
        with GPU_INFERENCE_LOCK:
            r_sd = HTTP.post(API_SD_URL, json=payload_sd, timeout=(TIMEOUT_HTTP_CONNECT, 300))
            if r_sd.status_code != 200:
                return f"❌ Error en Stable Diffusion (HTTP {r_sd.status_code}): {r_sd.text[:300]}"
            data_sd = r_sd.json()
            imagenes = data_sd.get("images") or []
            if not imagenes:
                return "❌ Stable Diffusion no devolvió ninguna imagen."

            img_bytes = base64.b64decode(imagenes[0])
            ts = time.strftime("%Y%m%d_%H%M%S")
            slug = re.sub(r"[^a-z0-9]+", "_", prompt_usuario.lower())[:28].strip("_") or "render"
            out_path = RENDERS_DIR / f"sd_{ts}_{slug}.png"
            out_path.write_bytes(img_bytes)
            dur = time.perf_counter() - t0
    except Exception as e:
        log_event("SD_ERR", str(e), "ERROR")
        return f"❌ Excepción conectando con Stable Diffusion ({API_SD_URL}): {e}"

    auditar("sd_generate", prompt_usuario, f"OK ({out_path.name} en {dur:.1f}s)")

    preview_ansi = _render_imagen_ansi_consola(out_path)
    if preview_ansi:
        print(f"\n{preview_ansi}")

    print(f"{C.GREEN}✅ Imagen generada en {dur:.1f}s y guardada en: {out_path}{C.RESET}")

    if TELEGRAM.enabled:
        TELEGRAM.send_photo(out_path, caption=f"🎨 Render ({dur:.1f}s): {prompt_usuario}\nPrompt: {sd_prompt[:250]}")

    if abrir_en_windows and IS_WINDOWS:
        try:
            os.startfile(str(out_path))  # type: ignore[attr-defined]
        except Exception:
            pass

    return f"🎨 Imagen generada exitosamente en {dur:.1f}s.\nArchivo local: {out_path}\nPrompt SD: {sd_prompt}"


# --- CAPTURA DE MICRÓFONO WINDOWS NATIVE + WHISPER STT + TTS ---
def grabar_microfono_windows_wav(segundos: int = 0) -> Optional[Path]:
    """
    Graba audio del micrófono en formato WAV (16kHz, 16-bit, Mono) de forma 100% nativa en Windows
    usando la API multimedia del sistema `winmm.dll` (`mciSendStringW`), sin requerir PyAudio.
    - Si `segundos > 0`: graba exactamente esa cantidad de segundos.
    - Si `segundos <= 0`: graba hasta que el usuario presione ENTER.
    """
    destino = AUDIO_DIR / f"mic_{time.strftime('%Y%m%d_%H%M%S')}.wav"

    if IS_WINDOWS:
        try:
            winmm = ctypes.windll.winmm  # type: ignore[attr-defined]

            def _mci(cmd: str) -> int:
                buf = ctypes.create_unicode_buffer(256)
                return int(winmm.mciSendStringW(cmd, buf, 254, 0))

            _mci("close aryi_mic")
            rc = _mci("open new type waveaudio alias aryi_mic")
            if rc != 0:
                raise RuntimeError(f"mciSendStringW open devolvió código {rc}")

            _mci("set aryi_mic time format ms")
            _mci("set aryi_mic bitspersample 16")
            _mci("set aryi_mic samplespersec 16000")
            _mci("set aryi_mic channels 1")
            _mci("record aryi_mic")

            if segundos > 0:
                print(f"{C.CYAN}🎙️ [MICRÓFONO ACTIVO] Grabando durante {segundos} segundos... ¡Habla ahora!{C.RESET}")
                time.sleep(segundos)
            else:
                leer_linea_consola_sincrona(
                    f"{C.CYAN}🎙️ [MICRÓFONO ACTIVO] Habla ahora y presiona [ENTER] cuando termines... {C.RESET}"
                )

            _mci("stop aryi_mic")
            _mci(f'save aryi_mic "{str(destino)}"')
            _mci("close aryi_mic")

            if destino.is_file() and destino.stat().st_size > 200:
                log_event("MIC_RECORD", f"Audio capturado en {destino} ({destino.stat().st_size} bytes)")
                return destino
        except Exception as e:
            log_event("MIC_WINMM_ERR", f"Fallo en winmm ({e}), probando fallback ffmpeg...", "WARN")

    # Fallback multiplataforma con ffmpeg si está en PATH
    if shutil.which("ffmpeg"):
        dur_s = segundos if segundos > 0 else 6
        print(f"{C.CYAN}🎙️ [MICRÓFONO FFMPEG] Grabando {dur_s}s...{C.RESET}")
        cmd = f'ffmpeg -y -f dshow -i audio="default" -t {dur_s} -ar 16000 -ac 1 "{destino}"' if IS_WINDOWS else f'ffmpeg -y -f pulse -i default -t {dur_s} -ar 16000 -ac 1 "{destino}"'
        ejecutar_comando_sistema(cmd, usar_powershell=False)
        if destino.is_file():
            return destino

    return None


def transcribir_audio_whisper(audio_path: Path) -> str:
    """Envía un archivo de audio (`.wav`, `.ogg`, `.webm`, `.mp3`) al contenedor Whisper STT (`:8000`)."""
    if not audio_path.is_file():
        return ""
    print(f"{C.CYAN}👂 [WHISPER STT] Transcribiendo audio ({audio_path.name})...{C.RESET}")
    t0 = time.perf_counter()
    try:
        mime = "audio/wav" if audio_path.suffix.lower() == ".wav" else "audio/ogg"
        with open(audio_path, "rb") as f:
            r = HTTP.post(
                API_STT_URL,
                files={"file": (audio_path.name, f, mime)},
                timeout=(TIMEOUT_HTTP_CONNECT, 90),
            )
        if r.status_code == 200:
            texto = (r.json().get("text") or "").strip()
            dur = time.perf_counter() - t0
            log_event("STT_OK", f"Transcripción en {dur:.2f}s: '{texto[:120]}'")
            return texto
        log_event("STT_ERR", f"HTTP {r.status_code}: {r.text[:200]}", "WARN")
    except Exception as e:
        log_event("STT_EXC", f"Excepción en Whisper STT: {e}", "WARN")
    return ""


def sintetizar_y_reproducir_voz(texto: str, enviar_a_telegram: bool = False) -> Optional[Path]:
    """
    Convierte texto a voz usando tu contenedor TTS (`http://100.115.1.71:5050/tts`),
    reproduce el WAV de forma nativa en Windows con `winsound` y, si el contenedor TTS
    no responde, usa automáticamente el sintetizador nativo de Windows (`SAPI.SpVoice`).
    """
    limpio = limpiar_texto_para_voz(texto)
    if not limpio:
        return None

    print(f"{C.YELLOW}🗣️ [VOZ TTS] Sintetizando respuesta...{C.RESET}")
    wav_path = AUDIO_DIR / f"tts_{time.strftime('%Y%m%d_%H%M%S')}.wav"
    t0 = time.perf_counter()

    # 1. Intentar con el contenedor Docker TTS (:5050) igual que en `area_privada.php`
    try:
        r = HTTP.post(
            API_TTS_URL,
            json={"texto": limpio},
            timeout=(4, 45),
        )
        if r.status_code == 200 and len(r.content) > 128:
            wav_path.write_bytes(r.content)
            dur = time.perf_counter() - t0
            log_event("TTS_OK", f"Audio WAV generado en {dur:.2f}s ({len(r.content)} bytes)")
            if IS_WINDOWS:
                try:
                    import winsound  # type: ignore

                    winsound.PlaySound(str(wav_path), winsound.SND_FILENAME)
                except Exception:
                    pass
            if enviar_a_telegram and TELEGRAM.enabled:
                TELEGRAM.send_audio(wav_path, caption="🗣️ Respuesta de voz de ARYI")
            return wav_path
    except Exception as e:
        log_event("TTS_FALLBACK", f"Contenedor TTS :5050 no disponible ({e}), usando Windows SAPI nativo", "INFO")

    # 2. Fallback nativo Windows SAPI.SpVoice (habla por los altavoces aunque el contenedor 5050 esté apagado)
    if IS_WINDOWS:
        safe_ps_text = limpio.replace("'", " ").replace('"', " ").replace("\n", " ")[:600]
        ps_tts = f"$s = New-Object -ComObject SAPI.SpVoice; $s.Speak('{safe_ps_text}') | Out-Null"
        ejecutar_comando_sistema(ps_tts, usar_powershell=True)
    return None


# =============================================================================
# 3. ARCHIVADOR Y EDITOR INTERACTIVO COMPLETO EN TERMINAL (SANDBOX + WORKSPACE)
# =============================================================================
class TerminalArchivador:
    """
    Reemplaza y supera cualquier archivador parcial: permite navegar, inspeccionar,
    crear, editar por líneas, buscar y reemplazar quirúrgicamente, copiar, mover y
    eliminar archivos o carpetas directamente desde comandos de terminal o Telegram.
    """

    @staticmethod
    def listar_directorio(ruta_arg: str = "") -> str:
        global CURRENT_NAV_DIR
        target = ruta_permitida(ruta_arg, base_dir=CURRENT_NAV_DIR) if ruta_arg else CURRENT_NAV_DIR
        if not target.exists():
            return f"❌ La ruta no existe: {target}"
        if target.is_file():
            return TerminalArchivador.ver_archivo_numerado(str(target), 1, 120)

        CURRENT_NAV_DIR = target
        items = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        filas = [
            f"\n{C.BOLD}{C.CYAN}📂 ARCHIVADOR COMPLETO · Ruta actual: {target}{C.RESET}",
            f"{'#':>3} | {'TIPO':<6} | {'TAMAÑO':>10} | {'MODIFICADO':<16} | {'NOMBRE'}",
            "-" * 78,
        ]
        for idx, it in enumerate(items, 1):
            es_dir = it.is_dir()
            icono = "📁 DIR" if es_dir else "📄 FILE"
            try:
                st = it.stat()
                tam = "-" if es_dir else formatear_bytes(st.st_size)
                mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime))
            except Exception:
                tam, mtime = "?", "?"
            nombre_fmt = f"{C.BOLD}{C.BLUE}{it.name}/{C.RESET}" if es_dir else it.name
            filas.append(f"{idx:>3} | {icono:<6} | {tam:>10} | {mtime:<16} | {nombre_fmt}")

        filas.append(
            "\nComandos del Archivador: `/cd <carpeta>`, `/cat <archivo> [ini] [fin]`, `/edit <archivo>`, "
            "`/patch <archivo>`, `/mkdir <nombre>`, `/touch <nombre>`, `/rm <ruta>`, `/cp <a> <b>`, `/mv <a> <b>`, `/search <texto>`"
        )
        return "\n".join(filas)

    @staticmethod
    def ver_archivo_numerado(ruta_str: str, linea_ini: int = 1, linea_fin: int = 160) -> str:
        ruta = ruta_permitida(ruta_str, base_dir=CURRENT_NAV_DIR)
        if not ruta.is_file():
            return f"❌ El archivo no existe: {ruta}"
        lineas = ruta.read_text(encoding="utf-8", errors="replace").splitlines()
        total = len(lineas)
        ini = max(1, linea_ini)
        fin = min(total, max(ini, linea_fin))
        cabecera = f"\n{C.BOLD}{C.CYAN}📄 {ruta} (Líneas {ini}-{fin} de {total} | {formatear_bytes(ruta.stat().st_size)}){C.RESET}\n" + ("-" * 78)
        cuerpo = [f"{i:>5} | {lineas[i - 1]}" for i in range(ini, fin + 1)]
        return cabecera + "\n" + "\n".join(cuerpo)

    @staticmethod
    def buscar_en_archivos(patron: str) -> str:
        patron = patron.strip()
        if not patron:
            return "❌ Indica el texto o expresión regular a buscar."
        ignorar = {".git", "node_modules", "vendor", "__pycache__", ".aryi_logs", ".aryi_renders", ".aryi_audio"}
        hallazgos: List[str] = []
        rx = re.compile(re.escape(patron), re.IGNORECASE)

        for root, dirs, files in os.walk(CURRENT_NAV_DIR):
            dirs[:] = [d for d in dirs if d not in ignorar]
            for fname in files:
                fpath = Path(root) / fname
                if fpath.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".wav", ".ogg", ".exe", ".dll", ".zip"}:
                    continue
                try:
                    if fpath.stat().st_size > 2 * 1024 * 1024:
                        continue
                    for idx, ln in enumerate(fpath.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                        if rx.search(ln):
                            rel = fpath.relative_to(WORKSPACE_ROOT) if fpath.is_relative_to(WORKSPACE_ROOT) else fpath
                            hallazgos.append(f"  • {rel}:{idx} -> {ln.strip()[:110]}")
                            if len(hallazgos) >= 40:
                                break
                except Exception:
                    continue
            if len(hallazgos) >= 40:
                break

        if not hallazgos:
            return f"No se encontraron coincidencias para '{patron}' en {CURRENT_NAV_DIR}."
        return f"🔍 Coincidencias para '{patron}' ({len(hallazgos)} mostradas):\n" + "\n".join(hallazgos)

    @staticmethod
    def editor_interactivo_consola(ruta_str: str) -> str:
        """
        Editor de archivos interactivo directamente en la terminal (sin salir de ARYI),
        o lanza VS Code (`code`) / Bloc de notas (`notepad`) si se pasa `--code` o `--notepad`.
        """
        partes = ruta_str.strip().split()
        if not partes:
            return "❌ Uso: `/edit <archivo>` (o `/edit --notepad <archivo>`, `/edit --code <archivo>`)"

        modo_ext = ""
        if partes[0] in {"--notepad", "--code"}:
            modo_ext = partes[0]
            partes = partes[1:]
        if not partes:
            return "❌ Falta el nombre del archivo."

        ruta = ruta_permitida(" ".join(partes), base_dir=CURRENT_NAV_DIR)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        if not ruta.exists():
            escribir_archivo_atomico(ruta, "")

        if modo_ext == "--notepad" and IS_WINDOWS:
            subprocess.Popen(["notepad.exe", str(ruta)])
            return f"📝 Abierto en Notepad de Windows: {ruta}"
        if modo_ext == "--code" and shutil.which("code"):
            subprocess.Popen(["code", str(ruta)])
            return f"📝 Abierto en VS Code: {ruta}"

        lineas = ruta.read_text(encoding="utf-8", errors="replace").splitlines()
        print(
            f"\n{C.BOLD}{C.MAGENTA}=== EDITOR INTERACTIVO DE TERMINAL ARYI · {ruta.name} ({len(lineas)} líneas) ==={C.RESET}\n"
            "Subcomandos disponibles dentro del editor:\n"
            "  • `show [ini] [fin]`       : Muestra las líneas numeradas (ej. `show 1 50`)\n"
            "  • `set <N> <texto>`        : Reemplaza el contenido de la línea N\n"
            "  • `ins <N> <texto>`        : Inserta una nueva línea antes de la línea N\n"
            "  • `append <texto>`         : Añade una línea al final del archivo\n"
            "  • `del <N> [M]`            : Elimina la línea N (o el rango N..M)\n"
            "  • `replace <viejo>|<nuevo>`: Reemplaza todas las ocurrencias de <viejo> por <nuevo>\n"
            "  • `ai <instrucción>`       : Pide a ARYI IA que edite el archivo según tu instrucción\n"
            "  • `save`                   : Guarda los cambios atómicamente y sale del editor\n"
            "  • `quit`                   : Sale sin guardar\n"
        )
        print(TerminalArchivador.ver_archivo_numerado(str(ruta), 1, min(35, max(1, len(lineas)))))

        while True:
            cmd_ed = leer_linea_consola_sincrona(f"{C.CYAN}[EDIT {ruta.name}] > {C.RESET}").strip()
            if not cmd_ed:
                continue
            low_ed = cmd_ed.lower()

            if low_ed in {"quit", "exit", "q"}:
                return f"Edición de {ruta.name} cancelada sin guardar."

            if low_ed in {"save", "wq", "s"}:
                escribir_archivo_atomico(ruta, "\n".join(lineas))
                return f"✅ Archivo guardado exitosamente: {ruta} ({len(lineas)} líneas)."

            if low_ed.startswith("show"):
                p_sh = cmd_ed.split()
                ini = int(p_sh[1]) if len(p_sh) > 1 and p_sh[1].isdigit() else 1
                fin = int(p_sh[2]) if len(p_sh) > 2 and p_sh[2].isdigit() else ini + 40
                ini = max(1, ini)
                fin = min(len(lineas), fin)
                for i in range(ini, fin + 1):
                    print(f"{i:>5} | {lineas[i - 1]}")
                continue

            if low_ed.startswith("set "):
                m_set = re.match(r"^set\s+(\d+)\s?(.*)$", cmd_ed)
                if m_set:
                    idx = int(m_set.group(1))
                    if 1 <= idx <= len(lineas):
                        lineas[idx - 1] = m_set.group(2)
                        print(f"  Línea {idx} actualizada.")
                    else:
                        print(f"  Índice fuera de rango (1..{len(lineas)}).")
                continue

            if low_ed.startswith("ins "):
                m_ins = re.match(r"^ins\s+(\d+)\s?(.*)$", cmd_ed)
                if m_ins:
                    idx = max(1, min(len(lineas) + 1, int(m_ins.group(1))))
                    lineas.insert(idx - 1, m_ins.group(2))
                    print(f"  Línea insertada en posición {idx}.")
                continue

            if low_ed.startswith("append "):
                lineas.append(cmd_ed[7:])
                print(f"  Línea #{len(lineas)} añadida.")
                continue

            if low_ed.startswith("del "):
                p_del = cmd_ed.split()
                if len(p_del) >= 2 and p_del[1].isdigit():
                    i1 = int(p_del[1])
                    i2 = int(p_del[2]) if len(p_del) >= 3 and p_del[2].isdigit() else i1
                    if 1 <= i1 <= i2 <= len(lineas):
                        del lineas[i1 - 1 : i2]
                        print(f"  Eliminadas líneas {i1}..{i2}.")
                continue

            if low_ed.startswith("replace "):
                resto = cmd_ed[8:]
                if "|" in resto:
                    viejo, nuevo = resto.split("|", 1)
                    unido = "\n".join(lineas)
                    cuenta = unido.count(viejo)
                    lineas = unido.replace(viejo, nuevo).splitlines()
                    print(f"  Reemplazadas {cuenta} ocurrencia(s).")
                else:
                    print("  Formato: replace texto_viejo|texto_nuevo")
                continue

            if low_ed.startswith("ai "):
                instruccion_ia = cmd_ed[3:].strip()
                escribir_archivo_atomico(ruta, "\n".join(lineas))
                SHARED_INBOX.put(("consola", f"Edita el archivo '{ruta}' aplicando este cambio exacto: {instruccion_ia}"))
                return f"🤖 Cambio delegado a ARYI IA sobre {ruta.name}."

            print("  Comando no reconocido. Usa: show, set, ins, append, del, replace, ai, save, quit.")


# =============================================================================
# 4. PERFILES "NIVEL DIOS" Y EJECUCIÓN WINDOWS NATIVE / GITOPS
# =============================================================================
GOD_PROFILES: Dict[str, Dict[str, str]] = {
    "systems_architect": {
        "titulo": "Arquitecto Supremo de Sistemas & Cloud-Native (Nivel Dios)",
        "role_type": "architect",
        "directiva": (
            "Actúas con rigor de Principal Systems Architect. Te basas ESTRICTAMENTE en los archivos reales "
            "del workspace escaneado (nunca inventas plantillas genéricas ni placeholders). Defines la arquitectura "
            "exacta de los componentes reales del proyecto."
        ),
    },
    "fullstack_framework_master": {
        "titulo": "Ingeniero Principal Polyglot & Creador de Frameworks (Nivel Dios)",
        "role_type": "coder",
        "directiva": (
            "Dominas Python, PHP, Docker, TypeScript/Node, Rust, Go, C# y PowerShell. "
            "Puedes crear archivos nuevos con `<file path=\"...\">` o editar líneas específicas de archivos "
            "existentes usando `<edit_file path=\"...\">` con bloques SEARCH/REPLACE."
        ),
    },
    "gitops_release_commander": {
        "titulo": "Comandante GitOps, CI/CD & Automatización de Repositorios (Nivel Dios)",
        "role_type": "gitops",
        "directiva": (
            "Gestionas el ciclo de vida en Git y GitHub emitiendo SIEMPRE etiquetas XML ejecutables `<git op=\"...\"></git>`. "
            "Para hacer commit y push emites `<git op=\"commit\" message=\"...\"></git>` seguido de `<git op=\"push\"></git>`."
        ),
    },
    "cybersec_qa_auditor": {
        "titulo": "Auditor de Seguridad Ofensiva/Defensiva & QA Estricto (Nivel Dios)",
        "role_type": "qa",
        "directiva": (
            "Analizas el código real del proyecto buscando vulnerabilidades, errores de configuración o mejoras técnicas "
            "concretas. Nunca sobrescribes el archivo principal con una plantilla vacía."
        ),
    },
    "deep_research_strategist": {
        "titulo": "Investigador Científico, Estratégico y Analista en Tiempo Real (Nivel Dios)",
        "role_type": "researcher",
        "directiva": (
            "Investigas cualquier disciplina con objetividad absoluta, contrastando fuentes en tiempo real mediante "
            "`<web_search>` y `<web_fetch>`."
        ),
    },
}


def detectar_perfil_dios(prompt_usuario: str) -> Dict[str, str]:
    low = prompt_usuario.lower()
    if any(k in low for k in ("commit", "push", "pull request", "pr ", "branch", "rama", "merge", "git")):
        return GOD_PROFILES["gitops_release_commander"]
    if any(k in low for k in ("audita", "seguridad", "vulnerabilidad", "bug", "test", "qa", "corrige error")):
        return GOD_PROFILES["cybersec_qa_auditor"]
    if any(k in low for k in ("investiga", "busca en la web", "noticias", "comparativa", "paper", "qué es", "analiza el mercado")):
        return GOD_PROFILES["deep_research_strategist"]
    if any(k in low for k in ("arquitectura", "sistema desde cero", "equipo", "misión", "orquesta", "microservicio", "diseña")):
        return GOD_PROFILES["systems_architect"]
    return GOD_PROFILES["fullstack_framework_master"]


def limpiar_html_a_texto(raw_html: str, max_chars: int = 12_000) -> str:
    limpio = re.sub(r"<(script|style|noscript|svg|header|footer|nav)\b[^>]*>.*?</\1>", " ", raw_html, flags=re.DOTALL | re.IGNORECASE)
    limpio = re.sub(r"</?(p|div|h[1-6]|li|tr|br|pre|code)\b[^>]*>", "\n", limpio, flags=re.IGNORECASE)
    limpio = re.sub(r"<[^>]+>", " ", limpio)
    limpio = html.unescape(limpio)
    lineas = [re.sub(r"[ \t]+", " ", ln).strip() for ln in limpio.splitlines()]
    lineas = [ln for ln in lineas if len(ln) > 1]
    return recortar("\n".join(lineas), max_chars, proporcion_cola=0.3)


def buscar_en_web(query: str, max_results: int = 6) -> str:
    query = query.strip()
    if not query:
        return "Consulta de búsqueda vacía."
    print(f"{C.CYAN}[WEB SEARCH] Consultando en tiempo real: '{query}'...{C.RESET}")
    log_event("WEB_SEARCH", f"Query: {query}")
    resultados: List[str] = []

    try:
        url = "https://html.duckduckgo.com/html/"
        r = HTTP.post(url, data={"q": query}, timeout=(TIMEOUT_HTTP_CONNECT, 15))
        if r.status_code == 200:
            bloques = re.findall(
                r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
                r.text,
                flags=re.DOTALL | re.IGNORECASE,
            )
            for href, titulo, snippet in bloques[:max_results]:
                if "uddg=" in href:
                    parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                    href = parsed.get("uddg", [href])[0]
                t_clean = html.unescape(re.sub(r"<[^>]+>", "", titulo)).strip()
                s_clean = html.unescape(re.sub(r"<[^>]+>", "", snippet)).strip()
                resultados.append(f"• {t_clean}\n  URL: {href}\n  Resumen: {s_clean}")
    except Exception as e:
        resultados.append(f"Aviso en DuckDuckGo HTML: {e}")

    if not resultados:
        try:
            wiki_url = "https://en.wikipedia.org/w/api.php"
            r = HTTP.get(
                wiki_url,
                params={"action": "opensearch", "search": query, "limit": max_results, "format": "json"},
                timeout=(5, 10),
            )
            if r.status_code == 200:
                data = r.json()
                for tit, desc, link in zip(data[1], data[2], data[3]):
                    resultados.append(f"• {tit}\n  URL: {link}\n  Resumen: {desc}")
        except Exception:
            pass

    auditar("web_search", query, f"{len(resultados)} resultados")
    if not resultados:
        return f"No se obtuvieron resultados directos para '{query}'."
    return f"RESULTADOS WEB EN TIEMPO REAL PARA '{query}':\n\n" + "\n\n".join(resultados)


def leer_pagina_web(url: str, max_chars: int = 10_000) -> str:
    url = url.strip()
    print(f"{C.CYAN}[WEB FETCH] Descargando y extrayendo: {url}...{C.RESET}")
    log_event("WEB_FETCH", f"URL: {url}")
    try:
        r = HTTP.get(url, timeout=(TIMEOUT_HTTP_CONNECT, 20))
        r.raise_for_status()
        ctype = r.headers.get("Content-Type", "").lower()
        if "json" in ctype:
            texto = json.dumps(r.json(), indent=2, ensure_ascii=False)[:max_chars]
        else:
            texto = limpiar_html_a_texto(r.text, max_chars=max_chars)
        auditar("web_fetch", url, f"OK ({len(texto)} chars)")
        return f"CONTENIDO DE {url}:\n\n{texto}"
    except Exception as e:
        return f"Error al leer URL {url}: {e}"


def aprender_framework(nombre_framework: str, telemetry: TelemetryEngine) -> str:
    slug = re.sub(r"[^a-z0-9_-]+", "_", nombre_framework.strip().lower()).strip("_") or "framework"
    archivo_destino = FRAMEWORKS_DIR / f"{slug}.md"

    print(f"{C.MAGENTA}[LEARN FRAMEWORK] Investigando y aprendiendo '{nombre_framework}' en tiempo real...{C.RESET}")
    busqueda = buscar_en_web(f"{nombre_framework} official documentation quickstart guide best practices code examples", max_results=5)

    urls = re.findall(r"URL:\s*(https?://[^\s]+)", busqueda)
    contenido_extra = ""
    for u in urls[:2]:
        contenido_extra += "\n\n" + leer_pagina_web(u, max_chars=5_000)

    prompt_sintesis = (
        f"Eres un Ingeniero Principal documentando el framework/librería '{nombre_framework}'.\n"
        f"Con base en la siguiente información obtenida en tiempo real de la web:\n\n"
        f"{busqueda}\n{contenido_extra}\n\n"
        f"Genera un Cheat-Sheet Técnico Maestro en Markdown que incluya:\n"
        f"1. Instalación y configuración inicial (Windows/Linux).\n"
        f"2. Arquitectura y conceptos clave.\n"
        f"3. Patrones de código reales y funcionales listos para producción.\n"
        f"4. Errores comunes a evitar."
    )

    candidatos = [m.name for m in telemetry.rank_models_for_role("researcher")]
    sintesis, _ = llamar_ollama_resiliente(
        api_base=telemetry.api_base,
        modelos_candidatos=candidatos,
        mensajes=[{"role": "user", "content": prompt_sintesis}],
        limite_tokens=8192,
        silencioso=False,
    )

    escribir_archivo_atomico(archivo_destino, sintesis)
    return (
        f"Framework '{nombre_framework}' aprendido y almacenado en memoria persistente: {archivo_destino}\n\n"
        f"RESUMEN DEL CONOCIMIENTO ADQUIRIDO:\n{recortar(sintesis, 3500)}"
    )


def cargar_frameworks_aprendidos() -> str:
    archivos = sorted(FRAMEWORKS_DIR.glob("*.md"))
    if not archivos:
        return "Ninguno almacenado aún (usa `<learn_framework name=\"...\"/>` para aprender cualquiera al instante)."
    return ", ".join(f.stem for f in archivos)


def ejecutar_comando_sistema(comando: str, usar_powershell: bool = True, cwd: Optional[Path] = None) -> Tuple[int, str, str]:
    work_dir = cwd or CURRENT_NAV_DIR or WORKSPACE_ROOT
    if IS_WINDOWS:
        if usar_powershell:
            pwsh = shutil.which("pwsh") or shutil.which("powershell") or "powershell.exe"
            shell_cmd = [pwsh, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", comando]
        else:
            shell_cmd = ["cmd.exe", "/c", comando]
    else:
        shell_cmd = [shutil.which("bash") or "/bin/sh", "-c", comando]

    log_event("EXEC_START", f"({work_dir}) $ {comando}")
    proc = subprocess.Popen(
        shell_cmd,
        cwd=str(work_dir),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    estado = "ok"
    try:
        salida, _ = proc.communicate(timeout=TIMEOUT_CMD)
    except subprocess.TimeoutExpired:
        estado = "timeout"
        try:
            proc.kill()
        except Exception:
            pass
        salida = f"[TIMEOUT tras {TIMEOUT_CMD}s]"
    except KeyboardInterrupt:
        estado = "interrumpido"
        try:
            proc.kill()
        except Exception:
            pass
        salida = "[INTERRUMPIDO POR EL OPERADOR]"

    rc = proc.returncode if proc.returncode is not None else -1
    auditar("exec_cmd", comando, f"rc={rc} ({estado})")
    return rc, (salida or "").strip() or "(sin salida)", estado


@dataclass
class ProcesoFondo:
    pid: int
    comando: str
    log: Path
    popen: "subprocess.Popen[Any]"
    inicio: float


PROCESOS_FONDO: Dict[int, ProcesoFondo] = {}


def iniciar_servicio_fondo(comando: str) -> ProcesoFondo:
    if IS_WINDOWS:
        pwsh = shutil.which("pwsh") or shutil.which("powershell") or "powershell.exe"
        shell_cmd = [pwsh, "-NoProfile", "-Command", comando]
    else:
        shell_cmd = [shutil.which("bash") or "/bin/sh", "-c", comando]

    log_path = LOGS_DIR / f"bg_{time.strftime('%Y%m%d_%H%M%S')}_{time.time_ns()}.log"
    with open(log_path, "ab") as log:
        proc = subprocess.Popen(
            shell_cmd,
            cwd=str(WORKSPACE_ROOT),
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    info = ProcesoFondo(proc.pid, comando, log_path, proc, time.time())
    PROCESOS_FONDO[proc.pid] = info
    auditar("bg_service", comando, f"PID={proc.pid} log={log_path.name}")
    return info


def listar_procesos_fondo() -> str:
    if not PROCESOS_FONDO:
        return "No hay servicios en segundo plano activos."
    filas = []
    for p in PROCESOS_FONDO.values():
        rc = p.popen.poll()
        estado = "ACTIVO" if rc is None else f"TERMINADO (rc={rc})"
        filas.append(f"  • PID {p.pid:<7} [{estado}] $ {p.comando[:70]} (Log: {p.log.name})")
    return "\n".join(filas)


class GitOpsManager:
    @staticmethod
    def run_git(args: List[str], cwd: Optional[Path] = None) -> Tuple[int, str]:
        cmd_str = "git " + " ".join(f'"{a}"' if " " in a else a for a in args)
        rc, out, _ = ejecutar_comando_sistema(cmd_str, usar_powershell=False, cwd=cwd)
        return rc, out

    @classmethod
    def execute_git_action(cls, attrs: Dict[str, str], body: str) -> str:
        op = (attrs.get("op") or attrs.get("action") or "status").strip().lower()
        repo_sub = attrs.get("cwd") or attrs.get("repo") or ""
        work_dir = ruta_permitida(repo_sub) if repo_sub else WORKSPACE_ROOT

        if op == "init":
            rc, out = cls.run_git(["init"], cwd=work_dir)
            return f"[GitOps init (rc={rc})]:\n{out}"

        if op == "status":
            rc, out = cls.run_git(["status", "-sb"], cwd=work_dir)
            _, diff_stat = cls.run_git(["diff", "--stat"], cwd=work_dir)
            return f"[GitOps status (rc={rc})]:\n{out}\n{diff_stat}".strip()

        if op == "branch":
            branch_name = (attrs.get("name") or attrs.get("branch") or body).strip()
            if not branch_name:
                rc, out = cls.run_git(["branch", "-a"], cwd=work_dir)
                return f"[GitOps branches]:\n{out}"
            rc, out = cls.run_git(["checkout", "-b", branch_name], cwd=work_dir)
            if rc != 0:
                rc, out = cls.run_git(["checkout", branch_name], cwd=work_dir)
            return f"[GitOps branch '{branch_name}' (rc={rc})]:\n{out}"

        if op == "commit":
            msg = (attrs.get("message") or attrs.get("msg") or body or "feat: autonomous update by ARYI Omega").strip()
            files_attr = (attrs.get("files") or attrs.get("add") or "-A").strip()
            if files_attr == "-A":
                cls.run_git(["add", "-A"], cwd=work_dir)
            else:
                for f_item in files_attr.split():
                    cls.run_git(["add", f_item], cwd=work_dir)
            rc, out = cls.run_git(["commit", "-m", msg], cwd=work_dir)
            return f"[GitOps commit (rc={rc})]:\n{out}"

        if op == "push":
            remote = (attrs.get("remote") or "origin").strip()
            branch = (attrs.get("branch") or "").strip()
            args = ["push", "-u", remote] + ([branch] if branch else ["HEAD"])
            rc, out = cls.run_git(args, cwd=work_dir)
            return f"[GitOps push (rc={rc})]:\n{out}"

        if op in ("pr", "pull_request"):
            title = (attrs.get("title") or "Autonomous PR by ARYI Omega").strip()
            base = (attrs.get("base") or "main").strip()
            head = (attrs.get("head") or "").strip()
            pr_body = (body or "Pull Request generado automáticamente por ARYI Omega.").strip()

            if shutil.which("gh"):
                cmd_parts = ["gh", "pr", "create", "--title", f'"{title}"', "--body", f'"{pr_body}"', "--base", base]
                if head:
                    cmd_parts.extend(["--head", head])
                rc, out, _ = ejecutar_comando_sistema(" ".join(cmd_parts), usar_powershell=False, cwd=work_dir)
                if rc == 0:
                    return f"[GitOps Pull Request creado vía GitHub CLI]:\n{out}"

            if GITHUB_TOKEN:
                _, remote_url = cls.run_git(["config", "--get", "remote.origin.url"], cwd=work_dir)
                m = re.search(r"github\.com[:/]([^/]+)/([^\.\s]+)", remote_url)
                if not head:
                    _, head_out = cls.run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=work_dir)
                    head = head_out.strip()
                if m:
                    owner, repo = m.group(1), m.group(2)
                    api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
                    try:
                        r = HTTP.post(
                            api_url,
                            headers={
                                "Authorization": f"Bearer {GITHUB_TOKEN}",
                                "Accept": "application/vnd.github+json",
                            },
                            json={"title": title, "body": pr_body, "head": head, "base": base},
                            timeout=(10, 20),
                        )
                        if r.status_code in (200, 201):
                            pr_url = r.json().get("html_url", "")
                            return f"[GitOps Pull Request creado exitosamente vía API]: {pr_url}"
                        return f"[GitOps Error API GitHub ({r.status_code})]: {r.text[:500]}"
                    except Exception as e:
                        return f"[GitOps Excepción API GitHub]: {e}"

            return (
                "[GitOps PR Aviso]: Para crear Pull Requests automáticamente instala GitHub CLI (`winget install GitHub.cli`) "
                "o define la variable de entorno `GITHUB_TOKEN`."
            )

        rc, out = cls.run_git(op.split() + ([body.strip()] if body.strip() else []), cwd=work_dir)
        return f"[GitOps '{op}' (rc={rc})]:\n{out}"


# =============================================================================
# 5. CLIENTE OLLAMA RESILIENTE CON HEARTBEAT EN VIVO (ANTI-FREEZE & ANTI-500)
# =============================================================================
def _mensajes_a_prompt_plano(mensajes: List[Dict[str, str]]) -> str:
    bloques: List[str] = []
    for m in mensajes:
        rol = m.get("role", "user").upper()
        contenido = m.get("content", "")
        if rol == "SYSTEM":
            bloques.append(f"### INSTRUCCIONES DEL SISTEMA:\n{contenido}")
        elif rol == "ASSISTANT":
            bloques.append(f"### ASISTENTE:\n{contenido}")
        else:
            bloques.append(f"### USUARIO:\n{contenido}")
    bloques.append("### ASISTENTE:\n")
    return "\n\n".join(bloques)


def _intentar_chat_o_generate(
    api_base: str,
    modelo: str,
    mensajes: List[Dict[str, str]],
    num_ctx: int,
    temperatura: float,
    silencioso: bool,
    prefijo_stream: str,
    usar_generate: bool = False,
) -> str:
    partes: List[str] = []
    printed_header = False
    first_token_event = threading.Event()
    stop_heartbeat_event = threading.Event()
    t0 = time.perf_counter()

    endpoint_name = "/generate" if usar_generate else "/chat"
    log_event("OLLAMA_REQ", f"POST {endpoint_name} model={modelo} num_ctx={num_ctx}")

    def _heartbeat_worker() -> None:
        while not stop_heartbeat_event.wait(4.0):
            if first_token_event.is_set():
                break
            elapsed = time.perf_counter() - t0
            msg_hb = f"⏳ [GPU Pulse] Cargando/procesando en '{modelo}' ({elapsed:.1f}s transcurridos)..."
            log_event("GPU_PULSE", msg_hb)
            if not silencioso:
                print(f"  {C.DIM}{msg_hb}{C.RESET}", flush=True)

    hb_thread = threading.Thread(target=_heartbeat_worker, daemon=True, name="OllamaHeartbeat")
    hb_thread.start()

    try:
        if not usar_generate:
            url = f"{api_base.rstrip('/')}/chat"
            payload: Dict[str, Any] = {
                "model": modelo,
                "messages": mensajes,
                "stream": True,
                "options": {"temperature": temperatura, "num_ctx": num_ctx},
            }
        else:
            url = f"{api_base.rstrip('/')}/generate"
            payload = {
                "model": modelo,
                "prompt": _mensajes_a_prompt_plano(mensajes),
                "stream": True,
                "options": {"temperature": temperatura, "num_ctx": num_ctx},
            }

        with HTTP.post(url, json=payload, stream=True, timeout=(TIMEOUT_HTTP_CONNECT, TIMEOUT_HTTP_READ)) as r:
            if r.status_code >= 400:
                detalle_err = ""
                try:
                    detalle_err = r.json().get("error", "")
                except Exception:
                    detalle_err = r.text[:300]
                raise RuntimeError(f"HTTP {r.status_code} en {url} (modelo={modelo}, num_ctx={num_ctx}): {detalle_err}")

            for linea in r.iter_lines():
                if not linea:
                    continue
                try:
                    evento = json.loads(linea)
                except Exception:
                    continue
                if "error" in evento:
                    raise RuntimeError(f"Error en stream de Ollama ({modelo}): {evento['error']}")

                frag = (
                    (evento.get("message") or {}).get("content", "")
                    if not usar_generate
                    else evento.get("response", "")
                )
                if frag:
                    if not first_token_event.is_set():
                        first_token_event.set()
                        ttft_real = time.perf_counter() - t0
                        log_event("OLLAMA_TTFT", f"Primer token de {modelo} en {ttft_real:.2f}s")
                    if not silencioso:
                        if prefijo_stream and not printed_header:
                            print(prefijo_stream, end="", flush=True)
                            printed_header = True
                        print(frag, end="", flush=True)
                    partes.append(frag)
                if evento.get("done"):
                    break
    finally:
        stop_heartbeat_event.set()
        first_token_event.set()

    if not silencioso and partes:
        print()
    full_text = "".join(partes)
    total_s = time.perf_counter() - t0
    log_event("OLLAMA_DONE", f"Completado {modelo} ({len(full_text)} chars en {total_s:.2f}s)")
    return full_text


def llamar_ollama_resiliente(
    api_base: str,
    modelos_candidatos: List[str],
    mensajes: List[Dict[str, str]],
    limite_tokens: int = 8192,
    temperatura: float = 0.15,
    silencioso: bool = False,
    prefijo_stream: str = "",
) -> Tuple[str, str]:
    errores_acumulados: List[str] = []

    for idx, modelo in enumerate(modelos_candidatos):
        param_b = estimar_parametros_b(modelo)
        ctx_inicial = min(limite_tokens, 4096 if (param_b >= 25.0 or "gguf" in modelo.lower()) else 8192)

        with GPU_INFERENCE_LOCK:
            try:
                resp = _intentar_chat_o_generate(
                    api_base=api_base,
                    modelo=modelo,
                    mensajes=mensajes,
                    num_ctx=ctx_inicial,
                    temperatura=temperatura,
                    silencioso=silencioso,
                    prefijo_stream=prefijo_stream,
                    usar_generate=False,
                )
                if resp.strip():
                    return resp, modelo
            except Exception as e1:
                errores_acumulados.append(str(e1))
                log_event("OLLAMA_RETRY", f"Fallo /chat en {modelo}: {e1}", "WARN")
                if not silencioso:
                    print(f"\n{C.YELLOW}  [AVISO OLLAMA] {e1} -> Reintentando '{modelo}' vía /api/generate (num_ctx=4096)...{C.RESET}")

            try:
                resp = _intentar_chat_o_generate(
                    api_base=api_base,
                    modelo=modelo,
                    mensajes=mensajes,
                    num_ctx=4096,
                    temperatura=temperatura,
                    silencioso=silencioso,
                    prefijo_stream=prefijo_stream,
                    usar_generate=True,
                )
                if resp.strip():
                    return resp, modelo
            except Exception as e2:
                errores_acumulados.append(str(e2))
                log_event("OLLAMA_FAILOVER", f"Fallo /generate en {modelo}: {e2}", "ERROR")
                if idx + 1 < len(modelos_candidatos):
                    sig_modelo = modelos_candidatos[idx + 1]
                    print(
                        f"{C.YELLOW}  [AUTO-FAILOVER] '{modelo}' devolvió error en el servidor. "
                        f"Conmutando automáticamente a '{sig_modelo}'...{C.RESET}"
                    )

    raise RuntimeError("Todos los modelos candidatos fallaron:\n" + "\n".join(errores_acumulados[-4:]))


# =============================================================================
# 6. ESCÁNER PROFUNDO DEL WORKSPACE Y COORDINADOR SWARM
# =============================================================================
@dataclass
class SwarmAgentSpec:
    name: str
    role_type: str
    persona_prompt: str
    task_instruction: str


def escanear_contexto_real_proyecto(max_chars: int = 9_000) -> str:
    log_event("PROJECT_SCAN", f"Escaneando estructura real de {WORKSPACE_ROOT}")
    ignorar = {".git", "node_modules", "vendor", "__pycache__", ".aryi_logs", ".aryi_memory", ".aryi_renders", ".aryi_audio", "tmp", "backups"}
    arbol: List[str] = []

    try:
        for item in sorted(WORKSPACE_ROOT.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if item.name in ignorar:
                continue
            if item.is_dir():
                sub_items = []
                try:
                    for sub in sorted(item.iterdir(), key=lambda p: p.name.lower())[:18]:
                        if sub.name not in ignorar:
                            sub_items.append(sub.name + ("/" if sub.is_dir() else ""))
                except Exception:
                    pass
                arbol.append(f"📁 {item.name}/ -> [{', '.join(sub_items)}]")
            else:
                tam_kb = round(item.stat().st_size / 1024, 1)
                arbol.append(f"📄 {item.name} ({tam_kb} KB)")
    except Exception as e:
        arbol.append(f"Error listando directorio: {e}")

    _, git_st = GitOpsManager.run_git(["status", "-sb"], cwd=WORKSPACE_ROOT)
    _, git_log = GitOpsManager.run_git(["log", "-n", "3", "--oneline"], cwd=WORKSPACE_ROOT)

    archivos_clave = ["README.md", "docker-compose.yml", "Dockerfile", "ARYI_AUDIT_REPORT.md", "agent_state.json"]
    extractos: List[str] = []
    for nombre in archivos_clave:
        ruta = WORKSPACE_ROOT / nombre
        if ruta.is_file():
            try:
                txt = ruta.read_text(encoding="utf-8", errors="replace")
                extractos.append(f"=== ARCHIVO EXISTENTE: {nombre} ({len(txt)} chars) ===\n{recortar(txt, 2200)}")
            except Exception:
                pass

    resumen = (
        f"=== RADIOGRAFÍA REAL DEL PROYECTO EN {WORKSPACE_ROOT} ===\n"
        f"ÁRBOL DE ARCHIVOS:\n" + "\n".join(arbol) + "\n\n"
        f"ESTADO GIT ACTUAL:\n{git_st}\nÚltimos commits:\n{git_log}\n\n"
        + "\n\n".join(extractos)
    )
    return recortar(resumen, max_chars)


class SwarmCoordinator:
    def __init__(self, telemetry: TelemetryEngine):
        self.telemetry = telemetry
        self.api_base = telemetry.api_base

    def execute_mission(self, mission_goal: str, mode: str = "hybrid") -> str:
        log_event("MISSION_START", f"Objetivo: {mission_goal}")
        print(f"\n{C.CYAN}🔍 [PROJECT SCANNER] Escaneando archivos reales, Docker y estado Git en {WORKSPACE_ROOT}...{C.RESET}")
        radiografia_proyecto = escanear_contexto_real_proyecto()

        wants_git = any(k in mission_goal.lower() for k in ("commit", "push", "pull request", "pr", "git"))

        specs: List[SwarmAgentSpec] = [
            SwarmAgentSpec(
                name="Lead Systems Architect",
                role_type="architect",
                persona_prompt=GOD_PROFILES["systems_architect"]["directiva"],
                task_instruction=(
                    f"Analiza la RADIOGRAFÍA REAL DEL PROYECTO adjunta y diseña el blueprint técnico exacto para: {mission_goal}.\n"
                    "IMPORTANTE: NO emitas etiquetas `<file>` en este paso; entrega un análisis profundo de la arquitectura "
                    "real (Docker, PROYECTO, ARYI Omega, scripts, reportes) y el índice detallado que debe seguir el Ingeniero."
                ),
            ),
            SwarmAgentSpec(
                name="Core Full-Stack & Documentation Engineer",
                role_type="coder",
                persona_prompt=GOD_PROFILES["fullstack_framework_master"]["directiva"],
                task_instruction=(
                    f"Con base en la RADIOGRAFÍA REAL DEL PROYECTO y el Blueprint del Arquitecto, ejecuta la implementación para: {mission_goal}.\n"
                    "EMITE EL ARCHIVO COMPLETO Y DEFINITIVO dentro de una etiqueta `<file path=\"...\">...</file>` "
                    "o edita archivos existentes con `<edit_file path=\"...\">`."
                ),
            ),
            SwarmAgentSpec(
                name="CyberSec & QA Auditor",
                role_type="qa",
                persona_prompt=GOD_PROFILES["cybersec_qa_auditor"]["directiva"],
                task_instruction=(
                    f"Audita técnicamente el proyecto real y el entregable para: {mission_goal}.\n"
                    "IMPORTANTE: NO sobrescribas el archivo con `<file>`; entrega únicamente el reporte de auditoría de calidad y seguridad."
                ),
            ),
        ]

        if wants_git:
            specs.append(
                SwarmAgentSpec(
                    name="GitOps Release Commander",
                    role_type="gitops",
                    persona_prompt=GOD_PROFILES["gitops_release_commander"]["directiva"],
                    task_instruction=(
                        f"La misión requiere operaciones Git para: {mission_goal}.\n"
                        "Debes emitir OBLIGATORIAMENTE las etiquetas XML ejecutables reales al inicio de línea:\n"
                        "<git op=\"commit\" message=\"docs(project): autonomous mission update by ARYI Omega\">\n</git>\n"
                        "<git op=\"push\" remote=\"origin\">\n</git>"
                    ),
                )
            )

        print(f"\n{C.BOLD}{C.CYAN}=== EQUIPO TÁCTICO CONVOCADO ({len(specs)} AGENTES) ==={C.RESET}")
        for idx, s in enumerate(specs, 1):
            m_name, _ = self.telemetry.select_best_model_for_role(s.role_type)
            print(f"  {idx}. {C.BOLD}{s.name}{C.RESET} [{s.role_type}] -> Modelo primario: {C.GREEN}{m_name}{C.RESET}")

        reportes: Dict[str, str] = {}

        def _run_agent(spec: SwarmAgentSpec, contexto_previo: str = "") -> Tuple[str, str]:
            candidatos = [m.name for m in self.telemetry.rank_models_for_role(spec.role_type)]
            primario = candidatos[0] if candidatos else "qwen2.5-coder:7b"

            sys_msg = (
                f"Eres {spec.name}.\n{spec.persona_prompt}\n"
                f"Trabajas sobre el directorio real Windows Native: {WORKSPACE_ROOT}."
            )
            user_msg = (
                f"MISIÓN GLOBAL: {mission_goal}\n\n"
                f"{radiografia_proyecto}\n\n"
                + (f"=== BLUEPRINT DEL ARQUITECTO ===\n{recortar(contexto_previo, 3500)}\n\n" if contexto_previo else "")
                + f"TU TAREA ESPECÍFICA:\n{spec.task_instruction}"
            )
            print(f"\n{C.BLUE}▶ [{spec.name}] ejecutando en '{primario}' (Monitoreo Live Log activo)...{C.RESET}")
            log_event("SWARM_AGENT", f"Iniciando {spec.name} en {primario}")
            resp, modelo_usado = llamar_ollama_resiliente(
                api_base=self.api_base,
                modelos_candidatos=candidatos,
                mensajes=[{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}],
                limite_tokens=8192,
                temperatura=0.15,
                silencioso=False,
            )
            return f"{spec.name} ({modelo_usado})", resp

        blueprint = ""
        try:
            ag_key, blueprint = _run_agent(specs[0])
            reportes[ag_key] = blueprint
        except Exception as exc:
            print(f"{C.RED}[SWARM AVISO] Arquitecto omitido ({exc}). Continuando...{C.RESET}")

        for sp in specs[1:]:
            try:
                nombre_ag, salida_ag = _run_agent(sp, blueprint)
                reportes[nombre_ag] = salida_ag
            except Exception as exc:
                print(f"{C.RED}[SWARM ERROR] Agente {sp.name} falló: {exc}{C.RESET}")

        ts = time.strftime("%Y%m%d_%H%M%S")
        mission_file = MISSIONS_DIR / f"mission_{ts}.md"
        compilado = [f"# Acta de Misión: {mission_goal}\nFecha: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"]
        for k, v in reportes.items():
            compilado.append(f"## Agente: {k}\n\n{v}\n\n---\n")
        escribir_archivo_atomico(mission_file, "\n".join(compilado))
        log_event("MISSION_END", f"Acta guardada en {mission_file}")

        return (
            f"MISIÓN EJECUTADA POR EL EQUIPO ({len(reportes)} especialistas). "
            f"Acta completa guardada en: {mission_file}\n\n"
            + "\n\n".join(f"=== REPORTE DE {k} ===\n{v}" for k, v in reportes.items())
        )


# =============================================================================
# 7. SYSTEM PROMPT MAESTRO Y PARSER DE HERRAMIENTAS XML (CON VISIÓN, SD Y EDIT)
# =============================================================================
SYSTEM_PROMPT_TEMPLATE = """ERES ARYI OMEGA v10.0, AGENTE AUTÓNOMO MULTIMODAL WINDOWS NATIVE Y ORQUESTADOR MULTI-MODELO DE NIVEL DIOS.

PERFIL ACTIVO PARA ESTA TAREA:
- Rol: {GOD_TITLE}
- Directiva: {GOD_DIRECTIVE}

ENTORNO Y CAPACIDADES NATIVAS:
- Sistema Operativo: {OS_INFO}
- Workspace Raíz Permitido: {WORKSPACE}
- Directorio Activo del Archivador: {CURRENT_DIR}
- Frameworks en Memoria Persistente: {LEARNED_FRAMEWORKS}

TIENES ACCESO DIRECTO AL SISTEMA OPERATIVO, ARCHIVADOR/EDITOR, VISIÓN MULTIMODAL, STABLE DIFFUSION, VOZ TTS, GIT, WEB EN TIEMPO REAL Y ENJAMBRE DE EQUIPOS MEDIANTE ETIQUETAS XML.
Cada etiqueta debe abrirse y cerrarse limpiamente al inicio de una línea:

1. Crear o sobrescribir un archivo completo:
<file path="ruta/relativa/archivo.ext">
contenido íntegro del archivo
</file>

2. Editar quirúrgicamente líneas o bloques de un archivo existente (sin reescribirlo todo):
<edit_file path="ruta/relativa/archivo.ext">
<<<<<<< SEARCH
líneas exactas actuales que quieres cambiar
=======
nuevas líneas reemplazadas
>>>>>>> REPLACE
</edit_file>

3. Leer un archivo existente del workspace:
<read_file path="ruta/relativa/archivo.py">
</read_file>

4. Analizar o describir una imagen local con los Modelos de Visión (`llava-phi3` / `moondream`):
<vision path="ruta/a/imagen.png">
Pregunta o instrucción visual sobre la imagen
</vision>

5. Generar una imagen con Stable Diffusion (`100.115.1.71:7860`):
<sd_image width="512" height="512" steps="20">
Descripción detallada de la imagen a generar
</sd_image>

6. Hablar en voz alta con el sintetizador TTS (`100.115.1.71:5050` / Windows Voice):
<speak>
Texto que deseas pronunciar por los altavoces
</speak>

7. Ejecutar comandos en PowerShell nativo de Windows:
<powershell>
Get-ChildItem -Force
</powershell>

8. Ejecutar comandos en CMD / Bash estándar:
<bash>
pytest -q
</bash>

9. Iniciar un servidor o proceso persistente en segundo plano:
<bash_bg>
python app.py
</bash_bg>

10. Operaciones Git y GitHub (op="init" | "status" | "branch" | "commit" | "push" | "pr"):
<git op="commit" message="feat(core): implementar módulo multimodal">
</git>
<git op="push" remote="origin">
</git>

11. Consultar la Web (WWW) en tiempo real o aprender un framework:
<web_search>
consulta precisa a buscar en tiempo real
</web_search>
<web_fetch url="https://docs.python.org/3/">
</web_fetch>
<learn_framework name="FastAPI">
</learn_framework>

12. Convocar un Equipo Multi-Agente (Swarm) o escribir en el Chat Web (`chat_db.json`):
<spawn_team mode="hybrid">
Descripción detallada de la misión
</spawn_team>
<web_chat sender="SS-TFH">
Mensaje para los visitantes conectados al chat web
</web_chat>

REGLAS DE ORO:
- Nunca inventes que un archivo se creó/editó o que una imagen se generó sin emitir primero la etiqueta correspondiente y verificar el `RESULTADO DE LAS ACCIONES`.
- Para modificar unas pocas líneas de un archivo grande, prefiere `<edit_file path="...">` con bloques `SEARCH/REPLACE`.
"""


def construir_system_prompt(prompt_usuario: str) -> Tuple[str, Dict[str, str]]:
    perfil = detectar_perfil_dios(prompt_usuario)
    os_info = f"{platform.system()} {platform.release()} ({platform.machine()})"
    prompt = (
        SYSTEM_PROMPT_TEMPLATE.replace("{GOD_TITLE}", perfil["titulo"])
        .replace("{GOD_DIRECTIVE}", perfil["directiva"])
        .replace("{OS_INFO}", os_info)
        .replace("{WORKSPACE}", str(WORKSPACE_ROOT))
        .replace("{CURRENT_DIR}", str(CURRENT_NAV_DIR))
        .replace("{LEARNED_FRAMEWORKS}", cargar_frameworks_aprendidos())
    )
    return prompt, perfil


@dataclass
class AccionAgente:
    tipo: str
    attrs: Dict[str, str]
    cuerpo: str
    inicio: int
    fin: int


XML_TOOL_RE = re.compile(
    r"^[ \t]*<(?P<tag>file|edit_file|read_file|vision|sd_image|speak|powershell|cmd|bash|bash_bg|git|web_search|web_fetch|learn_framework|spawn_team|web_chat)\b(?P<attrs>[^>\n]*)>(?P<body>.*?)</(?P=tag)\s*>",
    re.IGNORECASE | re.DOTALL | re.MULTILINE,
)

ATTR_KV_RE = re.compile(r"""(\w+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""")


def parsear_atributos(texto_attrs: str) -> Dict[str, str]:
    res: Dict[str, str] = {}
    for m in ATTR_KV_RE.finditer(texto_attrs or ""):
        clave = m.group(1).lower()
        valor = next((g for g in m.groups()[1:] if g is not None), "")
        res[clave] = valor.strip()
    return res


def _normalizar_cuerpo(cuerpo: str) -> str:
    cuerpo = cuerpo.replace("\r\n", "\n")
    cuerpo = re.sub(r"\A[ \t]*\n", "", cuerpo, count=1)
    cuerpo = re.sub(r"\n[ \t]*\Z", "", cuerpo, count=1)
    return cuerpo


def extraer_acciones(texto_ia: str) -> List[AccionAgente]:
    acciones_brutas: List[AccionAgente] = []
    limpio = limpiar_bloques_think(texto_ia)
    for m in XML_TOOL_RE.finditer(limpio):
        tag = m.group("tag").lower()
        attrs = parsear_atributos(m.group("attrs"))
        body = _normalizar_cuerpo(m.group("body"))
        acciones_brutas.append(AccionAgente(tag, attrs, body, m.start(), m.end()))

    mejores_files: Dict[str, AccionAgente] = {}
    for acc in acciones_brutas:
        if acc.tipo == "file":
            p = (acc.attrs.get("path") or acc.attrs.get("ruta") or acc.attrs.get("file") or "").strip().lower()
            if p:
                prev = mejores_files.get(p)
                if prev is None or len(acc.cuerpo) >= len(prev.cuerpo):
                    mejores_files[p] = acc

    acciones_finales: List[AccionAgente] = []
    files_vistos: set[str] = set()
    for acc in acciones_brutas:
        if acc.tipo == "file":
            p = (acc.attrs.get("path") or acc.attrs.get("ruta") or acc.attrs.get("file") or "").strip().lower()
            if p and p not in files_vistos:
                files_vistos.add(p)
                acciones_finales.append(mejores_files[p])
        else:
            acciones_finales.append(acc)

    return acciones_finales


# =============================================================================
# 8. EJECUTOR DE ACCIONES DEL AGENTE
# =============================================================================
@dataclass
class ResumenEjecucion:
    hubo_acciones: bool = False
    feedback: str = ""
    ejecutadas: int = 0
    rechazadas: int = 0
    errores: int = 0


def ejecutar_acciones_turno(
    texto_ia: str,
    telemetry: TelemetryEngine,
    swarm: SwarmCoordinator,
) -> ResumenEjecucion:
    acciones = extraer_acciones(texto_ia)
    resumen = ResumenEjecucion(hubo_acciones=bool(acciones))
    if not acciones:
        return resumen

    reportes: List[str] = []

    for acc in acciones:
        tipo = acc.tipo
        attrs = acc.attrs
        cuerpo = acc.cuerpo

        try:
            if tipo == "file":
                ruta_str = attrs.get("path") or attrs.get("ruta") or attrs.get("file") or ""
                ruta = ruta_permitida(ruta_str)
                print(f"\n{C.CYAN}[HERRAMIENTA · <file>] Archivo destino: {ruta} ({len(cuerpo)} chars){C.RESET}")
                if not pedir_confirmacion(f"¿Escribir archivo '{ruta}' ({len(cuerpo)} caracteres)?"):
                    resumen.rechazadas += 1
                    reportes.append(f"Sistema: escritura de {ruta} rechazada por el operador.")
                    continue
                escribir_archivo_atomico(ruta, cuerpo)
                resumen.ejecutadas += 1
                reportes.append(f"Sistema: archivo guardado exitosamente en {ruta} ({len(cuerpo)} caracteres).")

            elif tipo == "edit_file":
                ruta_str = attrs.get("path") or attrs.get("ruta") or attrs.get("file") or ""
                ruta = ruta_permitida(ruta_str)
                print(f"\n{C.CYAN}[HERRAMIENTA · <edit_file>] Edición quirúrgica en: {ruta}{C.RESET}")
                if not pedir_confirmacion(f"¿Aplicar edición SEARCH/REPLACE en '{ruta}'?"):
                    resumen.rechazadas += 1
                    reportes.append(f"Sistema: edición de {ruta} rechazada por el operador.")
                    continue
                msg_ed = aplicar_edicion_quirurgica(
                    ruta,
                    cuerpo,
                    search_attr=attrs.get("search", ""),
                    replace_attr=attrs.get("replace", ""),
                )
                print(f"{C.GREEN}✓ {msg_ed}{C.RESET}")
                resumen.ejecutadas += 1
                reportes.append(f"Sistema: {msg_ed}")

            elif tipo == "read_file":
                ruta_str = attrs.get("path") or attrs.get("ruta") or cuerpo.strip()
                ruta = ruta_permitida(ruta_str)
                print(f"\n{C.CYAN}[HERRAMIENTA · <read_file>] Leyendo: {ruta}{C.RESET}")
                if not ruta.is_file():
                    reportes.append(f"Sistema: el archivo {ruta} no existe.")
                else:
                    contenido = ruta.read_text(encoding="utf-8", errors="replace")
                    resumen.ejecutadas += 1
                    reportes.append(f"CONTENIDO DE {ruta}:\n{recortar(contenido, MAX_FEEDBACK)}")

            elif tipo == "vision":
                ruta_img = attrs.get("path") or attrs.get("image") or attrs.get("file") or ""
                pregunta_vis = cuerpo.strip() or attrs.get("prompt") or "Describe detalladamente esta imagen en español."
                res_vis = describir_imagen_con_vision(ruta_img, pregunta_vis, telemetry)
                resumen.ejecutadas += 1
                reportes.append(res_vis)

            elif tipo == "sd_image":
                w = int(attrs.get("width", "512"))
                h = int(attrs.get("height", "512"))
                st = int(attrs.get("steps", "20"))
                cfg = float(attrs.get("cfg", "7.0"))
                prompt_sd = attrs.get("prompt") or cuerpo.strip()
                res_sd = generar_imagen_stable_diffusion(
                    prompt_sd,
                    telemetry,
                    width=w,
                    height=h,
                    steps=st,
                    cfg_scale=cfg,
                )
                resumen.ejecutadas += 1
                reportes.append(res_sd)

            elif tipo == "speak":
                sintetizar_y_reproducir_voz(cuerpo.strip(), enviar_a_telegram=TELEGRAM.enabled)
                resumen.ejecutadas += 1
                reportes.append("Sistema: audio sintetizado y reproducido por TTS.")

            elif tipo in ("powershell", "cmd", "bash"):
                usar_ps = tipo == "powershell"
                cmd_str = cuerpo.strip()
                print(f"\n{C.CYAN}[HERRAMIENTA · <{tipo}>] Comando propuesto:\n  $ {cmd_str}{C.RESET}")
                if not pedir_confirmacion(f"¿Ejecutar comando en {tipo.upper()}?\n$ {cmd_str}"):
                    resumen.rechazadas += 1
                    reportes.append(f"Sistema: comando '{cmd_str}' rechazado por el operador.")
                    continue
                rc, salida, estado = ejecutar_comando_sistema(cmd_str, usar_powershell=usar_ps)
                print(f"{C.GREEN if rc == 0 else C.RED}[SALIDA {tipo.upper()} · rc={rc}]\n{recortar(salida, MAX_SALIDA_CONSOLA)}{C.RESET}")
                resumen.ejecutadas += 1
                reportes.append(f"Sistema: comando finalizado (rc={rc}, estado={estado}).\nSalida:\n{recortar(salida)}")

            elif tipo == "bash_bg":
                cmd_str = cuerpo.strip()
                print(f"\n{C.CYAN}[HERRAMIENTA · <bash_bg>] Servicio en segundo plano:\n  $ {cmd_str}{C.RESET}")
                if not pedir_confirmacion(f"¿Iniciar proceso en segundo plano?\n$ {cmd_str}"):
                    resumen.rechazadas += 1
                    reportes.append("Sistema: servicio en segundo plano rechazado.")
                    continue
                info = iniciar_servicio_fondo(cmd_str)
                time.sleep(1.2)
                rc = info.popen.poll()
                resumen.ejecutadas += 1
                if rc is not None:
                    reportes.append(f"Sistema: el proceso terminó inmediatamente con código {rc}. Log: {info.log}")
                else:
                    reportes.append(f"Sistema: servicio activo con PID={info.pid}. Log: {info.log}")

            elif tipo == "git":
                op = attrs.get("op", "status")
                print(f"\n{C.CYAN}[HERRAMIENTA · <git op=\"{op}\">]{C.RESET}")
                if op not in ("status", "diff", "log") and not pedir_confirmacion(f"¿Ejecutar operación Git '{op}'?"):
                    resumen.rechazadas += 1
                    reportes.append(f"Sistema: operación git '{op}' rechazada.")
                    continue
                out_git = GitOpsManager.execute_git_action(attrs, cuerpo)
                print(f"{C.GREEN}{recortar(out_git, MAX_SALIDA_CONSOLA)}{C.RESET}")
                resumen.ejecutadas += 1
                reportes.append(out_git)

            elif tipo == "web_search":
                q = attrs.get("query") or attrs.get("q") or cuerpo.strip()
                out_web = buscar_en_web(q)
                resumen.ejecutadas += 1
                reportes.append(out_web)

            elif tipo == "web_fetch":
                url = attrs.get("url") or cuerpo.strip()
                out_fetch = leer_pagina_web(url)
                resumen.ejecutadas += 1
                reportes.append(out_fetch)

            elif tipo == "learn_framework":
                fw_name = attrs.get("name") or attrs.get("framework") or cuerpo.strip()
                out_fw = aprender_framework(fw_name, telemetry)
                resumen.ejecutadas += 1
                reportes.append(out_fw)

            elif tipo == "spawn_team":
                mode = attrs.get("mode", "hybrid")
                goal = attrs.get("mission") or cuerpo.strip()
                out_swarm = swarm.execute_mission(goal, mode=mode)
                resumen.ejecutadas += 1
                reportes.append(out_swarm)

            elif tipo == "web_chat":
                sender = attrs.get("sender") or ADMIN_WEB_HANDLE
                ok = WEB_CHAT.post_message(cuerpo.strip(), sender=sender)
                resumen.ejecutadas += 1 if ok else 0
                reportes.append(
                    f"Sistema: mensaje publicado en chat_db.json como '{sender}'."
                    if ok else "Sistema: error al publicar en chat_db.json."
                )

        except Exception as exc:
            resumen.errores += 1
            err_txt = f"Sistema: error ejecutando <{tipo}>: {exc}"
            print(f"{C.RED}{err_txt}{C.RESET}")
            reportes.append(err_txt)

    resumen.feedback = recortar("\n\n".join(reportes), MAX_FEEDBACK * 2)
    return resumen


# =============================================================================
# 9. BUCLE PRINCIPAL DE ORQUESTACIÓN Y COMANDOS MULTIMODALES / ARCHIVADOR
# =============================================================================
def mostrar_ayuda_comandos() -> str:
    return (
        f"\n{C.BOLD}{C.CYAN}=== SUITE MULTIMODAL Y ARCHIVADOR DE TERMINAL (ARYI OMEGA v10.0) ==={C.RESET}\n"
        f"{C.YELLOW}🎨 VISIÓN, IMAGEN Y VOZ (WHISPER + OLLAMA + TTS + STABLE DIFFUSION):{C.RESET}\n"
        "  /vision <img_path> [pregunta] Describe o analiza una imagen con `llava-phi3` / `moondream`.\n"
        "  /screenshot [pregunta]        Captura tu pantalla de Windows en vivo y la analiza con Visión.\n"
        "  /imagine <prompt>             Genera una imagen en Stable Diffusion (:7860), libera VRAM y la envía a Telegram.\n"
        "  /voice [segundos]             Graba tu micrófono en Windows, transcribe en Whisper (:8000), responde y habla por TTS (:5050).\n"
        "  /talk                         Modo conversación de voz continua manos libres (hablas -> responde por voz -> vuelve a escuchar).\n"
        "  /say <texto>                  Sintetiza y reproduce cualquier texto por el motor de voz TTS.\n"
        "  /tts on | off                 Activa o desactiva la lectura por voz automática en todas las respuestas.\n\n"
        f"{C.YELLOW}📂 ARCHIVADOR Y EDITOR COMPLETO DESDE COMANDOS:{C.RESET}\n"
        "  /files [ruta]  (o /ls)        Lista archivos/carpetas con tamaños y fechas en el directorio activo.\n"
        "  /cd <ruta>                    Cambia el directorio activo del Archivador.\n"
        "  /cat <archivo> [ini] [fin]    Muestra el contenido numerado de un archivo.\n"
        "  /edit <archivo>               Abre el Editor Interactivo en Consola (o `/edit --notepad <f>`, `/edit --code <f>`).\n"
        "  /patch <archivo> <viejo>|<nv> Reemplaza texto directamente en un archivo.\n"
        "  /search <texto>               Busca texto dentro de todos los archivos del proyecto.\n"
        "  /mkdir <dir> | /touch <file>  Crea una carpeta o un archivo vacío.\n"
        "  /cp <a> <b>  | /mv <a> <b>    Copia o mueve/renombra archivos o carpetas.\n"
        "  /rm <ruta>                    Elimina un archivo o carpeta (con confirmación).\n\n"
        f"{C.YELLOW}⚙️ ORQUESTACIÓN, TELEMETRÍA, VRAM Y LOGS:{C.RESET}\n"
        "  /mission <objetivo>           Escanea el proyecto real, convoca al equipo multi-agente y materializa cambios.\n"
        "  /health                       Diagnóstico de latencia de los 4 contenedores (Whisper, Ollama, TTS, SD) y VRAM.\n"
        "  /vram free                    Descarga todos los modelos de Ollama (`keep_alive: 0`) para liberar los 6GB de VRAM.\n"
        "  /logs [N] | /logs follow      Muestra logs en vivo o abre ventana PowerShell estilo `docker logs -f`.\n"
        "  /telemetry | /models          Benchmark y tabla de modelos clasificados.\n"
        "  /learn <framework>            Investiga un framework en la web en tiempo real y guarda Cheat-Sheet.\n"
        "  /web <mensaje>                Publica como 'SS-TFH' en `chat_monolitico.php` (`chat_db.json`).\n"
        "  /auto on | off                Activa/desactiva ejecución 100% autónoma sin pedir confirmación.\n"
        "  salir | exit                  Cierra el orquestador.\n"
    )


def seleccionar_endpoint() -> str:
    env_url = os.getenv("ARYI_OLLAMA_URL", "").strip()
    if env_url:
        return env_url.rstrip("/")

    for key in ("2", "1"):
        cand = ENDPOINTS[key]["url"].rstrip("/")
        try:
            r = HTTP.get(f"{cand}/tags", timeout=(3, 5))
            if r.status_code == 200:
                print(f"{C.GREEN}[CONEXIÓN] Nodo Ollama detectado automáticamente: {ENDPOINTS[key]['nombre']}{C.RESET}")
                log_event("CONNECT", f"Conectado a {cand}")
                return cand
        except Exception:
            continue

    return ENDPOINTS["2"]["url"].rstrip("/")


def obtener_siguiente_entrada() -> Optional[Tuple[str, str]]:
    rel_dir = "." if CURRENT_NAV_DIR == WORKSPACE_ROOT else str(CURRENT_NAV_DIR.name)
    print(f"\n{C.BOLD}{C.GREEN}ARYI [{rel_dir}] (Consola / Voz / Telegram) > {C.RESET}", end="", flush=True)
    while True:
        try:
            linea_consola = CONSOLE_LINE_QUEUE.get_nowait()
            if linea_consola == "__EOF__":
                return ("eof", "")
            return ("consola", linea_consola)
        except queue.Empty:
            pass

        try:
            origen_ext, msg_ext = SHARED_INBOX.get_nowait()
            print(f"\n{C.CYAN}[{origen_ext.upper()} -> ARYI]: {msg_ext}{C.RESET}")
            return (origen_ext, msg_ext)
        except queue.Empty:
            pass

        time.sleep(0.12)


def main() -> None:
    global AUTO_APPROVE, AUTO_TTS_SPEAK, CURRENT_NAV_DIR

    log_event("BOOT", f"Iniciando ARYI OMEGA v10.0 en {WORKSPACE_ROOT}")
    print(f"{C.BOLD}{C.CYAN}" + "=" * 82)
    print("  ARYI OMEGA v10.0 · MULTIMODAL TERMINAL (VISION + WHISPER + TTS + SD + ARCHIVADOR)")
    print("=" * 82 + f"{C.RESET}")
    print(f"  • Sistema Operativo : {platform.system()} {platform.release()} ({platform.machine()})")
    print(f"  • Workspace Raíz    : {WORKSPACE_ROOT}")
    print(f"  • Live Log Stream   : {LIVE_LOG_FILE} (usa `/logs` o `/logs follow`)")
    print(f"  • Modo Autónomo     : {'ACTIVO (AUTO-APPROVE)' if AUTO_APPROVE else 'SUPERVISADO (usa /auto on para delegar 100%)'}")
    print(f"  • Telegram Bridge   : {'ACTIVO (Chat ID ' + TELEGRAM_CHAT_ID + ' · Texto/Fotos/Voz)' if TELEGRAM.enabled else 'DESACTIVADO'}")

    api_base = seleccionar_endpoint()
    print(reporte_salud_cluster(api_base))

    telemetry = TelemetryEngine(api_base)
    telemetry.run_full_telemetry(force=False)
    print(telemetry.summary_table())

    swarm = SwarmCoordinator(telemetry)
    WEB_CHAT.start()
    TELEGRAM.start()

    print(mostrar_ayuda_comandos())

    historial: List[Dict[str, str]] = []
    modo_talk_continuo = False

    while True:
        try:
            if modo_talk_continuo:
                print(f"\n{C.MAGENTA}🎙️ [MODO CONVERSACIÓN CONTINUA] Grabando 6s (escribe `stop` o presiona Ctrl+C para salir del modo continuo)...{C.RESET}")
                wav_grabado = grabar_microfono_windows_wav(segundos=6)
                if not wav_grabado:
                    modo_talk_continuo = False
                    continue
                texto_voz = transcribir_audio_whisper(wav_grabado)
                if not texto_voz or texto_voz.lower().strip(".!") in {"salir", "detente", "para", "cancela", "stop"}:
                    print(f"{C.YELLOW}[VOZ] Fin de conversación continua.{C.RESET}")
                    modo_talk_continuo = False
                    continue
                print(f"{C.GREEN}🗣️ Tú dijiste: \"{texto_voz}\"{C.RESET}")
                origen, texto = ("voice", texto_voz)
            else:
                par = obtener_siguiente_entrada()
                if not par:
                    continue
                origen, texto = par
        except KeyboardInterrupt:
            if modo_talk_continuo:
                modo_talk_continuo = False
                print(f"\n{C.YELLOW}[VOZ] Modo conversación continua detenido.{C.RESET}")
                continue
            break

        if origen == "eof":
            break

        # Si llegó una nota de voz desde Telegram, transcribirla primero en Whisper STT
        if origen == "telegram_voice":
            aud_file = Path(texto)
            transcripcion = transcribir_audio_whisper(aud_file)
            if not transcripcion:
                TELEGRAM.send("❌ No pude transcribir la nota de voz en Whisper STT (:8000).")
                continue
            TELEGRAM.send(f"👂 *Transcripción Whisper:* \"{transcripcion}\"")
            origen = "telegram"
            texto = transcripcion
            AUTO_TTS_SPEAK = True  # Responder también con voz

        texto = texto.strip()
        if not texto:
            continue

        low = texto.lower()
        if low in {"salir", "exit", "/exit"}:
            break

        # --- 1. COMANDOS DE AYUDA, LOGS, SALUD Y VRAM ---
        if low in {"/help", "ayuda"}:
            msg = mostrar_ayuda_comandos()
            print(msg)
            if origen == "telegram":
                TELEGRAM.send(msg)
            continue

        if low == "/health":
            rep_h = reporte_salud_cluster(api_base)
            print(rep_h)
            if origen == "telegram":
                TELEGRAM.send(re.sub(r"\033\[[0-9;]*m", "", rep_h))
            continue

        if low.startswith("/vram"):
            descargados = liberar_vram_ollama(api_base, fallback_models=list(telemetry.models.keys())[:4])
            msg_v = f"🧹 Memoria VRAM de Ollama liberada (`keep_alive: 0`). Modelos descargados: {', '.join(descargados) or 'ninguno activo'}."
            print(f"{C.GREEN}{msg_v}{C.RESET}")
            if origen == "telegram":
                TELEGRAM.send(msg_v)
            continue

        if low.startswith("/logs"):
            partes_cmd = low.split()
            if len(partes_cmd) > 1 and partes_cmd[1] in {"follow", "-f", "live", "window"}:
                res_follow = abrir_visor_logs_en_vivo()
                print(res_follow)
                if origen == "telegram":
                    TELEGRAM.send(res_follow)
            else:
                n_lines = 35
                if len(partes_cmd) > 1 and partes_cmd[1].isdigit():
                    n_lines = int(partes_cmd[1])
                salida_logs = leer_ultimos_logs(n_lines)
                print(salida_logs)
                if origen == "telegram":
                    TELEGRAM.send(recortar(salida_logs, 3500))
            continue

        # --- 2. COMANDOS MULTIMODALES: VISIÓN, SCREENSHOT, STABLE DIFFUSION Y VOZ ---
        if low.startswith("/vision "):
            resto_v = texto[8:].strip()
            m_q = re.match(r'^"([^"]+)"\s*(.*)$', resto_v) or re.match(r"^'([^']+)'\s*(.*)$", resto_v)
            if m_q:
                img_p, preg_v = m_q.group(1), m_q.group(2)
            else:
                partes_v = resto_v.split(None, 1)
                img_p = partes_v[0] if partes_v else ""
                preg_v = partes_v[1] if len(partes_v) > 1 else "Describe detalladamente esta imagen en español."
            res_vis = describir_imagen_con_vision(img_p, preg_v, telemetry)
            print(res_vis)
            if origen == "telegram" or TELEGRAM.enabled:
                TELEGRAM.send(recortar(res_vis, 3500))
            if AUTO_TTS_SPEAK:
                sintetizar_y_reproducir_voz(res_vis)
            continue

        if low.startswith("/screenshot"):
            preg_sc = texto[11:].strip() or "Describe detalladamente qué hay en mi pantalla en este momento."
            print(f"{C.CYAN}📸 Capturando pantalla principal de Windows...{C.RESET}")
            sc_path = capturar_pantalla_windows()
            if not sc_path:
                print(f"{C.RED}❌ No se pudo capturar la pantalla.{C.RESET}")
                continue
            if TELEGRAM.enabled:
                TELEGRAM.send_photo(sc_path, caption="📸 Captura de pantalla tomada por ARYI")
            res_sc = describir_imagen_con_vision(str(sc_path), preg_sc, telemetry)
            print(res_sc)
            if TELEGRAM.enabled:
                TELEGRAM.send(recortar(res_sc, 3500))
            continue

        if low.startswith("/imagine ") or low.startswith("/sd "):
            prompt_img = texto.split(None, 1)[1].strip() if " " in texto else ""
            if origen == "telegram":
                TELEGRAM.send(f"🎨 Generando imagen en Stable Diffusion para: '{prompt_img}'...")
            res_img = generar_imagen_stable_diffusion(prompt_img, telemetry)
            print(res_img)
            if AUTO_TTS_SPEAK:
                sintetizar_y_reproducir_voz("Aquí tienes tu imagen generada.")
            continue

        if low.startswith("/say "):
            txt_say = texto[5:].strip()
            sintetizar_y_reproducir_voz(txt_say, enviar_a_telegram=(origen == "telegram"))
            continue

        if low.startswith("/tts"):
            AUTO_TTS_SPEAK = "on" in low or "1" in low or "true" in low
            msg_tts = f"Lectura por voz automática (TTS): {'ACTIVADA' if AUTO_TTS_SPEAK else 'DESACTIVADA'}"
            print(f"{C.GREEN}[VOZ] {msg_tts}{C.RESET}")
            if origen == "telegram":
                TELEGRAM.send(f"🗣️ {msg_tts}")
            continue

        if low == "/talk":
            modo_talk_continuo = True
            AUTO_TTS_SPEAK = True
            print(f"{C.GREEN}🎙️ Modo Conversación Continua ACTIVADO. Habla cuando veas el aviso.{C.RESET}")
            continue

        if low.startswith("/voice"):
            partes_vc = low.split()
            seg_vc = int(partes_vc[1]) if len(partes_vc) > 1 and partes_vc[1].isdigit() else 0
            wav_vc = grabar_microfono_windows_wav(segundos=seg_vc)
            if not wav_vc:
                print(f"{C.RED}❌ No se pudo grabar audio del micrófono.{C.RESET}")
                continue
            trans_vc = transcribir_audio_whisper(wav_vc)
            if not trans_vc:
                print(f"{C.RED}❌ Whisper STT no detectó voz clara.{C.RESET}")
                continue
            print(f"{C.GREEN}🗣️ Transcripción Whisper: \"{trans_vc}\"{C.RESET}")
            texto = trans_vc
            origen = "voice"

        # --- 3. COMANDOS DEL ARCHIVADOR Y EDITOR COMPLETO EN TERMINAL ---
        if low in {"/files", "/ls", "ls", "dir"} or low.startswith("/files ") or low.startswith("/ls "):
            arg_f = texto.split(None, 1)[1].strip() if " " in texto else ""
            out_ls = TerminalArchivador.listar_directorio(arg_f)
            print(out_ls)
            if origen == "telegram":
                TELEGRAM.send(re.sub(r"\033\[[0-9;]*m", "", recortar(out_ls, 3500)))
            continue

        if low.startswith("/cd "):
            dest_cd = texto[4:].strip()
            try:
                nuevo_dir = ruta_permitida(dest_cd, base_dir=CURRENT_NAV_DIR)
                if nuevo_dir.is_dir():
                    CURRENT_NAV_DIR = nuevo_dir
                    print(TerminalArchivador.listar_directorio(""))
                else:
                    print(f"{C.RED}❌ No es un directorio: {nuevo_dir}{C.RESET}")
            except Exception as e:
                print(f"{C.RED}❌ {e}{C.RESET}")
            continue

        if low.startswith("/cat "):
            partes_cat = texto[5:].strip().split()
            if partes_cat:
                ini_c = int(partes_cat[1]) if len(partes_cat) > 1 and partes_cat[1].isdigit() else 1
                fin_c = int(partes_cat[2]) if len(partes_cat) > 2 and partes_cat[2].isdigit() else ini_c + 140
                out_cat = TerminalArchivador.ver_archivo_numerado(partes_cat[0], ini_c, fin_c)
                print(out_cat)
                if origen == "telegram":
                    TELEGRAM.send(re.sub(r"\033\[[0-9;]*m", "", recortar(out_cat, 3500)))
            continue

        if low.startswith("/edit "):
            out_ed = TerminalArchivador.editor_interactivo_consola(texto[6:])
            print(out_ed)
            continue

        if low.startswith("/patch "):
            # Formato: /patch <archivo> <texto_viejo>|<texto_nuevo>
            resto_p = texto[7:].strip()
            partes_p = resto_p.split(None, 1)
            if len(partes_p) == 2 and "|" in partes_p[1]:
                f_patch = ruta_permitida(partes_p[0], base_dir=CURRENT_NAV_DIR)
                v_str, n_str = partes_p[1].split("|", 1)
                try:
                    msg_p = aplicar_edicion_quirurgica(f_patch, "", search_attr=v_str, replace_attr=n_str)
                    print(f"{C.GREEN}✅ {msg_p}{C.RESET}")
                except Exception as e:
                    print(f"{C.RED}❌ {e}{C.RESET}")
            else:
                print("Uso: /patch <archivo> <texto_buscar>|<texto_reemplazar>")
            continue

        if low.startswith("/search "):
            out_sr = TerminalArchivador.buscar_en_archivos(texto[8:])
            print(out_sr)
            if origen == "telegram":
                TELEGRAM.send(recortar(out_sr, 3500))
            continue

        if low.startswith("/mkdir "):
            d_mk = ruta_permitida(texto[7:].strip(), base_dir=CURRENT_NAV_DIR)
            d_mk.mkdir(parents=True, exist_ok=True)
            print(f"{C.GREEN}📁 Carpeta creada: {d_mk}{C.RESET}")
            continue

        if low.startswith("/touch "):
            f_tc = ruta_permitida(texto[7:].strip(), base_dir=CURRENT_NAV_DIR)
            if not f_tc.exists():
                escribir_archivo_atomico(f_tc, "")
            print(f"{C.GREEN}📄 Archivo listo: {f_tc}{C.RESET}")
            continue

        if low.startswith("/cp ") or low.startswith("/mv "):
            es_mv = low.startswith("/mv ")
            partes_cm = texto[4:].strip().split()
            if len(partes_cm) >= 2:
                src_p = ruta_permitida(partes_cm[0], base_dir=CURRENT_NAV_DIR)
                dst_p = ruta_permitida(partes_cm[1], base_dir=CURRENT_NAV_DIR)
                if es_mv:
                    shutil.move(str(src_p), str(dst_p))
                    print(f"{C.GREEN}✅ Movido/renombrado: {src_p.name} -> {dst_p}{C.RESET}")
                else:
                    if src_p.is_dir():
                        shutil.copytree(str(src_p), str(dst_p), dirs_exist_ok=True)
                    else:
                        shutil.copy2(str(src_p), str(dst_p))
                    print(f"{C.GREEN}✅ Copiado: {src_p.name} -> {dst_p}{C.RESET}")
            continue

        if low.startswith("/rm "):
            target_rm = ruta_permitida(texto[4:].strip(), base_dir=CURRENT_NAV_DIR)
            if target_rm == WORKSPACE_ROOT:
                print(f"{C.RED}❌ No puedes borrar la raíz del workspace.{C.RESET}")
                continue
            if pedir_confirmacion(f"¿Eliminar permanentemente '{target_rm}'?"):
                if target_rm.is_dir():
                    shutil.rmtree(str(target_rm))
                elif target_rm.exists():
                    target_rm.unlink()
                print(f"{C.GREEN}🗑️ Eliminado: {target_rm}{C.RESET}")
            continue

        # --- 4. COMANDOS DE TELEMETRÍA, SISTEMA Y MISIONES ---
        if low == "/telemetry":
            if origen == "telegram":
                TELEGRAM.send("⚡ Ejecutando prueba telemétrica en todos los modelos del clúster...")
            telemetry.run_full_telemetry(force=True)
            tabla = telemetry.summary_table()
            print(tabla)
            if origen == "telegram":
                TELEGRAM.send(f"📊 Telemetría actualizada:\n{tabla}")
            continue

        if low == "/models":
            tabla = telemetry.summary_table()
            print(tabla)
            if origen == "telegram":
                TELEGRAM.send(tabla)
            continue

        if low.startswith("/web "):
            msg_web = texto[5:].strip()
            if msg_web and WEB_CHAT.post_message(msg_web, sender=ADMIN_WEB_HANDLE):
                print(f"{C.GREEN}[WEBCHAT] Mensaje enviado como {ADMIN_WEB_HANDLE} a {CHAT_DB_FILE}.{C.RESET}")
                if origen == "telegram":
                    TELEGRAM.send(f"💬 Publicado en chat_db.json ({ADMIN_WEB_HANDLE}): {msg_web}")
            continue

        if low.startswith("/auto"):
            AUTO_APPROVE = "on" in low or "1" in low or "true" in low
            estado_txt = f"Modo Autónomo (AUTO-APPROVE): {'ACTIVADO' if AUTO_APPROVE else 'DESACTIVADO'}"
            print(f"{C.GREEN}[SISTEMA] {estado_txt}{C.RESET}")
            log_event("MODE", estado_txt)
            if TELEGRAM.enabled:
                TELEGRAM.send(f"⚙️ {estado_txt}")
            continue

        if low == "/ps":
            ps_txt = listar_procesos_fondo()
            print(ps_txt)
            if origen == "telegram":
                TELEGRAM.send(ps_txt)
            continue

        if low == "/status":
            arch_m, _ = telemetry.select_best_model_for_role("architect")
            code_m, _ = telemetry.select_best_model_for_role("coder")
            vis_m, _ = telemetry.select_best_model_for_role("vision")
            git_m, _ = telemetry.select_best_model_for_role("gitops")
            st = (
                f"Estado ARYI OMEGA v10.0:\n"
                f"• Workspace: {WORKSPACE_ROOT}\n"
                f"• Directorio Archivador: {CURRENT_NAV_DIR}\n"
                f"• Live Log: {LIVE_LOG_FILE}\n"
                f"• Auto-Approve: {AUTO_APPROVE} | Auto-TTS: {AUTO_TTS_SPEAK}\n"
                f"• Modelo Arquitecto: {arch_m}\n"
                f"• Modelo Coder: {code_m}\n"
                f"• Modelo Visión: {vis_m}\n"
                f"• Modelo GitOps: {git_m}\n"
                f"• Frameworks Aprendidos: {cargar_frameworks_aprendidos()}\n"
                + reporte_salud_cluster(api_base)
            )
            print(st)
            if origen == "telegram":
                TELEGRAM.send(re.sub(r"\033\[[0-9;]*m", "", st))
            continue

        if low.startswith("/learn "):
            fw = texto[7:].strip()
            if origen == "telegram":
                TELEGRAM.send(f"📚 Aprendiendo framework '{fw}' en tiempo real...")
            res_fw = aprender_framework(fw, telemetry)
            print(res_fw)
            if origen == "telegram":
                TELEGRAM.send(recortar(res_fw, 3500))
            continue

        if low.startswith("/mission "):
            objetivo = texto[9:].strip()
            if origen == "telegram":
                TELEGRAM.send(f"🚀 Iniciando Misión Multi-Agente (con escaneo real de proyecto) para: {objetivo}")
            reporte_mision = swarm.execute_mission(objetivo, mode="hybrid")
            res_directo = ejecutar_acciones_turno(reporte_mision, telemetry, swarm)
            if res_directo.hubo_acciones:
                print(
                    f"\n{C.GREEN}✓ [SWARM] Acciones materializadas desde el equipo "
                    f"(Ejecutadas: {res_directo.ejecutadas}, Rechazadas: {res_directo.rechazadas}).{C.RESET}"
                )
                if TELEGRAM.enabled:
                    TELEGRAM.send(f"✅ Misión completada:\n{recortar(res_directo.feedback, 2500)}")
                continue

            texto = (
                f"El equipo multi-agente ha diseñado la siguiente solución para la misión '{objetivo}'.\n"
                f"Materializa inmediatamente en el workspace los archivos (`<file>`), ediciones (`<edit_file>`) y operaciones Git (`<git>`) necesarias:\n\n"
                f"{recortar(reporte_mision, 5000)}"
            )

        # --- DETECCIÓN DE INTENCIONES NATURALES DE VOZ/TEXTO (IGUAL QUE EN ARYI_UI.PHP) ---
        m_draw = re.match(r"^(?:dibuja|dib[uú]jame|pinta|p[ií]ntame)\s+(.+)$", low) or re.match(
            r"^(?:genera|crea|haz|hazme)\s+(?:una?\s+)?(?:imagen|foto|ilustraci[oó]n|dibujo|render)\s+(?:de\s+|del\s+|con\s+)?(.+)$",
            low,
        )
        if m_draw:
            res_nat_sd = generar_imagen_stable_diffusion(m_draw.group(1), telemetry)
            print(res_nat_sd)
            if origen == "voice" or AUTO_TTS_SPEAK:
                sintetizar_y_reproducir_voz("Aquí tienes tu imagen generada.")
            continue

        if re.search(r"(libera|limpia|vac[ií]a).{0,25}(vram|memoria de video)", low):
            liberar_vram_ollama(api_base, fallback_models=list(telemetry.models.keys())[:4])
            msg_nat_v = "Listo, liberé la memoria de video de Ollama."
            print(f"{C.GREEN}{msg_nat_v}{C.RESET}")
            if origen == "voice" or AUTO_TTS_SPEAK:
                sintetizar_y_reproducir_voz(msg_nat_v)
            continue

        # --- 5. EJECUCIÓN CONVERSACIONAL Y DE HERRAMIENTAS EN OLLAMA ---
        sys_prompt, perfil = construir_system_prompt(texto)
        candidatos_turno = [m.name for m in telemetry.rank_models_for_role(perfil["role_type"])]
        modelo_primario, limite_ctx = telemetry.select_best_model_for_role(perfil["role_type"])

        if not historial:
            historial.append({"role": "system", "content": sys_prompt})
        else:
            historial[0] = {"role": "system", "content": sys_prompt}

        historial.append({"role": "user", "content": texto})

        print(
            f"\n{C.MAGENTA}⚡ [ORQUESTADOR] Perfil activo: {C.BOLD}{perfil['titulo']}{C.RESET}\n"
            f"{C.MAGENTA}⚡ [TELEMETRÍA] Modelo primario: {C.BOLD}{modelo_primario}{C.RESET} (safe_ctx: {limite_ctx} tokens)"
        )

        for paso in range(1, PASOS_MAXIMOS + 1):
            while len(historial) > 3 and sum(estimar_tokens(m["content"]) for m in historial) > int(limite_ctx * 0.70):
                historial.pop(1)

            try:
                encabezado = f"\n{C.BOLD}{C.BLUE}[{modelo_primario} · Paso {paso}/{PASOS_MAXIMOS}]{C.RESET}\n"
                respuesta_ia, modelo_real = llamar_ollama_resiliente(
                    api_base=api_base,
                    modelos_candidatos=candidatos_turno,
                    mensajes=historial,
                    limite_tokens=limite_ctx,
                    temperatura=0.15,
                    prefijo_stream=encabezado,
                )
            except KeyboardInterrupt:
                print(f"\n{C.YELLOW}[SISTEMA] Generación interrumpida por el usuario.{C.RESET}")
                break
            except Exception as exc:
                err_msg = f"[ERROR OLLAMA] {exc}"
                print(f"\n{C.RED}{err_msg}{C.RESET}")
                if origen == "telegram":
                    TELEGRAM.send(err_msg)
                break

            historial.append({"role": "assistant", "content": respuesta_ia})

            if origen == "telegram" or TELEGRAM.enabled:
                TELEGRAM.send(f"🤖 [{modelo_real} · Paso {paso}]\n{recortar(respuesta_ia, 3500)}")

            if origen == "webchat":
                limpia_web = XML_TOOL_RE.sub("", limpiar_bloques_think(respuesta_ia)).strip()
                if limpia_web:
                    WEB_CHAT.post_message(recortar(limpia_web, 1200), sender="ARYI_OMEGA")

            resumen = ejecutar_acciones_turno(respuesta_ia, telemetry, swarm)

            # Si el turno fue iniciado por micrófono (`/voice` o `/talk`) o está activo `/tts on`, hablar la respuesta final
            if not resumen.hubo_acciones:
                if origen == "voice" or AUTO_TTS_SPEAK:
                    sintetizar_y_reproducir_voz(respuesta_ia, enviar_a_telegram=(origen == "telegram"))
                break

            feedback_msg = (
                f"RESULTADO DE LAS ACCIONES (Ejecutadas: {resumen.ejecutadas}, "
                f"Rechazadas: {resumen.rechazadas}, Errores: {resumen.errores}):\n\n"
                f"{resumen.feedback}\n\n"
                "Analiza el resultado anterior. Si hubo algún error de compilación/ejecución, corrígelo. "
                "Si la tarea ya está completa y verificada, presenta el informe final sin etiquetas de acción."
            )
            historial.append({"role": "user", "content": feedback_msg})

            if TELEGRAM.enabled:
                TELEGRAM.send(f"🛠️ Resultado de Herramientas (Paso {paso}):\n{recortar(resumen.feedback, 2500)}")

    TELEGRAM.stop()
    log_event("SHUTDOWN", "ARYI OMEGA finalizado limpiamente")
    print(f"\n{C.CYAN}[SISTEMA] ARYI OMEGA finalizado limpiamente.{C.RESET}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{C.CYAN}[SISTEMA] Sesión terminada por el operador.{C.RESET}")