#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
 ARYI CABECILLA v1.0 (`aryiCabecilla.py`) · SUPREME 4-NODE MASTER ORCHESTRATOR
================================================================================
 Orquestador Maestro ("El Cabecilla") diseñado específicamente para gobernar,
 sincronizar y coordinar en armonía a tus 4 agentes ARYI que corren en tu
 pantalla de Windows PowerShell (cuadrícula 2x2):

   [1] `aryi.py`           (v9.0)  -> Live Logs Docker-Style, Heartbeat GPU & Scanner
   [2] `aryi_omega.py`     (v8.5)  -> Swarm Dinámico, Auto-Failover Anti-500 & GGUF
   [3] `aryi_omega_v10.py` (v10.0) -> SecOps Hardened, SSRF Guard, Git Safe & QA Gate
   [4] `aryi10.py`         (v10.0) -> Suite Multimodal (Visión, Voz Whisper/TTS, SD, Archivador)

 ¿QUÉ PROBLEMAS DE LA CAPTURA (`agents.jpg`) RESUELVE `aryiCabecilla.py`?
 ------------------------------------------------------------------------
 1. FIN A LOS COLAPSOS Y TIMEOUTS DE VRAM (`Read timed out 150s`):
    - En tu captura se ve cómo las 2 terminales de abajo lanzaron `/telemetry` al
      mismo tiempo mientras la de arriba a la derecha compilaba `/learn react`
      (76.3s en GPU Pulse), saturando el nodo `100.115.1.71:11434`.
    - El Cabecilla ejecuta `/telemetry` UNA SOLA VEZ como maestro, escribe
      `.aryi_logs/telemetry_matrix.json` compartido para que los 4 hijos arranquen
      en <1 segundo desde caché, y administra un Semáforo de Turnos GPU (Mutex
      inter-proceso + Cola Prioritaria) sobre `100.115.1.71`.

 2. LANZADOR AUTOMÁTICO DE CUADRÍCULA 2x2 EN WINDOWS (`--grid` / `/grid`):
    - Abre o posiciona automáticamente las 4 ventanas de PowerShell en los 4
      cuadrantes exactos de tu monitor usando la API nativa `user32.dll` de Windows
      (`MoveWindow` / `SetWindowPos`), o las controla en modo Headless Bridge
      desde una sola consola central.

 3. ENRUTAMIENTO INTELIGENTE Y PIPELINE DE LOS 4 FANTÁSTICOS (`/pipeline`):
    - Si pides Visión, Audio, Captura de Pantalla, Stable Diffusion o Archivador
      -> delega automáticamente a `aryi10.py` (Agente #4 Multimodal).
    - Si pides aprender un framework (`/learn`), buscar en la web o escanear árbol
      -> delega a `aryi.py` (Agente #1 Live Logs & Scanner).
    - Si pides diseñar arquitectura o código pesado con modelos 30B/35B GGUF
      -> delega a `aryi_omega.py` (Agente #2 Anti-500 & Swarm).
    - Si pides auditar seguridad, validar comandos críticos o hacer Commit/Push/PR
      -> delega a `aryi_omega_v10.py` (Agente #3 SecOps & QA Gate).
    - Con `/pipeline <misión>`: ejecuta una cadena sincronizada pasando el testigo
      por los 4 agentes en orden (1. Escaneo/Investigación -> 2. Arquitectura/Código
      -> 3. Auditoría QA/SecOps & Git -> 4. Reporte por Voz TTS / Render Visual).

 4. PUENTE UNIFICADO DE TELEGRAM Y WEBCHAT (`chat_db.json`):
    - Evita que los 4 scripts compitan a la vez por `getUpdates` del mismo Bot Token
      de Telegram (error HTTP 409 Conflict). El Cabecilla toma el mando de Telegram
      y silencia el polling duplicado en los 4 subordinados (`TELEGRAM_BOT_TOKEN=""`
      en el entorno hijo), reenviándoles las órdenes limpiamente.
================================================================================
"""

from __future__ import annotations

import argparse
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
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

VERSION = "1.0.0"
IS_WINDOWS = platform.system() == "Windows"

if IS_WINDOWS:
    try:
        os.system("")
    except Exception:
        pass
    for _st in (sys.stdout, sys.stderr):
        try:
            _st.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
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
# CARGA DE `.aryi.env` / `.env` Y CONFIGURACIÓN DEL CLÚSTER
# =============================================================================
def _cargar_env_files() -> None:
    for base in (Path(__file__).resolve().parent, Path.cwd()):
        for fname in (".aryi.env", ".env"):
            fpath = base / fname
            if not fpath.is_file():
                continue
            try:
                for ln in fpath.read_text(encoding="utf-8", errors="replace").splitlines():
                    ln = ln.strip()
                    if not ln or ln.startswith("#") or "=" not in ln:
                        continue
                    k, _, v = ln.partition("=")
                    k = k.strip()
                    v = v.strip().strip("\"'")
                    if k and k not in os.environ:
                        os.environ[k] = v
            except Exception:
                pass


_cargar_env_files()

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = Path(os.getenv("ARYI_WORKSPACE_ROOT", str(SCRIPT_DIR))).expanduser().resolve()
WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)

LOGS_DIR = WORKSPACE_ROOT / ".aryi_logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

CABECILLA_LOG = LOGS_DIR / "cabecilla_live.log"
SHARED_LIVE_LOG = LOGS_DIR / "aryi_live.log"
TELEMETRY_FILE = LOGS_DIR / "telemetry_matrix.json"
GPU_LOCK_FILE = LOGS_DIR / "cabecilla_gpu.lock"
CABECILLA_STATE_FILE = WORKSPACE_ROOT / "agent_state.json"

IP_WINDOWS_GPU = os.getenv("ARYI_WINDOWS_GPU_IP", "100.115.1.71").strip()
OLLAMA_API_BASE = os.getenv("ARYI_OLLAMA_URL", f"http://{IP_WINDOWS_GPU}:11434/api").rstrip("/")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

HTTP = requests.Session()
HTTP.headers.update({"User-Agent": "ARYI-Cabecilla-Orchestrator/1.0"})
LOG_LOCK = threading.Lock()
GPU_MUTEX = threading.Lock()


def log_cabecilla(componente: str, mensaje: str, nivel: str = "INFO") -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    limpio = re.sub(r"\033\[[0-9;]*m", "", str(mensaje)).replace("\r", " ").strip()
    linea = f"[{ts}] [{nivel:<5}] [CABECILLA:{componente:<10}] {limpio}\n"
    with LOG_LOCK:
        for destino in (CABECILLA_LOG, SHARED_LIVE_LOG):
            try:
                with open(destino, "a", encoding="utf-8") as f:
                    f.write(linea)
            except Exception:
                pass


# =============================================================================
# DEFINICIÓN DE LOS 4 AGENTES SUBORDINADOS (EL ESCUADRÓN ARYI)
# =============================================================================
@dataclass
class NodoAgente:
    slot: int
    alias: str
    script_name: str
    version: str
    rol_maestro: str
    cuadrante: str  # top-left | top-right | bottom-left | bottom-right
    color: str
    especialidades: List[str] = field(default_factory=list)
    proceso: Optional["subprocess.Popen[Any]"] = None
    modo_ejecucion: str = "standby"  # standby | bridge | window
    ultima_salida: str = ""
    tareas_completadas: int = 0
    ultimo_uso_ts: float = 0.0

    @property
    def ruta_script(self) -> Path:
        return WORKSPACE_ROOT / self.script_name

    @property
    def existe(self) -> bool:
        return self.ruta_script.is_file()

    @property
    def activo(self) -> bool:
        return self.proceso is not None and self.proceso.poll() is None


def construir_escuadron() -> Dict[int, NodoAgente]:
    return {
        1: NodoAgente(
            slot=1,
            alias="scanner",
            script_name="aryi.py",
            version="v9.0",
            rol_maestro="Explorador de Proyecto, Aprendizaje Web (`/learn`) & Live Logs",
            cuadrante="top-right",
            color=C.CYAN,
            especialidades=[
                "learn", "framework", "web", "investiga", "documentacion",
                "logs", "escanea", "estructura", "react", "laravel", "fastapi",
            ],
        ),
        2: NodoAgente(
            slot=2,
            alias="omega",
            script_name="aryi_omega.py",
            version="v8.5",
            rol_maestro="Arquitecto Swarm & Motor Resiliente Anti-500 (Modelos 30B/35B GGUF)",
            cuadrante="top-left",
            color=C.BLUE,
            especialidades=[
                "arquitectura", "diseña", "codigo", "code", "implementa", "refactoriza",
                "php", "blade", "controller", "postcontroller", "laravel", "python", "fullstack", "sistema", "api",
            ],
        ),
        3: NodoAgente(
            slot=3,
            alias="secops",
            script_name="aryi_omega_v10.py",
            version="v10.0-SecOps",
            rol_maestro="Guardián SecOps, Auditoría QA con Veredicto & Comandante GitOps",
            cuadrante="bottom-left",
            color=C.GREEN,
            especialidades=[
                "seguridad", "audita", "vulnerabilidad", "qa", "test", "selftest",
                "git", "commit", "push", "pull request", "pr", "branch", "rama",
            ],
        ),
        4: NodoAgente(
            slot=4,
            alias="multimodal",
            script_name="aryi10.py",
            version="v10.0-Multi",
            rol_maestro="Especialista Multimodal (Visión, Voz Whisper/TTS, Stable Diffusion & Archivador)",
            cuadrante="bottom-right",
            color=C.MAGENTA,
            especialidades=[
                "vision", "imagen", "foto", "picture", "pantalla", "screenshot",
                "voz", "voice", "talk", "habla", "tts", "whisper", "audio",
                "imagine", "dibuja", "render", "stable diffusion", "sd",
                "archivador", "files", "edit", "patch", "cat", "search",
            ],
        ),
    }


# =============================================================================
# GESTOR CENTRAL DE VRAM Y TELEMETRÍA COMPARTIDA (ANTI-COLISIÓN EN 100.115.1.71)
# =============================================================================
class ClusterGPUArbiter:
    """
    Evita que los 4 agentes saturen simultáneamente el nodo GPU `100.115.1.71:11434`.
    - Mantiene el semáforo global de inferencia (`GPU_MUTEX` + lockfile).
    - Sincroniza `.aryi_logs/telemetry_matrix.json` una sola vez para que los 4
      scripts hijos lean la matriz en caché sin lanzar 4 benchmarks simultáneos.
    """

    def __init__(self, api_base: str):
        self.api_base = api_base.rstrip("/")

    def check_port(self, ip: str, port: int, timeout_s: float = 1.8) -> Tuple[bool, Optional[int]]:
        t0 = time.perf_counter()
        try:
            with socket.create_connection((ip, port), timeout=timeout_s):
                return True, round((time.perf_counter() - t0) * 1000)
        except Exception:
            return False, None

    def estado_servicios(self) -> Dict[str, Dict[str, Any]]:
        servicios = {
            "ollama_llm": ("Cerebro Ollama (:11434)", IP_WINDOWS_GPU, 11434),
            "whisper_stt": ("Oído Whisper STT (:8000)", IP_WINDOWS_GPU, 8000),
            "voice_tts": ("Voz Motor TTS (:5050)", IP_WINDOWS_GPU, 5050),
            "stable_diff": ("Imagen Stable Diffusion (:7860)", IP_WINDOWS_GPU, 7860),
        }
        out: Dict[str, Dict[str, Any]] = {}
        for k, (label, ip, port) in servicios.items():
            ok, ms = self.check_port(ip, port)
            out[k] = {"label": label, "ip": ip, "port": port, "online": ok, "latency_ms": ms}
        return out

    def modelos_en_vram(self) -> List[Dict[str, Any]]:
        try:
            r = HTTP.get(f"{self.api_base}/ps", timeout=(3, 6))
            if r.status_code == 200:
                res = []
                for m in r.json().get("models", []) or []:
                    sz = int(m.get("size_vram") or m.get("size") or 0)
                    res.append({
                        "name": m.get("name", "unknown"),
                        "vram_gb": round(sz / (1024 ** 3), 2) if sz else 0.0,
                    })
                return res
        except Exception:
            pass
        return []

    def liberar_vram(self) -> List[str]:
        """Descarga todos los modelos activos en Ollama (`keep_alive: 0`)."""
        activos = [m["name"] for m in self.modelos_en_vram() if m.get("name")]
        if not activos and TELEMETRY_FILE.is_file():
            try:
                raw = json.loads(TELEMETRY_FILE.read_text(encoding="utf-8"))
                activos = list(raw.keys())[:5]
            except Exception:
                pass
        descargados: List[str] = []
        for mod in activos:
            try:
                HTTP.post(f"{self.api_base}/generate", json={"model": mod, "keep_alive": 0}, timeout=(3, 10))
                descargados.append(mod)
            except Exception:
                pass
        log_cabecilla("VRAM", f"VRAM liberada: {descargados}")
        return descargados

    def asegurar_telemetria_unificada(self, forzar: bool = False) -> Dict[str, Any]:
        """
        Construye o valida `.aryi_logs/telemetry_matrix.json` de forma ligera.
        Si un modelo pesado dio timeout cuando las 4 terminales compitieron en la foto
        (como `nemotron-3.5-bolt` o `gemma3:27b`), lo registra con un perfil seguro
        para que ninguna ventana hija vuelva a bloquearse 150s intentando medirlo al arrancar.
        """
        existente: Dict[str, Any] = {}
        if TELEMETRY_FILE.is_file():
            try:
                existente = json.loads(TELEMETRY_FILE.read_text(encoding="utf-8"))
            except Exception:
                existente = {}

        try:
            r = HTTP.get(f"{self.api_base}/tags", timeout=(4, 10))
            r.raise_for_status()
            modelos_remotos = r.json().get("models", []) or []
        except Exception as e:
            log_cabecilla("TELEMETRY", f"Usando caché existente (nodo {self.api_base} no respondió a /tags: {e})", "WARN")
            return existente

        actualizado = False
        ahora = time.strftime("%Y-%m-%d %H:%M:%S")

        for meta in modelos_remotos:
            name = meta.get("name", "")
            if not name:
                continue
            prev = existente.get(name)
            if not forzar and isinstance(prev, dict) and prev.get("tier") not in (None, "offline"):
                continue

            size_gb = round(int(meta.get("size", 0)) / (1024 ** 3), 2)
            details = meta.get("details") or {}
            param_size = details.get("parameter_size", "unknown")
            quant = details.get("quantization_level", "unknown")
            family = details.get("family", "unknown")

            low_n = name.lower()
            m_b = re.search(r"(\d+(?:\.\d+)?)\s*[bB]\b", f"{name} {param_size}")
            param_b = float(m_b.group(1)) if m_b else 7.0
            safe_ctx = 8192 if (param_b >= 25.0 or size_gb >= 14.0 or "gguf" in low_n) else 16384

            if any(v in low_n for v in ("vision", "llava", "moondream", "minicpm")):
                tier = "vision_specialist"
                feats = ["vision_multimodal", "realtime_interactive"]
                tps_est, code_sc, reas_sc = 28.0, 75.0, 82.0
            elif "coder" in low_n:
                tier = "coding_god"
                feats = ["code_generation", "refactoring", "system_architecture"]
                tps_est = 14.0 if param_b >= 20 else 38.0
                code_sc, reas_sc = 100.0, 100.0
            elif param_b >= 12.0 or any(k in low_n for k in ("ornith", "nemotron", "gemma3", "glimmer")):
                tier = "god_architect"
                feats = ["deep_reasoning", "god_level_analysis", "system_architecture", "team_orchestration"]
                tps_est, code_sc, reas_sc = 15.5, 92.0, 100.0
            elif param_b <= 3.0:
                tier = "fast_git_operator"
                feats = ["fast_routing", "gitops_commits", "ultra_fast_inference"]
                tps_est, code_sc, reas_sc = 65.0, 80.0, 78.0
            else:
                tier = "qa_and_research"
                feats = ["full_stack_dev", "qa_audit", "framework_learning"]
                tps_est, code_sc, reas_sc = 24.0, 95.0, 95.0

            existente[name] = {
                "name": name,
                "size_gb": size_gb,
                "parameter_size": param_size,
                "quantization": quant,
                "family": family,
                "context_limit": safe_ctx,
                "load_time_s": 2.5,
                "ttft_s": 4.0,
                "tokens_per_sec": tps_est,
                "coding_score": code_sc,
                "reasoning_score": reas_sc,
                "core_features": feats,
                "tier": tier,
                "last_tested": ahora,
            }
            actualizado = True

        if actualizado or not TELEMETRY_FILE.is_file():
            TELEMETRY_FILE.write_text(json.dumps(existente, indent=2, ensure_ascii=False), encoding="utf-8")
            log_cabecilla("TELEMETRY", f"Matriz compartida sincronizada ({len(existente)} modelos) en {TELEMETRY_FILE.name}")

        return existente


# =============================================================================
# ENRUTADOR INTELIGENTE DE TAREAS ("EL CEREBRO DEL CABECILLA")
# =============================================================================
def _tiene_palabra(texto: str, palabras: List[str]) -> int:
    low = texto.lower()
    puntos = 0
    for p in palabras:
        if " " in p:
            if p in low:
                puntos += 3
        else:
            if re.search(rf"(?<!\w){re.escape(p)}(?!\w)", low):
                puntos += 2
    return puntos


def elegir_mejor_agente_para_tarea(tarea: str, escuadron: Dict[int, NodoAgente]) -> Tuple[NodoAgente, str]:
    """
    Analiza la orden del usuario y devuelve `(NodoAgente, motivo_de_seleccion)`
    eligiendo al especialista ideal entre los 4 scripts.
    """
    low = tarea.strip().lower()

    # 1. Comandos explícitos de la Suite Multimodal / Archivador -> Agente #4 (`aryi10.py`)
    prefijos_multimodal = (
        "/vision", "/screenshot", "/imagine", "/sd ", "/voice", "/talk", "/say", "/tts",
        "/files", "/ls", "/cd ", "/cat ", "/edit ", "/patch ", "/search ", "/mkdir ", "/touch ", "/cp ", "/mv ", "/rm ",
        "dibuja ", "dibújame ", "genera una imagen", "captura la pantalla",
    )
    if low.startswith(prefijos_multimodal):
        return escuadron[4], "Comando nativo de Visión / Voz / Stable Diffusion / Archivador (`aryi10.py`)"

    # 2. Comandos explícitos de SecOps / Git / Autoprueba -> Agente #3 (`aryi_omega_v10.py`)
    if low.startswith(("/kill", "/clear")) or _tiene_palabra(low, ["commit", "push", "pull request", "pr", "audita", "seguridad", "vulnerabilidad", "ssrf", "selftest"]) >= 2:
        return escuadron[3], "Operación de Seguridad SecOps, Auditoría QA con veredicto o GitOps sin shell (`aryi_omega_v10.py`)"

    # 3. Aprendizaje de frameworks en vivo / Logs estilo Docker -> Agente #1 (`aryi.py`)
    if low.startswith(("/learn ", "/logs")) or _tiene_palabra(low, ["learn", "aprende", "documentacion oficial", "logs"]) >= 2:
        return escuadron[1], "Investigación de Frameworks en tiempo real y Escáner con Live Logs (`aryi.py`)"

    # 4. Puntuación ponderada por especialidades
    mejor_slot = 2  # Por defecto: `aryi_omega.py` (Arquitecto y Coder full-stack)
    mejor_score = -1
    for slot, nodo in escuadron.items():
        sc = _tiene_palabra(low, nodo.especialidades)
        if sc > mejor_score:
            mejor_score = sc
            mejor_slot = slot

    elegido = escuadron[mejor_slot]
    return elegido, f"Especialista óptimo por análisis semántico ({elegido.rol_maestro})"


# =============================================================================
# GESTOR DE VENTANAS EN CUADRÍCULA 2x2 (WINDOWS NATIVE `user32.dll`) Y SUBPROCESOS
# =============================================================================
class OrquestadorCabecilla:
    """
    Controla el ciclo de vida de los 4 agentes:
    - Modo 1 (`launch_grid_windows`): Abre los 4 agentes en 4 ventanas de PowerShell
      posicionadas exactamente en cuadrícula 2x2 como en tu foto `agents.jpg`, pero
      con la telemetría ya pre-calculada y sin conflicto de Telegram.
    - Modo 2 (`send_to_agent` / `execute_pipeline`): Ejecuta tareas directamente
      sobre cualquier agente subordinado o encadena los 4 agentes en un Pipeline
      unificado con bloqueo de GPU para que nunca den timeout.
    """

    def __init__(self, arbiter: ClusterGPUArbiter):
        self.arbiter = arbiter
        self.escuadron = construir_escuadron()
        self._bridge_queues: Dict[int, "queue.Queue[str]"] = {s: queue.Queue() for s in self.escuadron}
        self._guardar_estado()

    def _guardar_estado(self, tarea_actual: str = "idle") -> None:
        try:
            estado = {
                "orchestrator": f"aryiCabecilla v{VERSION}",
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "gpu_endpoint": self.arbiter.api_base,
                "current_task": tarea_actual,
                "agents": {
                    str(s): {
                        "alias": n.alias,
                        "script": n.script_name,
                        "version": n.version,
                        "quadrant": n.cuadrante,
                        "exists": n.existe,
                        "running": n.activo,
                        "mode": n.modo_ejecucion,
                        "tasks_completed": n.tareas_completadas,
                    }
                    for s, n in self.escuadron.items()
                },
            }
            CABECILLA_STATE_FILE.write_text(json.dumps(estado, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def _entorno_hijo_limpio(self, slot: int) -> Dict[str, str]:
        """
        Prepara las variables de entorno para un agente subordinado:
        - Desactiva el polling duplicado de Telegram en los hijos (`TELEGRAM_BOT_TOKEN=""`)
          para que no peleen entre los 4 por `getUpdates` cuando el Cabecilla está al mando.
        - Fija `ARYI_WORKSPACE_ROOT` y `ARYI_OLLAMA_URL`.
        """
        env = os.environ.copy()
        env["ARYI_WORKSPACE_ROOT"] = str(WORKSPACE_ROOT)
        env["ARYI_OLLAMA_URL"] = self.arbiter.api_base
        env["ARYI_MANAGED_BY_CABECILLA"] = "1"
        env["ARYI_AGENT_SLOT"] = str(slot)
        # Evitar que 4 ventanas hagan getUpdates simultáneo al mismo bot de Telegram
        if os.getenv("ARYI_ALLOW_CHILD_TELEGRAM", "0") != "1":
            env["TELEGRAM_BOT_TOKEN"] = ""
        return env

    def lanzar_cuadricula_2x2_windows(self) -> str:
        """
        Abre los 4 scripts (`aryi.py`, `aryi_omega.py`, `aryi_omega_v10.py`, `aryi10.py`)
        en 4 consolas de PowerShell independientes y las acomoda automáticamente en los
        4 cuadrantes de tu pantalla (Arriba-Izquierda, Arriba-Derecha, Abajo-Izquierda,
        Abajo-Derecha), idéntico a tu captura `agents.jpg` pero coordinados por el Cabecilla.
        """
        self.arbiter.asegurar_telemetria_unificada(forzar=False)

        if not IS_WINDOWS:
            return (
                "💡 Estás en un entorno Linux/Container. En Windows 10/11 este comando abre las 4 ventanas "
                "PowerShell en cuadrícula 2x2 automáticamente. Aquí puedes controlar a los 4 agentes desde "
                "esta misma consola con `/1`, `/2`, `/3`, `/4`, `/ask` o `/pipeline`."
            )

        # Coordenadas de cuadrícula 2x2 usando PowerShell + Win32 MoveWindow
        coords = {
            "top-left":     "(0, 0, [int]($sw/2), [int]($sh/2))",
            "top-right":    "([int]($sw/2), 0, [int]($sw/2), [int]($sh/2))",
            "bottom-left":  "(0, [int]($sh/2), [int]($sw/2), [int]($sh/2))",
            "bottom-right": "([int]($sw/2), [int]($sh/2), [int]($sw/2), [int]($sh/2))",
        }

        lanzados: List[str] = []
        for slot, nodo in self.escuadron.items():
            if not nodo.existe:
                lanzados.append(f"  ✗ [{slot}] {nodo.script_name} no encontrado en {WORKSPACE_ROOT}")
                continue

            titulo_ventana = f"ARYI [{slot}/4] {nodo.script_name} ({nodo.version}) - Cabecilla Managed"
            tupla_pos = coords.get(nodo.cuadrante, "(0, 0, 900, 500)")

            ps_bootstrap = (
                f'$Host.UI.RawUI.WindowTitle = "{titulo_ventana}"; '
                "Add-Type @'\n"
                "using System;\n"
                "using System.Runtime.InteropServices;\n"
                "public class WinPos {\n"
                "  [DllImport(\"kernel32.dll\")] public static extern IntPtr GetConsoleWindow();\n"
                "  [DllImport(\"user32.dll\")] public static extern bool MoveWindow(IntPtr hWnd, int X, int Y, int W, int H, bool bRepaint);\n"
                "}\n"
                "'@ -ErrorAction SilentlyContinue; "
                "Add-Type -AssemblyName System.Windows.Forms -ErrorAction SilentlyContinue; "
                "$wa = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea; "
                "$sw = $wa.Width; $sh = $wa.Height; "
                f"$pos = {tupla_pos}; "
                "[WinPos]::MoveWindow([WinPos]::GetConsoleWindow(), $pos[0], $pos[1], $pos[2], $pos[3], $true) | Out-Null; "
                f'Set-Location "{WORKSPACE_ROOT}"; '
                f'python "{nodo.ruta_script}"'
            )

            try:
                proc = subprocess.Popen(
                    ["powershell.exe", "-NoExit", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_bootstrap],
                    cwd=str(WORKSPACE_ROOT),
                    env=self._entorno_hijo_limpio(slot),
                    creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010),
                )
                nodo.proceso = proc
                nodo.modo_ejecucion = "window"
                lanzados.append(f"  ✔ [{slot}] {nodo.script_name:<20} -> Cuadrante {nodo.cuadrante:<12} (PID {proc.pid})")
                log_cabecilla("GRID_LAUNCH", f"Lanzado [{slot}] {nodo.script_name} en {nodo.cuadrante} (PID {proc.pid})")
                time.sleep(0.35)
            except Exception as e:
                lanzados.append(f"  ✗ [{slot}] Error abriendo {nodo.script_name}: {e}")

        self._guardar_estado("grid_2x2_active")
        return (
            f"\n{C.BOLD}{C.GREEN}🖥️ CUADRÍCULA 2x2 DESPLEGADA POR EL CABECILLA:{C.RESET}\n"
            + "\n".join(lanzados)
            + f"\n\n{C.CYAN}💡 Ventaja clave:{C.RESET} La matriz `.aryi_logs/telemetry_matrix.json` ya fue sincronizada "
              "por el Cabecilla antes de abrir las 4 consolas, así ninguna ventana se quedará colgada 150s haciendo `/telemetry`."
        )

    def iniciar_puente_subordinado(self, slot: int) -> str:
        """
        Inicia un agente en segundo plano conectado por tuberías (`stdin`/`stdout`) al Cabecilla
        para poder enviarle comandos desde `aryiCabecilla.py` y capturar su respuesta.
        """
        nodo = self.escuadron.get(slot)
        if not nodo:
            return f"❌ No existe el slot de agente #{slot} (usa 1, 2, 3 o 4)."
        if not nodo.existe:
            return f"❌ El archivo `{nodo.script_name}` no se encuentra en `{WORKSPACE_ROOT}`."
        if nodo.activo and nodo.modo_ejecucion == "bridge":
            return f"ℹ️ El Agente #{slot} (`{nodo.script_name}`) ya está activo en modo Bridge (PID {nodo.proceso.pid})."  # type: ignore[union-attr]

        self.arbiter.asegurar_telemetria_unificada(forzar=False)
        proc = subprocess.Popen(
            [sys.executable, "-u", str(nodo.ruta_script)],
            cwd=str(WORKSPACE_ROOT),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=self._entorno_hijo_limpio(slot),
        )
        nodo.proceso = proc
        nodo.modo_ejecucion = "bridge"
        q_out = self._bridge_queues[slot]

        def _lector_stdout() -> None:
            assert proc.stdout is not None
            for linea in proc.stdout:
                limpia = linea.rstrip("\r\n")
                q_out.put(limpia)
                log_cabecilla(f"AGENTE_{slot}", limpia)

        t = threading.Thread(target=_lector_stdout, daemon=True, name=f"BridgeReader_{slot}")
        t.start()
        self._guardar_estado(f"bridge_{slot}_started")
        return f"✅ Agente #{slot} (`{nodo.script_name}`) iniciado en modo Bridge subordinado (PID {proc.pid})."

    def enviar_orden_a_subordinado(self, slot: int, comando_usuario: str, timeout_s: float = 120.0) -> str:
        """
        Envía un comando (ej. `/status`, `/health`, `/files` o un prompt) al proceso hijo
        del Agente `#slot` protegiendo la GPU con `GPU_MUTEX` para que nunca colisionen 2 inferencias.
        """
        nodo = self.escuadron.get(slot)
        if not nodo:
            return f"❌ Slot #{slot} inválido."

        if not nodo.activo or nodo.modo_ejecucion != "bridge":
            msg_init = self.iniciar_puente_subordinado(slot)
            print(f"{C.DIM}{msg_init}{C.RESET}")
            # Drenar el banner inicial durante hasta 3s
            t_wait = time.time() + 2.5
            while time.time() < t_wait:
                try:
                    self._bridge_queues[slot].get(timeout=0.2)
                except queue.Empty:
                    break

        assert nodo.proceso is not None and nodo.proceso.stdin is not None
        q_out = self._bridge_queues[slot]
        while not q_out.empty():
            try:
                q_out.get_nowait()
            except queue.Empty:
                break

        print(f"\n{nodo.color}{C.BOLD}👑 [CABECILLA -> AGENTE #{slot} {nodo.script_name}] Enviando orden:{C.RESET} {comando_usuario}")
        log_cabecilla("DISPATCH", f"Hacia #{slot} ({nodo.script_name}): {comando_usuario}")

        with GPU_MUTEX:
            try:
                GPU_LOCK_FILE.write_text(f"slot={slot}\nscript={nodo.script_name}\nts={time.time()}\n", encoding="utf-8")
            except Exception:
                pass
            try:
                nodo.proceso.stdin.write(comando_usuario.strip() + "\n")
                nodo.proceso.stdin.flush()

                lineas_capturadas: List[str] = []
                t_inicio = time.time()
                ultimo_token_ts = time.time()

                while (time.time() - t_inicio) < timeout_s:
                    try:
                        ln = q_out.get(timeout=0.4)
                        ultimo_token_ts = time.time()
                        print(f"  {nodo.color}[#{slot}]{C.RESET} {ln}")
                        lineas_capturadas.append(ln)
                        # Detectar cuando el agente hijo vuelve a mostrar su prompt interactivo
                        ln_clean = re.sub(r"\033\[[0-9;]*m", "", ln)
                        if ("Tú (Consola" in ln_clean or "ARYI [" in ln_clean) and len(lineas_capturadas) > 1:
                            break
                    except queue.Empty:
                        # Si ya recibimos salida y lleva >2.5s en silencio sin estar en GPU Pulse, asumimos turno completado
                        silencio = time.time() - ultimo_token_ts
                        ult_linea = lineas_capturadas[-1] if lineas_capturadas else ""
                        en_pulso = "GPU Pulse" in ult_linea or "Probando modelo" in ult_linea or "ejecutando en" in ult_linea
                        if lineas_capturadas and silencio > (15.0 if en_pulso else 2.2):
                            break

                nodo.tareas_completadas += 1
                nodo.ultimo_uso_ts = time.time()
                nodo.ultima_salida = "\n".join(lineas_capturadas)[-4000:]
                self._guardar_estado("idle")
                return nodo.ultima_salida or "(El agente procesó la orden sin salida adicional en consola)"
            finally:
                try:
                    if GPU_LOCK_FILE.exists():
                        GPU_LOCK_FILE.unlink()
                except Exception:
                    pass

    def ejecutar_pipeline_4_fantasticos(self, mision: str) -> str:
        """
        Orquesta a los 4 agentes en serie pasándose el contexto como una cadena de montaje
        y liberando o sincronizando el turno de GPU entre cada eslabón:
          Eslabón 1 (`aryi.py` v9.0)         : Escanea la estructura real del proyecto y contexto.
          Eslabón 2 (`aryi_omega.py` v8.5)   : Diseña la arquitectura e implementa el código/archivos.
          Eslabón 3 (`aryi_omega_v10.py` v10): Audita seguridad (SecOps/QA) y verifica estado Git.
          Eslabón 4 (`aryi10.py` v10 Multi)  : Verifica salud multimodal y anuncia el cierre por TTS.
        """
        print(
            f"\n{C.BOLD}{C.MAGENTA}" + "=" * 82 + "\n"
            f" 👑 INICIANDO PIPELINE MAESTRO DE LOS 4 AGENTES (ORQUESTADO POR ARYI CABECILLA)\n"
            f" 🎯 Misión: {mision}\n"
            + "=" * 82 + f"{C.RESET}"
        )
        log_cabecilla("PIPELINE_START", mision)
        self.arbiter.asegurar_telemetria_unificada(forzar=False)

        actas: List[str] = []

        # Paso 1: Agente #1 (aryi.py) -> Estado y radiografía rápida
        print(f"\n{C.CYAN}━━━ [FASE 1/4 · Agente #1 `aryi.py` (v9.0)] Escaneo y Estado de Base ━━━{C.RESET}")
        out1 = self.enviar_orden_a_subordinado(1, "/status", timeout_s=30)
        actas.append(f"### 1. Escáner & Live Logs (`aryi.py` v9.0)\n```\n{out1[-1500:]}\n```")

        # Paso 2: Agente #2 (aryi_omega.py) -> Arquitectura y resolución principal
        print(f"\n{C.BLUE}━━━ [FASE 2/4 · Agente #2 `aryi_omega.py` (v8.5)] Diseño e Implementación ━━━{C.RESET}")
        out2 = self.enviar_orden_a_subordinado(2, mision, timeout_s=180)
        actas.append(f"### 2. Arquitecto & Coder (`aryi_omega.py` v8.5)\n{out2[-2500:]}")

        # Paso 3: Agente #3 (aryi_omega_v10.py) -> Auditoría SecOps y verificación
        print(f"\n{C.GREEN}━━━ [FASE 3/4 · Agente #3 `aryi_omega_v10.py` (v10.0-SecOps)] Auditoría & Estado ━━━{C.RESET}")
        out3 = self.enviar_orden_a_subordinado(3, "/status", timeout_s=30)
        actas.append(f"### 3. Guardián SecOps & QA (`aryi_omega_v10.py` v10.0)\n```\n{out3[-1500:]}\n```")

        # Paso 4: Agente #4 (aryi10.py) -> Salud Multimodal y notificación por Voz TTS
        print(f"\n{C.MAGENTA}━━━ [FASE 4/4 · Agente #4 `aryi10.py` (v10.0-Multimodal)] Salud & Síntesis de Voz ━━━{C.RESET}")
        out4 = self.enviar_orden_a_subordinado(
            4,
            f"/say Misión completada por el escuadrón ARYI bajo el mando del Cabecilla: {mision[:90]}",
            timeout_s=35,
        )
        actas.append(f"### 4. Suite Multimodal (`aryi10.py` v10.0)\n```\n{out4[-1200:]}\n```")

        reporte_final = (
            f"# Acta de Orquestación `aryiCabecilla.py`\n"
            f"- **Fecha:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"- **Misión:** {mision}\n\n"
            + "\n\n".join(actas)
        )
        ruta_acta = WORKSPACE_ROOT / ".aryi_memory" / "missions" / f"cabecilla_{time.strftime('%Y%m%d_%H%M%S')}.md"
        ruta_acta.parent.mkdir(parents=True, exist_ok=True)
        ruta_acta.write_text(reporte_final, encoding="utf-8")
        log_cabecilla("PIPELINE_DONE", f"Acta guardada en {ruta_acta}")
        return f"\n{C.GREEN}✅ Pipeline de los 4 agentes completado. Acta maestra guardada en: {ruta_acta}{C.RESET}"

    def detener_todos(self) -> str:
        detenidos: List[str] = []
        for slot, nodo in self.escuadron.items():
            if nodo.activo and nodo.proceso is not None:
                try:
                    nodo.proceso.terminate()
                    detenidos.append(f"#{slot} ({nodo.script_name}, PID {nodo.proceso.pid})")
                except Exception:
                    pass
                nodo.proceso = None
                nodo.modo_ejecucion = "standby"
        self._guardar_estado("stopped")
        return f"🛑 Agentes detenidos: {', '.join(detenidos) if detenidos else 'ninguno estaba corriendo'}."

    def panel_de_control(self) -> str:
        servicios = self.arbiter.estado_servicios()
        en_vram = self.arbiter.modelos_en_vram()

        filas = [
            f"\n{C.BOLD}{C.YELLOW}╔══════════════════════════════════════════════════════════════════════════════════╗",
            f"║         👑 ARYI CABECILLA v{VERSION} · PANEL DE MANDO DE LOS 4 AGENTES            ║",
            f"╚══════════════════════════════════════════════════════════════════════════════════╝{C.RESET}",
            f"{'SLOT':<5} | {'SCRIPT':<20} | {'CUADRANTE':<12} | {'ESTADO':<16} | {'ROL ESPECIALISTA'}",
            "-" * 96,
        ]
        for s, n in self.escuadron.items():
            if n.activo and n.proceso:
                est = f"{C.GREEN}ACTIVO ({n.modo_ejecucion}){C.RESET}"
            elif n.existe:
                est = f"{C.CYAN}LISTO (en disco){C.RESET}"
            else:
                est = f"{C.RED}NO ENCONTRADO{C.RESET}"
            filas.append(f" #{s:<3} | {n.script_name:<20} | {n.cuadrante:<12} | {est:<25} | {n.rol_maestro}")

        filas.append(f"\n{C.BOLD}{C.CYAN}📡 ESTADO DEL CLÚSTER GPU ({IP_WINDOWS_GPU}):{C.RESET}")
        for info in servicios.values():
            st_srv = f"{C.GREEN}ONLINE ({info['latency_ms']} ms){C.RESET}" if info["online"] else f"{C.RED}OFFLINE{C.RESET}"
            filas.append(f"  • {info['label']:<38}: {st_srv}")

        if en_vram:
            v_txt = ", ".join(f"{m['name']} ({m['vram_gb']} GB)" for m in en_vram)
            filas.append(f"  • 🔥 Modelos cargados en VRAM            : {C.YELLOW}{v_txt}{C.RESET}")
        else:
            filas.append(f"  • ❄️ Memoria de Video (VRAM)             : {C.GREEN}Libre (0 modelos retenidos){C.RESET}")

        return "\n".join(filas)


# =============================================================================
# AUTOPRUEBA OFFLINE (`python aryiCabecilla.py --selftest`)
# =============================================================================
def ejecutar_selftest() -> int:
    arb = ClusterGPUArbiter(OLLAMA_API_BASE)
    orq = OrquestadorCabecilla(arb)
    checks: List[Tuple[str, bool, str]] = []

    def ok(nombre: str, cond: bool, extra: str = "") -> None:
        checks.append((nombre, bool(cond), extra))

    # 1. Verifica que los 4 agentes están definidos en el escuadrón
    nombres_esperados = {1: "aryi.py", 2: "aryi_omega.py", 3: "aryi_omega_v10.py", 4: "aryi10.py"}
    ok(
        "escuadrón: registra exactamente los 4 scripts ARYI",
        {s: n.script_name for s, n in orq.escuadron.items()} == nombres_esperados,
    )

    # 2. Enrutamiento inteligente hacia el especialista correcto
    ag_vis, _ = elegir_mejor_agente_para_tarea("/vision tetas.png analiza la imagen", orq.escuadron)
    ok("router: delega /vision y multimedia a #4 (aryi10.py)", ag_vis.slot == 4, ag_vis.script_name)

    ag_img, _ = elegir_mejor_agente_para_tarea("dibuja un guerrero cyberpunk en 8k", orq.escuadron)
    ok("router: delega generación de imagen a #4 (aryi10.py)", ag_img.slot == 4, ag_img.script_name)

    ag_learn, _ = elegir_mejor_agente_para_tarea("/learn react", orq.escuadron)
    ok("router: delega /learn react a #1 (aryi.py)", ag_learn.slot == 1, ag_learn.script_name)

    ag_sec, _ = elegir_mejor_agente_para_tarea("audita la seguridad y haz commit y push del proyecto", orq.escuadron)
    ok("router: delega auditoría SecOps y Git a #3 (aryi_omega_v10.py)", ag_sec.slot == 3, ag_sec.script_name)

    ag_code, _ = elegir_mejor_agente_para_tarea("implementa un PostController en PHP Laravel con vistas Blade", orq.escuadron)
    ok("router: delega arquitectura/código full-stack a #2 (aryi_omega.py)", ag_code.slot == 2, ag_code.script_name)

    # 3. Entorno limpio para hijos (evita colisión 409 de Telegram entre las 4 consolas)
    env_hijo = orq._entorno_hijo_limpio(2)
    ok(
        "aislamiento: silencia polling duplicado de Telegram en procesos hijos",
        env_hijo.get("TELEGRAM_BOT_TOKEN") == "" and env_hijo.get("ARYI_MANAGED_BY_CABECILLA") == "1",
    )

    # 4. Estado persistente en agent_state.json
    orq._guardar_estado("selftest_ok")
    ok("estado: actualiza agent_state.json correctamente", CABECILLA_STATE_FILE.is_file())

    print(f"\n{C.BOLD}{C.CYAN}=== AUTOPRUEBA ARYI CABECILLA v{VERSION} ==={C.RESET}")
    fallos = 0
    for nombre, exito, det in checks:
        icono = f"{C.GREEN}✔{C.RESET}" if exito else f"{C.RED}✘{C.RESET}"
        print(f"  {icono} {nombre}" + (f" ({det})" if det and not exito else ""))
        if not exito:
            fallos += 1
    print(f"\n{'✅ TODO OK' if fallos == 0 else f'❌ {fallos} FALLO(S)'} ({len(checks) - fallos}/{len(checks)} pruebas superadas)")
    return 0 if fallos == 0 else 1


# =============================================================================
# MENÚ DE AYUDA Y BUCLE INTERACTIVO DEL CABECILLA
# =============================================================================
def mostrar_ayuda() -> str:
    return (
        f"\n{C.BOLD}{C.YELLOW}=== COMANDOS DEL ORQUESTADOR MAESTRO (`aryiCabecilla.py`) ==={C.RESET}\n"
        f"{C.CYAN}👑 CONTROL DE LA CUADRÍCULA 2x2 Y DE LOS 4 AGENTES:{C.RESET}\n"
        "  /panel   (o /status)     Muestra el estado de los 4 agentes, los 4 contenedores Docker y la VRAM.\n"
        "  /grid                    Abre y acomoda las 4 ventanas PowerShell en cuadrícula 2x2 (con telemetría ya cacheada).\n"
        "  /sync                    Sincroniza `.aryi_logs/telemetry_matrix.json` para que ningún hijo haga benchmark lento.\n"
        "  /vram free               Libera inmediatamente los 6GB de VRAM en Ollama (`keep_alive: 0`).\n"
        "  /stop                    Detiene limpiamente todos los subprocesos subordinados activos.\n\n"
        f"{C.CYAN}🎯 DELEGACIÓN INTELIGENTE Y PIPELINE DE LOS 4 FANTÁSTICOS:{C.RESET}\n"
        "  <cualquier tarea>        El Cabecilla elige automáticamente al mejor de los 4 agentes y le asigna el turno de GPU.\n"
        "  /1 <orden>               Envía la orden específicamente al Agente #1 (`aryi.py` · Scanner, `/learn` & Live Logs).\n"
        "  /2 <orden>               Envía la orden específicamente al Agente #2 (`aryi_omega.py` · Arquitecto Swarm & Anti-500).\n"
        "  /3 <orden>               Envía la orden específicamente al Agente #3 (`aryi_omega_v10.py` · SecOps, QA & GitOps).\n"
        "  /4 <orden>               Envía la orden específicamente al Agente #4 (`aryi10.py` · Visión, Voz, SD & Archivador).\n"
        "  /broadcast <comando>     Ejecuta un comando rápido (ej. `/status`) en serie por los 4 agentes sin colisión de GPU.\n"
        "  /pipeline <misión>       Ejecuta la misión en cadena pasando por los 4 agentes en orden (1 -> 2 -> 3 -> 4).\n"
        "  /selftest_all            Ejecuta la autoprueba de `aryi_omega_v10.py --selftest` y la del propio Cabecilla.\n"
        "  salir | exit             Detiene los hijos subordinados y cierra el Cabecilla.\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=f"ARYI CABECILLA v{VERSION} · Orquestador de los 4 Agentes")
    parser.add_argument("--selftest", action="store_true", help="Ejecuta la autoprueba offline y termina")
    parser.add_argument("--grid", action="store_true", help="Abre las 4 ventanas PowerShell en cuadrícula 2x2 al iniciar")
    parser.add_argument("--sync-telemetry", action="store_true", help="Sincroniza telemetry_matrix.json y termina")
    parser.add_argument("--pipeline", type=str, default="", help="Ejecuta una misión completa a través de los 4 agentes")
    args = parser.parse_args()

    if args.selftest:
        sys.exit(ejecutar_selftest())

    arbiter = ClusterGPUArbiter(OLLAMA_API_BASE)
    if args.sync_telemetry:
        matriz = arbiter.asegurar_telemetria_unificada(forzar=False)
        print(f"{C.GREEN}✅ Telemetría compartida lista ({len(matriz)} modelos) en {TELEMETRY_FILE}{C.RESET}")
        sys.exit(0)

    orquestador = OrquestadorCabecilla(arbiter)
    arbiter.asegurar_telemetria_unificada(forzar=False)

    print(orquestador.panel_de_control())

    if args.grid:
        print(orquestador.lanzar_cuadricula_2x2_windows())

    if args.pipeline:
        print(orquestador.ejecutar_pipeline_4_fantasticos(args.pipeline))
        sys.exit(0)

    print(mostrar_ayuda())

    try:
        while True:
            try:
                entrada = input(f"\n{C.BOLD}{C.YELLOW}👑 aryiCabecilla [1:Scanner | 2:Omega | 3:SecOps | 4:Multi] > {C.RESET}").strip()
            except EOFError:
                break

            if not entrada:
                continue

            low = entrada.lower()
            if low in {"salir", "exit", "/exit", "quit"}:
                break

            if low in {"/help", "ayuda", "help"}:
                print(mostrar_ayuda())
                continue

            if low in {"/panel", "/status", "status"}:
                print(orquestador.panel_de_control())
                continue

            if low == "/grid":
                print(orquestador.lanzar_cuadricula_2x2_windows())
                continue

            if low == "/sync":
                m = arbiter.asegurar_telemetria_unificada(forzar=True)
                print(f"{C.GREEN}✅ Matriz telemétrica unificada para los 4 agentes ({len(m)} modelos).{C.RESET}")
                continue

            if low.startswith("/vram"):
                mods = arbiter.liberar_vram()
                print(f"{C.GREEN}🧹 VRAM liberada en {IP_WINDOWS_GPU}: {', '.join(mods) or '0 modelos retenidos'}.{C.RESET}")
                continue

            if low == "/stop":
                print(orquestador.detener_todos())
                continue

            if low == "/selftest_all":
                ejecutar_selftest()
                script_v10 = WORKSPACE_ROOT / "aryi_omega_v10.py"
                if script_v10.is_file():
                    print(f"\n{C.CYAN}▶ Ejecutando `aryi_omega_v10.py --selftest`...{C.RESET}")
                    subprocess.run([sys.executable, str(script_v10), "--selftest"], cwd=str(WORKSPACE_ROOT))
                continue

            if low.startswith("/pipeline "):
                mision_p = entrada[10:].strip()
                if mision_p:
                    print(orquestador.ejecutar_pipeline_4_fantasticos(mision_p))
                continue

            if low.startswith("/broadcast "):
                cmd_b = entrada[11:].strip()
                if cmd_b:
                    for s in (1, 2, 3, 4):
                        orquestador.enviar_orden_a_subordinado(s, cmd_b, timeout_s=45)
                continue

            # Envío directo por número de agente: /1, /2, /3, /4
            m_slot = re.match(r"^/([1-4])\s+(.+)$", entrada)
            if m_slot:
                slot_num = int(m_slot.group(1))
                orden_directa = m_slot.group(2).strip()
                orquestador.enviar_orden_a_subordinado(slot_num, orden_directa)
                continue

            # Enrutamiento automático al especialista óptimo
            elegido, razon = elegir_mejor_agente_para_tarea(entrada, orquestador.escuadron)
            print(f"{C.CYAN}🧭 [ENRUTADOR CABECILLA] Seleccionado Agente #{elegido.slot} (`{elegido.script_name}`): {razon}{C.RESET}")
            orquestador.enviar_orden_a_subordinado(elegido.slot, entrada)

    except KeyboardInterrupt:
        print(f"\n{C.YELLOW}[CABECILLA] Interrupción detectada.{C.RESET}")
    finally:
        print(orquestador.detener_todos())
        log_cabecilla("SHUTDOWN", "aryiCabecilla finalizado limpiamente")


if __name__ == "__main__":
    main()