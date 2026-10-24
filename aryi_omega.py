#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
 ARYI OMEGA v8.5 · WINDOWS NATIVE AUTONOMOUS AGENT & MULTI-MODEL SWARM ORCHESTRATOR
================================================================================
 Fusión evolucionada de `rg.py` (Orquestador Maestro v7), `aryi.py` (Multi-Agent
 Pipeline) y sincronización con `chat_monolitico.php` (SSE + Telegram Bridge),
 diseñada para correr de forma 100% nativa en Windows (PowerShell / CMD) y Linux,
 sin dependencias pesadas obligatorias (solo Python 3.8+ y `requests`).

 NOVEDADES CRÍTICAS EN v8.5 (ANTI-500 OOM & GGUF COMPATIBILITY):
 1. BLINDAJE CONTRA ERROR 500 DE OLLAMA EN MODELOS GRANDES (30B / 35B MoE / GGUF):
    - Techo dinámico de KV-Cache (`num_ctx`): modelos >= 25B (`aratan/Ornith-1.5-35B`,
      `qwen3-coder:30b`) usan `num_ctx=4096` o `8192` para no desbordar la VRAM al
      reservar el buffer de contexto.
    - Fallback automático `/api/chat` -> `/api/generate`: modelos GGUF importados de
      HuggingFace que carecen de plantilla `role: system` o `chat_template` en Ollama
      convierten automáticamente la conversación a prompt plano en `/api/generate`.
    - Auto-Failover entre modelos del clúster: si un modelo falla o devuelve HTTP 500,
      reintenta reduciendo `num_ctx` y, si persiste, conmuta automáticamente al siguiente
      mejor modelo disponible en la matriz telemétrica sin abortar la misión.
 2. GESTIÓN INTELIGENTE DE VRAM EN SWARM:
    - Cuando una misión convoca modelos pesados (>15B), serializa su paso por la GPU
      para evitar colisiones de carga/descarga simultánea de decenas de GB en VRAM.
 3. FILTRO DE PENSAMIENTO (`<think>...</think>`) Y AUTO-INSPECCIÓN:
    - Limpia bloques `<think>` al extraer JSON/herramientas y permite que el agente lea
      su propio código fuente (`aryi_omega.py`) cuando le pides documentarse o mejorarse.
================================================================================
"""

from __future__ import annotations

import concurrent.futures
import html
import json
import os
import platform
import queue
import re
import shutil
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
# CONFIGURACIÓN GLOBAL Y ENTORNOS
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
IP_WINDOWS_GPU = os.getenv("ARYI_WINDOWS_GPU_IP", "100.115.1.71")

ENDPOINTS: Dict[str, Dict[str, str]] = {
    "1": {"nombre": "Localhost (127.0.0.1:11434)", "url": "http://127.0.0.1:11434/api"},
    "2": {"nombre": f"Nodo GPU Remoto ({IP_WINDOWS_GPU}:11434)", "url": f"http://{IP_WINDOWS_GPU}:11434/api"},
}


def _get_default_workspace() -> Path:
    # Si se ejecuta dentro de una carpeta de proyecto existente (ej. C:\SyntaxSanctuary\PROYECTO\public\TheBot),
    # incluir también el directorio actual como raíz permitida.
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

MEMORY_DIR = WORKSPACE_ROOT / ".aryi_memory"
FRAMEWORKS_DIR = MEMORY_DIR / "frameworks"
MISSIONS_DIR = MEMORY_DIR / "missions"
for _d in (MEMORY_DIR, FRAMEWORKS_DIR, MISSIONS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

TELEMETRY_FILE = LOGS_DIR / "telemetry_matrix.json"


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

MAX_FEEDBACK = _env_int("ARYI_MAX_FEEDBACK", 8_000)
MAX_SALIDA_CONSOLA = 2_500
TIMEOUT_CMD = _env_int("ARYI_TIMEOUT_BASH", 180)
TIMEOUT_HTTP_CONNECT = 10
TIMEOUT_HTTP_READ = _env_int("ARYI_HTTP_READ", 360)
PASOS_MAXIMOS = max(1, _env_int("ARYI_PASOS_MAXIMOS", 10))
AUTO_APPROVE = _env_bool("ARYI_AUTO_APPROVE", False)

# Credenciales de Telegram integradas desde tu `chat_monolitico.php` (sobreescribibles por entorno)
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

# Candado global de inferencia pesada para evitar que 2 modelos gigantes colisionen en VRAM simultáneamente
GPU_INFERENCE_LOCK = threading.Lock()


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
    """Elimina bloques <think>...</think> de modelos razonadores al parsear JSON."""
    return re.sub(r"<think>.*?</think>", "", texto or "", flags=re.DOTALL | re.IGNORECASE).strip()


def ruta_permitida(ruta_bruta: str) -> Path:
    limpia = (ruta_bruta or "").strip().strip("\"'")
    if not limpia or "\x00" in limpia:
        raise ValueError("Ruta vacía o inválida.")
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
    raise PermissionError(f"Ruta fuera de las raíces permitidas ({WORKSPACE_ROOT}): {candidata}")


def auditar(evento: str, detalle: str, resultado: str) -> None:
    try:
        registro = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "evento": evento,
            "detalle": detalle[:600],
            "resultado": resultado[:300],
        }
        with open(LOGS_DIR / "auditoria.jsonl", "a", encoding="utf-8") as f:
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


# =============================================================================
# PUENTE BIDIRECCIONAL CON TELEGRAM Y PUENTE CON `chat_db.json` (PHP SSE)
# =============================================================================
class WebChatDBBridge:
    """Se conecta directamente con el archivo `chat_db.json` de tu `chat_monolitico.php`."""

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
                                    if body.lower().startswith("@aryi"):
                                        clean_task = body[5:].strip()
                                        if clean_task:
                                            self.inbox.put(("webchat", f"[Visitante Web {sender}]: {clean_task}"))
            except Exception:
                pass
            time.sleep(1.0)


class TelegramBridge:
    """Gestiona la comunicación en tiempo real con el usuario vía Telegram (`8449908090:...` / `8933548802`)."""

    def __init__(self, token: str, allowed_chat_id: str, web_bridge: Optional[WebChatDBBridge] = None):
        self.token = token.strip()
        self.chat_id = str(allowed_chat_id).strip()
        self.enabled = bool(self.token)
        self.web_bridge = web_bridge
        self.inbox: "queue.Queue[Tuple[str, str]]" = queue.Queue()
        self.approval_queue: "queue.Queue[bool]" = queue.Queue()
        self.waiting_approval = False
        self._stop_event = threading.Event()
        self._offset = 0
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if not self.enabled:
            return
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="TelegramBridge")
        self._thread.start()
        print(f"{C.GREEN}[TELEGRAM] Bridge activo en segundo plano (Chat ID: {self.chat_id}).{C.RESET}")
        if self.chat_id:
            self.send(
                "🤖 *ARYI OMEGA v8.5 (Windows Native · Anti-500 Edition)* conectado.\n"
                "Comandos rápidos:\n"
                "• Escribe cualquier orden para delegarme código, Git, PRs o búsquedas.\n"
                "• `/mission <objetivo>` convoca un equipo multi-modelo con auto-failover.\n"
                "• `/web <mensaje>` responde en vivo al `chat_monolitico.php` como `SS-TFH`.\n"
                "• `/telemetry` ejecuta el benchmark de modelos en el nodo GPU.\n"
                "• `/auto on` | `/auto off` activa/desactiva ejecución 100% autónoma.\n"
                "• `/status` muestra estado del clúster y procesos."
            )

    def stop(self) -> None:
        self._stop_event.set()

    def send(self, text: str) -> None:
        if not self.enabled or not self.chat_id:
            return
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        fragmentos = [text[i : i + 3900] for i in range(0, len(text), 3900)] or [text]
        for frag in fragmentos:
            try:
                HTTP.post(
                    url,
                    json={"chat_id": self.chat_id, "text": frag},
                    timeout=(5, 10),
                )
            except Exception as e:
                auditar("telegram_error", str(e), "send_failed")

    def _poll_loop(self) -> None:
        url = f"https://api.telegram.org/bot{self.token}/getUpdates"
        while not self._stop_event.is_set():
            try:
                r = HTTP.get(url, params={"offset": self._offset, "timeout": 20}, timeout=(5, 25))
                if r.status_code != 200:
                    time.sleep(3)
                    continue
                data = r.json()
                for item in data.get("result", []):
                    self._offset = item["update_id"] + 1
                    msg = item.get("message") or {}
                    chat = str((msg.get("chat") or {}).get("id", ""))
                    texto = (msg.get("text") or "").strip()
                    if not texto:
                        continue
                    if not self.chat_id:
                        self.chat_id = chat
                        print(f"\n{C.CYAN}[TELEGRAM] Vinculado automáticamente al Chat ID: {self.chat_id}{C.RESET}")
                        self.send(f"✅ Chat vinculado (ID: {self.chat_id}).")
                    elif chat != self.chat_id:
                        continue

                    low = texto.lower()
                    if low.startswith("/web ") and self.web_bridge:
                        respuesta_web = texto[5:].strip()
                        if respuesta_web and self.web_bridge.post_message(respuesta_web, sender=ADMIN_WEB_HANDLE):
                            self.send(f"💬 Enviado a `chat_monolitico.php` ({ADMIN_WEB_HANDLE}):\n{respuesta_web}")
                        else:
                            self.send("❌ No se pudo escribir en `chat_db.json`.")
                        continue

                    if self.waiting_approval and low in {"/approve", "si", "sí", "s", "ok", "yes", "y"}:
                        self.approval_queue.put(True)
                    elif self.waiting_approval and low in {"/deny", "no", "n", "cancel"}:
                        self.approval_queue.put(False)
                    else:
                        self.inbox.put(("telegram", texto))
            except Exception:
                time.sleep(3)


SHARED_INBOX: "queue.Queue[Tuple[str, str]]" = queue.Queue()
WEB_CHAT = WebChatDBBridge(CHAT_DB_FILE, SHARED_INBOX)
TELEGRAM = TelegramBridge(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, web_bridge=WEB_CHAT)
TELEGRAM.inbox = SHARED_INBOX


def pedir_confirmacion(pregunta: str) -> bool:
    """Pide confirmación por consola o por Telegram si no está activo AUTO_APPROVE."""
    global AUTO_APPROVE
    if AUTO_APPROVE:
        print(f"{C.GREEN}  [AUTO-APPROVE] Autorizado automáticamente.{C.RESET}")
        return True

    if TELEGRAM.enabled and TELEGRAM.chat_id:
        TELEGRAM.waiting_approval = True
        TELEGRAM.send(f"⚠️ *Autorización requerida:*\n{pregunta}\n\nResponde `si` (`/approve`) o `no` (`/deny`).")

    print(f"{C.YELLOW}{pregunta}{C.RESET}")
    print(f"{C.YELLOW}¿Autorizar acción? [s/N/auto] (también puedes responder por Telegram): {C.RESET}", end="", flush=True)

    resultado: List[Optional[bool]] = [None]

    def _leer_consola() -> None:
        try:
            resp = sys.stdin.readline().strip().lower()
            if resp == "auto":
                resultado[0] = True
                globals()["AUTO_APPROVE"] = True
                print(f"{C.GREEN}[SISTEMA] Modo AUTO-APPROVE activado para el resto de la sesión.{C.RESET}")
            else:
                resultado[0] = resp in {"s", "si", "sí", "y", "yes"}
        except Exception:
            resultado[0] = False

    t_in = threading.Thread(target=_leer_consola, daemon=True)
    t_in.start()

    while resultado[0] is None:
        if TELEGRAM.enabled:
            try:
                tg_resp = TELEGRAM.approval_queue.get_nowait()
                resultado[0] = tg_resp
                print(f"\n{C.CYAN}[TELEGRAM] Respuesta recibida: {'APROBADO' if tg_resp else 'RECHAZADO'}{C.RESET}")
                break
            except queue.Empty:
                pass
        time.sleep(0.15)

    TELEGRAM.waiting_approval = False
    return bool(resultado[0])


# =============================================================================
# 1. MOTOR DE TELEMETRÍA Y CLASIFICACIÓN CORE DE MODELOS
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
    coding_score: float = 0.0       # 0.0 - 100.0
    reasoning_score: float = 0.0    # 0.0 - 100.0
    core_features: List[str] = field(default_factory=list)
    tier: str = "general"           # god_architect | coding_god | fast_git_operator | qa_and_research | vision_specialist
    last_tested: str = ""


def estimar_parametros_b(name: str, param_size_str: str = "") -> float:
    """Extrae el número de billones de parámetros del nombre o metadatos del modelo."""
    combined = f"{name} {param_size_str}"
    m = re.search(r"(\d+(?:\.\d+)?)\s*[bB]\b", combined)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return 7.0


def calcular_contexto_seguro_vram(name: str, size_gb: float, param_b: float) -> int:
    """
    Evita el error HTTP 500 de Ollama por agotamiento de VRAM al reservar el KV-Cache:
    - Modelos >= 25B o >= 14 GB en disco (ej. Ornith-35B, qwen3-coder:30b): máximo 8192 tokens.
    - Modelos medianos (7B - 14B): 16384 tokens.
    - Modelos ligeros (<= 4B): 16384 tokens.
    """
    if param_b >= 25.0 or size_gb >= 14.0 or "gguf" in name.lower():
        return 8192
    if param_b >= 7.0 or size_gb >= 4.5:
        return 16384
    return 16384


class TelemetryEngine:
    """Realiza pruebas telemétricas tras cargar cada modelo y los clasifica en Features Core."""

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
                    # Ajustar techos de contexto excesivos guardados en versiones previas que causaban HTTP 500
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

        # Penalizar modelos ultra-pequeños (<= 1.5B) para que no ganen roles de QA/Researcher frente a modelos de 7B+
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
        """Devuelve la lista ordenada de modelos candidatos para un rol (permite Auto-Failover si el #1 da error 500)."""
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
                    1 if m.size_gb >= 3.0 else 0,
                    m.tokens_per_sec,
                ),
                reverse=True,
            )
        if role == "architect":
            return sorted(
                valid,
                key=lambda m: (
                    1 if "god_level_analysis" in m.core_features else 0,
                    m.reasoning_score,
                    m.coding_score,
                    m.size_gb,
                ),
                reverse=True,
            )
        if role in ("gitops", "fast"):
            return sorted(
                valid,
                key=lambda m: (
                    m.tokens_per_sec,
                    m.coding_score,
                ),
                reverse=True,
            )
        if role == "qa":
            # Preferir modelos con buena capacidad analítica (>2 GB) antes que un 0.5B
            return sorted(
                valid,
                key=lambda m: (
                    1 if m.size_gb >= 2.0 else 0,
                    m.reasoning_score + m.coding_score,
                    m.tokens_per_sec,
                ),
                reverse=True,
            )
        # researcher / general
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
# 2. PERFILES "NIVEL DIOS" (HIPER-ESPECIALIZACIÓN DINÁMICA)
# =============================================================================
GOD_PROFILES: Dict[str, Dict[str, str]] = {
    "systems_architect": {
        "titulo": "Arquitecto Supremo de Sistemas & Cloud-Native (Nivel Dios)",
        "role_type": "architect",
        "directiva": (
            "Actúas con rigor de Principal Systems Architect. Diseñas sistemas desde cero modulares, "
            "tolerantes a fallos, seguros y listos para producción (Zero-Placeholders). Antes de codificar, "
            "defines la estructura de directorios, contratos de datos, manejo de concurrencia y pruebas."
        ),
    },
    "fullstack_framework_master": {
        "titulo": "Ingeniero Principal Polyglot & Creador de Frameworks (Nivel Dios)",
        "role_type": "coder",
        "directiva": (
            "Dominas Python, PHP, TypeScript/Node, Rust, Go, C#, PowerShell y frameworks modernos. "
            "Cuando te piden aprender o usar un framework nuevo, primero consultas la web en tiempo real "
            "con `<learn_framework>` o `<web_search>`, asimilas su sintaxis actual y escribes código limpio, "
            "tipado, completo y sin abreviaciones perezosas (`// ... resto del código`)."
        ),
    },
    "gitops_release_commander": {
        "titulo": "Comandante GitOps, CI/CD & Automatización de Repositorios (Nivel Dios)",
        "role_type": "gitops",
        "directiva": (
            "Gestionas el ciclo de vida completo en Git y GitHub. Verificas siempre `status` y `diff` antes de "
            "hacer commits, redactas mensajes Conventional Commits impecables (`feat:`, `fix:`, `refactor:`), "
            "gestionas ramas limpias, haces `push` y creas Pull Requests bien documentados."
        ),
    },
    "cybersec_qa_auditor": {
        "titulo": "Auditor de Seguridad Ofensiva/Defensiva & QA Estricto (Nivel Dios)",
        "role_type": "qa",
        "directiva": (
            "Analizas cada línea de código buscando vulnerabilidades (inyección, XSS, fugas de credenciales, condiciones de "
            "carrera, rutas inseguras en Windows/Linux) y ejecutas pruebas reales en consola para certificar que "
            "el sistema funciona sin errores antes de dar el visto bueno."
        ),
    },
    "deep_research_strategist": {
        "titulo": "Investigador Científico, Estratégico y Analista en Tiempo Real (Nivel Dios)",
        "role_type": "researcher",
        "directiva": (
            "Investigas cualquier disciplina (IA, finanzas cuantitativas, física, derecho, bioinformática, ingeniería) "
            "con objetividad absoluta, contrastando múltiples fuentes en tiempo real mediante `<web_search>` y `<web_fetch>`."
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


# =============================================================================
# 3. NAVEGACIÓN WEB EN TIEMPO REAL Y APRENDIZAJE DE FRAMEWORKS
# =============================================================================
def limpiar_html_a_texto(raw_html: str, max_chars: int = 12_000) -> str:
    limpio = re.sub(r"<(script|style|noscript|svg|header|footer|nav)\b[^>]*>.*?</\1>", " ", raw_html, flags=re.DOTALL | re.IGNORECASE)
    limpio = re.sub(r"</?(p|div|h[1-6]|li|tr|br|pre|code)\b[^>]*>", "\n", limpio, flags=re.IGNORECASE)
    limpio = re.sub(r"<[^>]+>", " ", limpio)
    limpio = html.unescape(limpio)
    lineas = [re.sub(r"[ \t]+", " ", ln).strip() for ln in limpio.splitlines()]
    lineas = [ln for ln in lineas if len(ln) > 1]
    resultado = "\n".join(lineas)
    return recortar(resultado, max_chars, proporcion_cola=0.3)


def buscar_en_web(query: str, max_results: int = 6) -> str:
    query = query.strip()
    if not query:
        return "Consulta de búsqueda vacía."
    print(f"{C.CYAN}[WEB SEARCH] Consultando en tiempo real: '{query}'...{C.RESET}")
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
    nombres = [f.stem for f in archivos]
    return ", ".join(nombres)


# =============================================================================
# 4. EJECUCIÓN WINDOWS NATIVE (POWERSHELL, CMD, PROCESOS DE FONDO) Y GITOPS
# =============================================================================
def ejecutar_comando_sistema(comando: str, usar_powershell: bool = True, cwd: Optional[Path] = None) -> Tuple[int, str, str]:
    work_dir = cwd or WORKSPACE_ROOT
    if IS_WINDOWS:
        if usar_powershell:
            pwsh = shutil.which("pwsh") or shutil.which("powershell") or "powershell.exe"
            shell_cmd = [pwsh, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", comando]
        else:
            shell_cmd = ["cmd.exe", "/c", comando]
    else:
        shell_cmd = [shutil.which("bash") or "/bin/sh", "-c", comando]

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
    auditar("bg_service", comando, f"PID={proc.pid}")
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
    """Automatiza operaciones Git (status, branch, commit, push, PR) en Windows/Linux."""

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
            cls.run_git(["add", "-A"], cwd=work_dir)
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
# 5. CLIENTE OLLAMA RESILIENTE (ANTI-500, FALLBACK A /generate Y AUTO-FAILOVER)
# =============================================================================
def _mensajes_a_prompt_plano(mensajes: List[Dict[str, str]]) -> str:
    """Convierte una lista de mensajes chat a un prompt plano para `/api/generate` (modelos GGUF sin chat_template)."""
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
    """Ejecuta una petición contra `/api/chat` o `/api/generate` capturando el detalle exacto si Ollama devuelve 500."""
    partes: List[str] = []
    printed_header = False

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
                if not silencioso:
                    if prefijo_stream and not printed_header:
                        print(prefijo_stream, end="", flush=True)
                        printed_header = True
                    print(frag, end="", flush=True)
                partes.append(frag)
            if evento.get("done"):
                break

    if not silencioso and partes:
        print()
    return "".join(partes)


def llamar_ollama_resiliente(
    api_base: str,
    modelos_candidatos: List[str],
    mensajes: List[Dict[str, str]],
    limite_tokens: int = 8192,
    temperatura: float = 0.15,
    silencioso: bool = False,
    prefijo_stream: str = "",
) -> Tuple[str, str]:
    """
    Intenta ejecutar la consulta en el primer modelo de `modelos_candidatos` con un techo seguro de VRAM:
    1. Prueba `/api/chat` con `num_ctx` seguro (ej. 8192 o 4096).
    2. Si devuelve HTTP 500 (común en modelos GGUF de 30B/35B por plantilla o KV-cache en VRAM),
       reintenta inmediatamente con `/api/generate` y `num_ctx=4096`.
    3. Si el modelo sigue fallando, hace Auto-Failover al siguiente modelo disponible en la lista.
    Devuelve `(respuesta_texto, modelo_que_respondio)`.
    """
    errores_acumulados: List[str] = []

    for idx, modelo in enumerate(modelos_candidatos):
        param_b = estimar_parametros_b(modelo)
        ctx_inicial = min(limite_tokens, 4096 if (param_b >= 25.0 or "gguf" in modelo.lower()) else 8192)

        # Usar lock para que dos hilos nunca intenten cargar dos modelos gigantes en VRAM a la vez
        with GPU_INFERENCE_LOCK:
            # Intento 1: /api/chat con ctx_inicial
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
                if not silencioso:
                    print(f"\n{C.YELLOW}  [AVISO OLLAMA] {e1} -> Reintentando '{modelo}' vía /api/generate (num_ctx=4096)...{C.RESET}")

            # Intento 2: /api/generate con num_ctx reducido (4096) — salva modelos GGUF sin chat_template o con poca VRAM libre
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
                if idx + 1 < len(modelos_candidatos):
                    sig_modelo = modelos_candidatos[idx + 1]
                    print(
                        f"{C.YELLOW}  [AUTO-FAILOVER] '{modelo}' devolvió error en el servidor. "
                        f"Conmutando automáticamente a '{sig_modelo}'...{C.RESET}"
                    )

    raise RuntimeError("Todos los modelos candidatos fallaron:\n" + "\n".join(errores_acumulados[-4:]))


@dataclass
class SwarmAgentSpec:
    name: str
    role_type: str
    persona_prompt: str
    task_instruction: str


class SwarmCoordinator:
    """Crea y coordina equipos de agentes especializados a medida para cualquier misión con Auto-Failover."""

    def __init__(self, telemetry: TelemetryEngine):
        self.telemetry = telemetry
        self.api_base = telemetry.api_base

    def _build_self_context_if_needed(self, mission_goal: str) -> str:
        """
        Si el usuario pide un cheat-sheet, auditoría o mejora de 'este programa' / 'aryi' / 'este script',
        inyecta automáticamente un resumen estructurado del propio archivo `aryi_omega.py` para que
        los agentes documenten el sistema real con 100% de exactitud.
        """
        low = mission_goal.lower()
        if any(k in low for k in ("este programa", "este script", "aryi", "cheat-sheet", "cheatsheet", "orquestador", "este bot")):
            try:
                self_path = Path(__file__).resolve()
                raw_code = self_path.read_text(encoding="utf-8", errors="replace")
                # Extraer cabecera docstring + firmas de clases y comandos principales
                docstring_match = re.search(r'"""(.*?)"""', raw_code, flags=re.DOTALL)
                cabecera = docstring_match.group(1).strip() if docstring_match else ""
                clases = re.findall(r"^class\s+(\w+).*?:", raw_code, flags=re.MULTILINE)
                funciones = re.findall(r"^def\s+([a-zA-Z0-9_]+)\(", raw_code, flags=re.MULTILINE)
                return (
                    f"\n--- CONTEXTO REAL DEL PROGRAMA ACTUAL ({self_path.name}) ---\n"
                    f"Descripción General:\n{cabecera}\n\n"
                    f"Clases Principales: {', '.join(clases)}\n"
                    f"Funciones Principales: {', '.join(funciones[:30])}\n"
                    f"Comandos Interactivos: /telemetry, /models, /mission <objetivo>, /learn <framework>, /web <mensaje>, /auto on|off, /ps, /status, salir\n"
                    f"Etiquetas XML soportadas: <file>, <read_file>, <powershell>, <bash>, <bash_bg>, <git>, <web_search>, <web_fetch>, <learn_framework>, <spawn_team>, <web_chat>\n"
                    f"------------------------------------------------------------\n"
                )
            except Exception:
                pass
        return ""

    def design_team_for_mission(self, mission_goal: str) -> List[SwarmAgentSpec]:
        candidatos_arch = [m.name for m in self.telemetry.rank_models_for_role("architect")]
        arch_principal = candidatos_arch[0] if candidatos_arch else "qwen2.5-coder:7b"
        print(f"\n{C.MAGENTA}🧠 [SWARM ARCHITECT · {arch_principal}] Diseñando equipo de especialistas para la misión...{C.RESET}")

        prompt = (
            "Eres el Director Supremo de Operaciones Multi-Agente.\n"
            f"MISIÓN SOLICITADA: {mission_goal}\n\n"
            "Diseña un equipo de entre 3 y 4 agentes hiper-especializados para cumplir esta misión con excelencia.\n"
            "Responde ÚNICAMENTE con un array JSON válido donde cada elemento tenga exactamente estas claves:\n"
            '  "name": Nombre del rol (ej. "Lead Systems Architect", "Core Python/PHP Engineer", "QA & Security Auditor", "GitOps Commander"),\n'
            '  "role_type": Uno de ["architect", "coder", "qa", "gitops", "researcher"],\n'
            '  "persona_prompt": Descripción de su perfil Nivel Dios y estándares técnicos,\n'
            '  "task_instruction": Qué parte concreta de la misión debe resolver y entregar.\n'
        )
        try:
            raw, _ = llamar_ollama_resiliente(
                api_base=self.api_base,
                modelos_candidatos=candidatos_arch,
                mensajes=[{"role": "user", "content": prompt}],
                limite_tokens=4096,
                temperatura=0.1,
                silencioso=True,
            )
            clean_raw = limpiar_bloques_think(raw)
            m = re.search(r"\[.*\]", clean_raw, flags=re.DOTALL)
            if m:
                arr = json.loads(m.group(0))
                specs: List[SwarmAgentSpec] = []
                for item in arr[:4]:
                    specs.append(
                        SwarmAgentSpec(
                            name=str(item.get("name", "Especialista")),
                            role_type=str(item.get("role_type", "coder")),
                            persona_prompt=str(item.get("persona_prompt", "Experto Nivel Dios.")),
                            task_instruction=str(item.get("task_instruction", mission_goal)),
                        )
                    )
                if specs:
                    return specs
        except Exception as e:
            print(f"{C.YELLOW}[SWARM] Usando plantilla de equipo táctico estándar ({e}).{C.RESET}")

        return [
            SwarmAgentSpec(
                name="Principal Systems Architect",
                role_type="architect",
                persona_prompt=GOD_PROFILES["systems_architect"]["directiva"],
                task_instruction=f"Diseña la estructura completa y secciones clave para: {mission_goal}",
            ),
            SwarmAgentSpec(
                name="Lead Full-Stack & Documentation Engineer",
                role_type="coder",
                persona_prompt=GOD_PROFILES["fullstack_framework_master"]["directiva"],
                task_instruction=f"Redacta el archivo completo usando la etiqueta <file path=\"...\"> para: {mission_goal}",
            ),
            SwarmAgentSpec(
                name="CyberSec & QA Auditor",
                role_type="qa",
                persona_prompt=GOD_PROFILES["cybersec_qa_auditor"]["directiva"],
                task_instruction=f"Verifica que la entrega esté completa, precisa y libre de errores para: {mission_goal}",
            ),
        ]

    def execute_mission(self, mission_goal: str, mode: str = "hybrid") -> str:
        specs = self.design_team_for_mission(mission_goal)
        self_ctx = self._build_self_context_if_needed(mission_goal)

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
                f"Trabajas en el directorio Windows Native: {WORKSPACE_ROOT}.\n"
                "Si tu tarea implica crear un archivo o guía, incluye el bloque `<file path=\"nombre_archivo.md\">...</file>`."
            )
            user_msg = (
                f"MISIÓN GLOBAL: {mission_goal}\n"
                f"{self_ctx}\n"
                f"TU TAREA ESPECÍFICA: {spec.task_instruction}\n\n"
                + (f"BLUEPRINT DEL ARQUITECTO:\n{recortar(contexto_previo, 3000)}\n" if contexto_previo else "")
            )
            print(f"\n{C.BLUE}▶ [{spec.name}] ejecutando en '{primario}' (con Auto-Failover activo)...{C.RESET}")
            resp, modelo_usado = llamar_ollama_resiliente(
                api_base=self.api_base,
                modelos_candidatos=candidatos,
                mensajes=[{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}],
                limite_tokens=6144,
                temperatura=0.15,
                silencioso=False,
            )
            return f"{spec.name} ({modelo_usado})", resp

        blueprint = ""
        rest_specs = specs
        if specs and specs[0].role_type == "architect" and mode != "parallel":
            try:
                ag_key, blueprint = _run_agent(specs[0])
                reportes[ag_key] = blueprint
            except Exception as exc:
                print(f"{C.RED}[SWARM AVISO] Arquitecto omitido tras reintentos ({exc}). Continuando con el equipo...{C.RESET}")
            rest_specs = specs[1:]

        # Ejecución controlada por GPU_INFERENCE_LOCK para no saturar VRAM con dos modelos de 30B al mismo tiempo
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futuros = [pool.submit(_run_agent, sp, blueprint) for sp in rest_specs]
            for fut in concurrent.futures.as_completed(futuros):
                try:
                    nombre_ag, salida_ag = fut.result()
                    reportes[nombre_ag] = salida_ag
                except Exception as exc:
                    print(f"{C.RED}[SWARM ERROR] Agente falló: {exc}{C.RESET}")

        ts = time.strftime("%Y%m%d_%H%M%S")
        mission_file = MISSIONS_DIR / f"mission_{ts}.md"
        compilado = [f"# Acta de Misión: {mission_goal}\nFecha: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"]
        for k, v in reportes.items():
            compilado.append(f"## Agente: {k}\n\n{v}\n\n---\n")
        escribir_archivo_atomico(mission_file, "\n".join(compilado))

        return (
            f"MISIÓN EJECUTADA POR EL EQUIPO ({len(reportes)} especialistas). "
            f"Acta completa guardada en: {mission_file}\n\n"
            + "\n\n".join(f"=== REPORTE DE {k} ===\n{recortar(v, 3500)}" for k, v in reportes.items())
        )


# =============================================================================
# 6. SYSTEM PROMPT MAESTRO Y PARSER DE HERRAMIENTAS XML + MARKDOWN
# =============================================================================
SYSTEM_PROMPT_TEMPLATE = """ERES ARYI OMEGA v8.5, AGENTE AUTÓNOMO WINDOWS NATIVE Y ORQUESTADOR MULTI-MODELO DE NIVEL DIOS.

PERFIL ACTIVO PARA ESTA TAREA:
- Rol: {GOD_TITLE}
- Directiva: {GOD_DIRECTIVE}

ENTORNO Y CAPACIDADES NATIVAS:
- Sistema Operativo: {OS_INFO}
- Workspace Raíz Permitido: {WORKSPACE}
- Frameworks en Memoria Persistente: {LEARNED_FRAMEWORKS}

TIENES ACCESO DIRECTO AL SISTEMA OPERATIVO, GIT, WEB EN TIEMPO REAL, CHAT WEB (`chat_db.json`) Y ENJAMBRE DE EQUIPOS MEDIANTE ETIQUETAS XML.
Cada etiqueta debe abrirse y cerrarse limpiamente al inicio de una línea:

1. Crear o sobrescribir un archivo (código o documento completo, sin omitir líneas):
<file path="ruta/relativa/archivo.ext">
contenido íntegro del archivo
</file>

2. Leer un archivo existente del workspace:
<read_file path="ruta/relativa/archivo.py">
</read_file>

3. Ejecutar comandos en PowerShell nativo de Windows (síncrono, recibes la salida):
<powershell>
Get-ChildItem -Force
</powershell>

4. Ejecutar comandos en CMD / Bash estándar (síncrono):
<bash>
pytest -q
</bash>

5. Iniciar un servidor o proceso persistente en segundo plano:
<bash_bg>
python app.py
</bash_bg>

6. Operaciones Git y GitHub (op="init" | "status" | "branch" | "commit" | "push" | "pr"):
<git op="branch" name="feat/nueva-arquitectura">
</git>
<git op="commit" message="feat(core): implementar módulo de telemetría">
</git>
<git op="push" remote="origin" branch="feat/nueva-arquitectura">
</git>
<git op="pr" title="feat: nueva arquitectura" base="main">
Descripción detallada del Pull Request
</git>

7. Consultar la Web (WWW) en tiempo real:
<web_search>
consulta precisa a buscar en tiempo real
</web_search>

8. Leer el contenido completo de una página o documentación web:
<web_fetch url="https://docs.python.org/3/">
</web_fetch>

9. Aprender un framework nuevo en tiempo real y guardarlo en memoria permanente:
<learn_framework name="FastAPI">
</learn_framework>

10. Convocar un Equipo Multi-Agente (Swarm) para misiones complejas:
<spawn_team mode="hybrid">
Descripción detallada de la misión que debe resolver el equipo de especialistas
</spawn_team>

11. Enviar un mensaje en tiempo real al Chat Web (`chat_monolitico.php` / `chat_db.json`):
<web_chat sender="SS-TFH">
Mensaje que verán los visitantes conectados por SSE en tiempo real
</web_chat>

REGLAS DE ORO:
- Nunca inventes que un archivo se creó o que un comando funcionó sin emitir primero la etiqueta correspondiente y verificar el `RESULTADO DE LAS ACCIONES`.
- Cuando crees sistemas o documentos desde cero, construye el archivo con `<file path="...">...</file>`.
"""


def construir_system_prompt(prompt_usuario: str) -> Tuple[str, Dict[str, str]]:
    perfil = detectar_perfil_dios(prompt_usuario)
    os_info = f"{platform.system()} {platform.release()} ({platform.machine()})"
    prompt = (
        SYSTEM_PROMPT_TEMPLATE.replace("{GOD_TITLE}", perfil["titulo"])
        .replace("{GOD_DIRECTIVE}", perfil["directiva"])
        .replace("{OS_INFO}", os_info)
        .replace("{WORKSPACE}", str(WORKSPACE_ROOT))
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
    r"^[ \t]*<(?P<tag>file|read_file|powershell|cmd|bash|bash_bg|git|web_search|web_fetch|learn_framework|spawn_team|web_chat)\b(?P<attrs>[^>\n]*)>(?P<body>.*?)</(?P=tag)\s*>",
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
    acciones: List[AccionAgente] = []
    limpio = limpiar_bloques_think(texto_ia)
    for m in XML_TOOL_RE.finditer(limpio):
        tag = m.group("tag").lower()
        attrs = parsear_atributos(m.group("attrs"))
        body = _normalizar_cuerpo(m.group("body"))
        acciones.append(AccionAgente(tag, attrs, body, m.start(), m.end()))
    return acciones


# =============================================================================
# 7. EJECUTOR DE ACCIONES DEL AGENTE
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
# 8. BUCLE PRINCIPAL DE ORQUESTACIÓN Y COMANDOS INTERACTIVOS
# =============================================================================
def mostrar_ayuda_comandos() -> str:
    return (
        "\nCOMANDOS ESPECIALES DEL ORQUESTADOR:\n"
        "  /telemetry          Ejecuta prueba telemétrica en vivo de todos los modelos y actualiza su clasificación.\n"
        "  /models             Muestra la tabla comparativa de modelos y sus Core Features.\n"
        "  /mission <objetivo> Crea un equipo multi-agente a medida y coordina la misión de principio a fin.\n"
        "  /learn <framework>  Investiga en la web en tiempo real un framework y guarda un Cheat-Sheet en memoria.\n"
        "  /web <mensaje>      Envía un mensaje directo como 'SS-TFH' al chat web (`chat_db.json`).\n"
        "  /auto on | off      Activa o desactiva la ejecución 100% autónoma sin pedir confirmación.\n"
        "  /ps                 Lista los servicios en segundo plano activos.\n"
        "  /status             Resumen del nodo, modo autónomo, Telegram y modelos.\n"
        "  salir | exit        Cierra el orquestador.\n"
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
                return cand
        except Exception:
            continue

    return ENDPOINTS["2"]["url"].rstrip("/")


def obtener_siguiente_entrada() -> Optional[Tuple[str, str]]:
    print(f"\n{C.BOLD}{C.GREEN}Tú (Consola / Telegram / @aryi en WebChat) > {C.RESET}", end="", flush=True)
    resultado: List[Optional[Tuple[str, str]]] = [None]

    def _leer_stdin() -> None:
        try:
            linea = sys.stdin.readline()
            if not linea:
                resultado[0] = ("eof", "")
            else:
                resultado[0] = ("consola", linea.strip())
        except Exception:
            resultado[0] = ("eof", "")

    t = threading.Thread(target=_leer_stdin, daemon=True)
    t.start()

    while resultado[0] is None:
        try:
            origen_ext, msg_ext = SHARED_INBOX.get_nowait()
            print(f"\n{C.CYAN}[{origen_ext.upper()} -> ARYI]: {msg_ext}{C.RESET}")
            return (origen_ext, msg_ext)
        except queue.Empty:
            pass
        time.sleep(0.15)

    return resultado[0]


def main() -> None:
    global AUTO_APPROVE

    print(f"{C.BOLD}{C.CYAN}" + "=" * 78)
    print("  ARYI OMEGA v8.5 · WINDOWS NATIVE AUTONOMOUS AGENT & SWARM ORCHESTRATOR")
    print("=" * 78 + f"{C.RESET}")
    print(f"  • Sistema Operativo : {platform.system()} {platform.release()} ({platform.machine()})")
    print(f"  • Workspace Raíz    : {WORKSPACE_ROOT}")
    print(f"  • Modo Autónomo     : {'ACTIVO (AUTO-APPROVE)' if AUTO_APPROVE else 'SUPERVISADO (usa /auto on para delegar 100%)'}")
    print(f"  • Telegram Bridge   : {'ACTIVO (Chat ID ' + TELEGRAM_CHAT_ID + ')' if TELEGRAM.enabled else 'DESACTIVADO'}")
    print(f"  • WebChat DB Bridge : {CHAT_DB_FILE} (Handle: {ADMIN_WEB_HANDLE})")

    api_base = seleccionar_endpoint()
    telemetry = TelemetryEngine(api_base)
    telemetry.run_full_telemetry(force=False)
    print(telemetry.summary_table())

    swarm = SwarmCoordinator(telemetry)
    WEB_CHAT.start()
    TELEGRAM.start()

    print(mostrar_ayuda_comandos())

    historial: List[Dict[str, str]] = []

    while True:
        try:
            par = obtener_siguiente_entrada()
        except KeyboardInterrupt:
            break

        if not par:
            continue
        origen, texto = par
        if origen == "eof":
            break
        if not texto:
            continue

        low = texto.lower()
        if low in {"salir", "exit", "/exit"}:
            break

        if low in {"/help", "ayuda"}:
            msg = mostrar_ayuda_comandos()
            print(msg)
            if origen == "telegram":
                TELEGRAM.send(msg)
            continue

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
                    TELEGRAM.send(f"💬 Publicado en `chat_db.json` ({ADMIN_WEB_HANDLE}): {msg_web}")
            continue

        if low.startswith("/auto"):
            AUTO_APPROVE = "on" in low or "1" in low or "true" in low
            estado_txt = f"Modo Autónomo (AUTO-APPROVE): {'ACTIVADO' if AUTO_APPROVE else 'DESACTIVADO'}"
            print(f"{C.GREEN}[SISTEMA] {estado_txt}{C.RESET}")
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
            qa_m, _ = telemetry.select_best_model_for_role("qa")
            git_m, _ = telemetry.select_best_model_for_role("gitops")
            st = (
                f"Estado ARYI OMEGA v8.5:\n"
                f"• Workspace: {WORKSPACE_ROOT}\n"
                f"• Auto-Approve: {AUTO_APPROVE}\n"
                f"• Modelo Arquitecto: {arch_m}\n"
                f"• Modelo Coder: {code_m}\n"
                f"• Modelo QA/Researcher: {qa_m}\n"
                f"• Modelo GitOps: {git_m}\n"
                f"• Frameworks Aprendidos: {cargar_frameworks_aprendidos()}\n"
                f"• Servicios de fondo:\n{listar_procesos_fondo()}"
            )
            print(st)
            if origen == "telegram":
                TELEGRAM.send(st)
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
                TELEGRAM.send(f"🚀 Iniciando Misión Multi-Agente para: {objetivo}")
            reporte_mision = swarm.execute_mission(objetivo, mode="hybrid")
            # Si los especialistas ya emitieron etiquetas <file> dentro de la misión, ejecutarlas directamente
            res_directo = ejecutar_acciones_turno(reporte_mision, telemetry, swarm)
            if res_directo.hubo_acciones:
                print(f"\n{C.GREEN}✓ [SWARM] Acciones materializadas directamente desde el equipo ({res_directo.ejecutadas} ejecutadas).{C.RESET}")
                if TELEGRAM.enabled:
                    TELEGRAM.send(f"✅ Misión completada y archivos creados:\n{recortar(res_directo.feedback, 2500)}")
                continue

            texto = (
                f"El equipo multi-agente ha diseñado la siguiente solución para la misión '{objetivo}'.\n"
                f"Materializa inmediatamente en el workspace el archivo final usando `<file path=\"...\">`:\n\n{recortar(reporte_mision, 5000)}"
            )

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
                TELEGRAM.send(f"🤖 *[{modelo_real} · Paso {paso}]*\n{recortar(respuesta_ia, 3500)}")

            if origen == "webchat":
                limpia_web = XML_TOOL_RE.sub("", limpiar_bloques_think(respuesta_ia)).strip()
                if limpia_web:
                    WEB_CHAT.post_message(recortar(limpia_web, 1200), sender="ARYI_OMEGA")

            resumen = ejecutar_acciones_turno(respuesta_ia, telemetry, swarm)
            if not resumen.hubo_acciones:
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
                TELEGRAM.send(f"🛠️ *Resultado de Herramientas (Paso {paso}):*\n{recortar(resumen.feedback, 2500)}")

    TELEGRAM.stop()
    print(f"\n{C.CYAN}[SISTEMA] ARYI OMEGA finalizado limpiamente.{C.RESET}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{C.CYAN}[SISTEMA] Sesión terminada por el operador.{C.RESET}")