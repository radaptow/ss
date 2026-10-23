#!/usr/bin/env python3
"""
aryiCodigo.py - Definitive Autonomous Coding, System & Project Audit AI Agent
Cross-platform (Windows, Linux, BSD, macOS) | Zero external dependencies | Self-Healing Ollama Backend
"""

import os
import sys
import time
import json
import re
import shutil
import platform
import subprocess
import argparse
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

# Enable ANSI escape codes on Windows 10/11 terminals
if platform.system() == "Windows":
    os.system("")

# =====================================================================
# CONFIGURATION & STYLING
# =====================================================================
DEFAULT_OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
DEFAULT_MODEL = os.environ.get("ARYI_MODEL", "qwen2.5-coder:latest")

IGNORED_DIRS = {
    ".git", "__pycache__", "node_modules", "vendor", "venv", ".venv",
    "env", ".idea", ".vscode", "dist", "build", "target", ".next"
}

CODE_EXTENSIONS = {
    ".py", ".php", ".js", ".ts", ".html", ".css", ".c", ".cpp", ".h", ".hpp",
    ".sh", ".bat", ".ps1", ".sql", ".json", ".yml", ".yaml", ".xml", ".md",
    ".ini", ".conf", ".env.example", "Dockerfile", "Makefile"
}

class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


# =====================================================================
# OS & ENVIRONMENT DETECTION
# =====================================================================
def get_os_profile() -> dict:
    sys_name = platform.system()
    info = {
        "os": sys_name,
        "release": platform.release(),
        "arch": platform.machine(),
        "cwd": str(Path.cwd()),
        "pkg_manager": "unknown",
        "shell": "bash" if sys_name != "Windows" else "powershell"
    }

    if sys_name == "Windows":
        info["pkg_manager"] = "winget (or choco)"
    elif sys_name == "Linux":
        for mgr, cmd in [
            ("pacman (Arch)", "pacman"),
            ("apt (Debian/Ubuntu/Zorin)", "apt"),
            ("dnf (Fedora/RHEL)", "dnf"),
            ("zypper (openSUSE)", "zypper"),
            ("apk (Alpine)", "apk")
        ]:
            if shutil.which(cmd):
                info["pkg_manager"] = mgr
                break
    elif "BSD" in sys_name:
        info["pkg_manager"] = "pkg (FreeBSD) / pkg_add (OpenBSD)"
        info["shell"] = "sh"
    elif sys_name == "Darwin":
        info["pkg_manager"] = "brew (Homebrew)"

    return info


# =====================================================================
# SYSTEM PROMPT BUILDER
# =====================================================================
def build_system_prompt(os_profile: dict) -> str:
    return f"""You are Aryi (aryiCodigo), an elite autonomous AI software engineer, system administrator, and code auditor.

ENVIRONMENT CONTEXT:
- Operating System: {os_profile['os']} ({os_profile['release']} / {os_profile['arch']})
- Default Shell: {os_profile['shell']}
- Detected Package Manager: {os_profile['pkg_manager']}
- Current Working Directory: {os_profile['cwd']}

AVAILABLE TOOLS:
Whenever you need to interact with the file system or execute commands, output a tool call inside `<tool_call>` tags containing valid JSON. You can chain multiple steps across turns: after you emit a `<tool_call>`, the system will execute it and return the `<tool_result>` to you.

Supported Tools:
1. `list_dir` - Explore directory contents or tree structure.
   <tool_call>{{"tool": "list_dir", "path": ".", "recursive": true}}</tool_call>

2. `read_file` - Read the contents of a file before editing or analyzing it.
   <tool_call>{{"tool": "read_file", "path": "src/index.php"}}</tool_call>

3. `write_file` - Create a new file or overwrite an existing file with complete, working code.
   <tool_call>{{"tool": "write_file", "path": "app/main.py", "content": "print('Hello')"}}</tool_call>

4. `make_dir` - Create a new folder (and any parent directories).
   <tool_call>{{"tool": "make_dir", "path": "src/components"}}</tool_call>

5. `search_files` - Search for a text pattern or regex across files in a directory.
   <tool_call>{{"tool": "search_files", "path": ".", "pattern": "TODO|FIXME|function"}}</tool_call>

6. `run_command` - Execute shell commands (install packages, run compilers/linters/tests, git operations, system tasks).
   - On Windows, use `winget install <pkg>` or PowerShell commands.
   - On Linux/BSD, use the detected package manager (e.g., `sudo apt install -y <pkg>`, `sudo pacman -S --noconfirm <pkg>`).
   <tool_call>{{"tool": "run_command", "command": "git status"}}</tool_call>

RULES OF ENGAGEMENT:
1. When asked to modify or improve existing projects, ALWAYS inspect the directory (`list_dir`) and read the target files (`read_file`) before writing changes.
2. Never output lazy placeholders like `// ... rest of code here` when using `write_file`. Always write the complete, functional file content.
3. Wait for `<tool_result>` after issuing `<tool_call>` blocks before making final conclusions.
4. Once all actions are complete, provide a clear, concise summary of what you built, fixed, or executed.
"""


# =====================================================================
# CORE AGENT CLASS
# =====================================================================
class AryiAgent:
    def __init__(self, model: str = DEFAULT_MODEL, url: str = DEFAULT_OLLAMA_URL, auto_approve: bool = False):
        self.model = model
        # Normalize base URL (strip /api/chat or trailing slashes if passed)
        self.base_url = url.split("/api/")[0].rstrip("/")
        # Replace localhost with 127.0.0.1 to avoid IPv6 (::1) resolution hangs on Windows/Linux
        self.base_url = self.base_url.replace("://localhost", "://127.0.0.1")
        self.url = f"{self.base_url}/api/chat"

        self.auto_approve = auto_approve
        self.os_profile = get_os_profile()
        self.installed_models = []
        self.max_autonomous_steps = 15

        # Self-healing connection & model check on startup
        self.ensure_ollama_ready()
        self.messages = [{"role": "system", "content": build_system_prompt(self.os_profile)}]

    # -----------------------------------------------------------------
    # SELF-HEALING OLLAMA CONNECTION & MODEL AUTO-DETECTION
    # -----------------------------------------------------------------
    def _ping_ollama(self, timeout: int = 3) -> list:
        """Returns list of installed model names if reachable, or raises URLError."""
        tags_url = f"{self.base_url}/api/tags"
        req = urllib.request.Request(tags_url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return [m.get("name") for m in data.get("models", []) if m.get("name")]

    def _try_start_ollama_service(self) -> bool:
        """Attempts to start `ollama serve` in the background if running locally."""
        if "127.0.0.1" not in self.base_url and "localhost" not in self.base_url:
            return False

        ollama_bin = shutil.which("ollama")
        if not ollama_bin:
            # Check standard Windows install path if not in PATH yet
            if self.os_profile["os"] == "Windows":
                win_path = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
                if win_path.exists():
                    ollama_bin = str(win_path)

        if not ollama_bin:
            print(f"{Colors.RED}[!] 'ollama' executable not found in PATH.{Colors.RESET}")
            print(f"{Colors.YELLOW}    Install Ollama from https://ollama.com or check your PATH variable.{Colors.RESET}")
            return False

        print(f"{Colors.YELLOW}[⚡] Ollama is not running. Auto-starting `{ollama_bin} serve` in background...{Colors.RESET}")
        try:
            if self.os_profile["os"] == "Windows":
                creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) | getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
                subprocess.Popen(
                    [ollama_bin, "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    creationflags=creation_flags
                )
            else:
                subprocess.Popen(
                    [ollama_bin, "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True
                )

            # Poll for up to 10 seconds until Ollama responds
            for i in range(10):
                time.sleep(1)
                try:
                    self.installed_models = self._ping_ollama(timeout=2)
                    print(f"{Colors.GREEN}[✓] Ollama server started successfully at {self.base_url}!{Colors.RESET}")
                    return True
                except Exception:
                    continue
        except Exception as e:
            print(f"{Colors.RED}[!] Failed to launch `ollama serve`: {e}{Colors.RESET}")

        return False

    def ensure_ollama_ready(self) -> bool:
        """Verifies server reachability, auto-starts if down, and auto-selects a valid model."""
        connected = False
        try:
            self.installed_models = self._ping_ollama(timeout=3)
            connected = True
        except Exception:
            # Server unreachable -> attempt auto-start
            connected = self._try_start_ollama_service()

        if not connected:
            print(f"\n{Colors.RED}{Colors.BOLD}[!] Connection Diagnostic: Cannot reach Ollama at {self.base_url}{Colors.RESET}")
            print(f"{Colors.YELLOW}    Troubleshooting steps:{Colors.RESET}")
            print("    1. Open a terminal and run: `ollama serve`")
            print("    2. On Linux with systemd, run: `sudo systemctl restart ollama`")
            print("    3. If Ollama is on another PC/container, launch Aryi with: `python aryiCodigo.py -u http://SERVER_IP:11434`")
            return False

        # Check if any models are installed
        if not self.installed_models:
            print(f"{Colors.YELLOW}[!] Connected to Ollama, but you have 0 models installed.{Colors.RESET}")
            ollama_bin = shutil.which("ollama")
            if ollama_bin:
                choice = input(f"{Colors.CYAN}[?] Would you like Aryi to pull `qwen2.5-coder:7b` now? [y/n]: {Colors.RESET}").strip().lower()
                if choice in ("y", "yes"):
                    subprocess.run([ollama_bin, "pull", "qwen2.5-coder:7b"])
                    try:
                        self.installed_models = self._ping_ollama()
                    except Exception:
                        pass
            if not self.installed_models:
                return False

        # Auto-select model if the requested model tag isn't installed
        if self.model not in self.installed_models:
            requested_base = self.model.split(":")[0].lower()
            preferred_order = [
                requested_base,
                "qwen2.5-coder",
                "qwen",
                "deepseek-coder",
                "codellama",
                "llama3",
                "gemma"
            ]
            selected = None
            for pref in preferred_order:
                match = next((m for m in self.installed_models if pref in m.lower()), None)
                if match:
                    selected = match
                    break
            if not selected:
                selected = self.installed_models[0]

            print(f"{Colors.YELLOW}[i] Model '{self.model}' not found locally.{Colors.RESET}")
            print(f"{Colors.GREEN}[✓] Auto-selected installed model: '{selected}'{Colors.RESET}")
            self.model = selected

        return True

    def refresh_system_prompt(self):
        self.os_profile = get_os_profile()
        self.messages[0] = {"role": "system", "content": build_system_prompt(self.os_profile)}

    def confirm_action(self, description: str) -> bool:
        if self.auto_approve:
            return True
        while True:
            choice = input(
                f"{Colors.YELLOW}[?] Allow Aryi to {description}? [y/n/a(lways)]: {Colors.RESET}"
            ).strip().lower()
            if choice in ("y", "yes"):
                return True
            if choice in ("a", "always"):
                self.auto_approve = True
                print(f"{Colors.GREEN}[*] Autonomous mode enabled for this session.{Colors.RESET}")
                return True
            if choice in ("n", "no"):
                return False

    # -----------------------------------------------------------------
    # TOOL IMPLEMENTATIONS
    # -----------------------------------------------------------------
    def tool_list_dir(self, path: str = ".", recursive: bool = False) -> str:
        target = Path(path).resolve()
        if not target.exists():
            return f"Error: Path '{path}' does not exist."
        if not target.is_dir():
            return f"Error: Path '{path}' is not a directory."

        entries = []
        try:
            if not recursive:
                for item in sorted(target.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                    if item.name in IGNORED_DIRS:
                        continue
                    prefix = "[DIR] " if item.is_dir() else "[FILE]"
                    size = f" ({item.stat().st_size} B)" if item.is_file() else ""
                    entries.append(f"{prefix} {item.name}{size}")
            else:
                for root, dirs, files in os.walk(target):
                    dirs[:] = [d for d in sorted(dirs) if d not in IGNORED_DIRS]
                    rel_root = Path(root).relative_to(target)
                    depth = 0 if str(rel_root) == "." else len(rel_root.parts)
                    if depth > 4:
                        continue
                    indent = "  " * depth
                    folder_name = "." if str(rel_root) == "." else rel_root.name
                    entries.append(f"{indent}[DIR] {folder_name}/")
                    for f in sorted(files):
                        entries.append(f"{indent}  - {f}")
        except Exception as e:
            return f"Error listing directory: {e}"

        return "\n".join(entries[:400]) if entries else "(Empty directory)"

    def tool_read_file(self, path: str) -> str:
        target = Path(path).resolve()
        if not target.exists():
            return f"Error: File '{path}' does not exist."
        if not target.is_file():
            return f"Error: '{path}' is not a regular file."
        try:
            content = target.read_text(encoding="utf-8", errors="replace")
            if len(content) > 25000:
                return content[:25000] + "\n\n... [Truncated: File exceeds 25,000 chars]"
            return content
        except Exception as e:
            return f"Error reading file '{path}': {e}"

    def tool_write_file(self, path: str, content: str) -> str:
        target = Path(path).resolve()
        action_type = "overwrite" if target.exists() else "create"
        if not self.confirm_action(f"{action_type} file '{target}' ({len(content)} chars)"):
            return "Action cancelled by user."
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return f"Success: Wrote {len(content)} characters to '{target}'."
        except Exception as e:
            return f"Error writing file '{path}': {e}"

    def tool_make_dir(self, path: str) -> str:
        target = Path(path).resolve()
        try:
            target.mkdir(parents=True, exist_ok=True)
            return f"Success: Directory '{target}' created/verified."
        except Exception as e:
            return f"Error creating directory '{path}': {e}"

    def tool_search_files(self, path: str = ".", pattern: str = "") -> str:
        target = Path(path).resolve()
        if not target.exists():
            return f"Error: Path '{path}' does not exist."
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            return f"Invalid regex pattern: {e}"

        matches = []
        for root, dirs, files in os.walk(target):
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
            for file in files:
                fpath = Path(root) / file
                if fpath.suffix.lower() not in CODE_EXTENSIONS and fpath.name not in CODE_EXTENSIONS:
                    continue
                try:
                    lines = fpath.read_text(encoding="utf-8", errors="ignore").splitlines()
                    for idx, line in enumerate(lines, 1):
                        if regex.search(line):
                            rel = fpath.relative_to(target)
                            matches.append(f"{rel}:{idx}: {line.strip()[:120]}")
                            if len(matches) >= 100:
                                return "\n".join(matches) + "\n... [Max 100 matches reached]"
                except Exception:
                    continue
        return "\n".join(matches) if matches else f"No matches found for pattern '{pattern}'."

    def tool_run_command(self, command: str) -> str:
        if not self.confirm_action(f"execute command: `{command}`"):
            return "Command execution cancelled by user."

        print(f"{Colors.DIM}[$] Running: {command}{Colors.RESET}")
        try:
            if self.os_profile["os"] == "Windows":
                proc = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", command],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
            else:
                shell_bin = "/bin/bash" if Path("/bin/bash").exists() else "/bin/sh"
                proc = subprocess.run(
                    command,
                    shell=True,
                    executable=shell_bin,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
            output = ""
            if proc.stdout:
                output += f"STDOUT:\n{proc.stdout.strip()}\n"
            if proc.stderr:
                output += f"STDERR:\n{proc.stderr.strip()}\n"
            output += f"Exit Code: {proc.returncode}"
            return output[:12000]
        except subprocess.TimeoutExpired:
            return "Error: Command timed out after 300 seconds."
        except Exception as e:
            return f"Error executing command: {e}"

    # -----------------------------------------------------------------
    # TOOL DISPATCHER & PARSER
    # -----------------------------------------------------------------
    def extract_tool_calls(self, response_text: str) -> list:
        calls = []
        pattern = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)
        for match in pattern.finditer(response_text):
            raw_json = match.group(1)
            try:
                calls.append(json.loads(raw_json))
            except json.JSONDecodeError:
                continue

        if not calls:
            fallback = re.compile(r"```json\s*(\{\s*\"tool\"\s*:.*?\})\s*```", re.DOTALL)
            for match in fallback.finditer(response_text):
                try:
                    calls.append(json.loads(match.group(1)))
                except json.JSONDecodeError:
                    continue

        return calls

    def execute_tool(self, tool_data: dict) -> str:
        tool_name = tool_data.get("tool")
        print(f"{Colors.CYAN}[⚙ Tool] {tool_name}{Colors.RESET} -> {json.dumps({k: v for k, v in tool_data.items() if k != 'content'})}")

        if tool_name == "list_dir":
            return self.tool_list_dir(
                path=tool_data.get("path", "."),
                recursive=bool(tool_data.get("recursive", False))
            )
        elif tool_name == "read_file":
            return self.tool_read_file(path=tool_data.get("path", ""))
        elif tool_name == "write_file":
            return self.tool_write_file(
                path=tool_data.get("path", ""),
                content=tool_data.get("content", "")
            )
        elif tool_name == "make_dir":
            return self.tool_make_dir(path=tool_data.get("path", ""))
        elif tool_name == "search_files":
            return self.tool_search_files(
                path=tool_data.get("path", "."),
                pattern=tool_data.get("pattern", "")
            )
        elif tool_name == "run_command":
            return self.tool_run_command(command=tool_data.get("command", ""))
        else:
            return f"Error: Unknown tool '{tool_name}'."

    # -----------------------------------------------------------------
    # OLLAMA LLM COMMUNICATION (WITH AUTO-RECOVERY)
    # -----------------------------------------------------------------
    def call_llm(self, messages: list = None, _retried: bool = False) -> str:
        payload = {
            "model": self.model,
            "messages": messages if messages is not None else self.messages,
            "stream": True,
            "options": {
                "temperature": 0.2,
                "num_ctx": 16384
            }
        }
        req = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        full_response = []
        print(f"{Colors.GREEN}{Colors.BOLD}Aryi ({self.model}):{Colors.RESET} ", end="", flush=True)
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                for line in resp:
                    if not line:
                        continue
                    chunk = json.loads(line.decode("utf-8"))
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        print(token, end="", flush=True)
                        full_response.append(token)
                    if chunk.get("done"):
                        break
            print()
            return "".join(full_response)

        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            print(f"\n{Colors.RED}[!] Ollama HTTP {e.code} Error:{Colors.RESET} {err_body}")
            if e.code == 404 and not _retried:
                print(f"{Colors.YELLOW}[⚡] Model or endpoint mismatch detected. Auto-selecting valid model and retrying...{Colors.RESET}")
                if self.ensure_ollama_ready():
                    return self.call_llm(messages=messages, _retried=True)
            return ""

        except urllib.error.URLError as e:
            print(f"\n{Colors.RED}[!] Connection error ({e.reason}). Attempting auto-recovery...{Colors.RESET}")
            if not _retried and self.ensure_ollama_ready():
                return self.call_llm(messages=messages, _retried=True)
            return ""

        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}[!] Generation interrupted by user.{Colors.RESET}")
            return "".join(full_response)

    # -----------------------------------------------------------------
    # AUTONOMOUS REACT LOOP
    # -----------------------------------------------------------------
    def chat(self, user_input: str):
        self.refresh_system_prompt()
        self.messages.append({"role": "user", "content": user_input})

        for _ in range(self.max_autonomous_steps):
            response = self.call_llm()
            if not response:
                return

            self.messages.append({"role": "assistant", "content": response})
            tool_calls = self.extract_tool_calls(response)

            if not tool_calls:
                break

            tool_results_summary = []
            for call in tool_calls:
                result = self.execute_tool(call)
                preview = result[:300].replace("\n", " ") + ("..." if len(result) > 300 else "")
                print(f"{Colors.DIM}  ↳ Result: {preview}{Colors.RESET}")
                tool_results_summary.append(
                    f"<tool_result tool=\"{call.get('tool')}\">\n{result}\n</tool_result>"
                )

            self.messages.append({
                "role": "user",
                "content": "\n\n".join(tool_results_summary) + "\n\nContinue with the next step or provide your final answer."
            })
        else:
            print(f"{Colors.YELLOW}[!] Reached maximum autonomous steps ({self.max_autonomous_steps}). Pausing for user input.{Colors.RESET}")

    # -----------------------------------------------------------------
    # DEEP ROOT DIRECTORY AUDITOR (BUGS & IMPROVEMENTS)
    # -----------------------------------------------------------------
    def audit_project(self, root_path: str = ".", save_report: bool = True):
        target = Path(root_path).resolve()
        if not target.exists() or not target.is_dir():
            print(f"{Colors.RED}[!] Invalid directory for audit: {target}{Colors.RESET}")
            return

        print(f"{Colors.HEADER}{Colors.BOLD}[🔍 Auditing Project Root]: {target}{Colors.RESET}")
        tree_snapshot = self.tool_list_dir(str(target), recursive=True)

        collected_files = []
        total_chars = 0
        max_audit_chars = 45000

        for root, dirs, files in os.walk(target):
            dirs[:] = [d for d in sorted(dirs) if d not in IGNORED_DIRS]
            for f in sorted(files):
                fpath = Path(root) / f
                if fpath.name == "ARYI_AUDIT_REPORT.md":
                    continue
                if fpath.suffix.lower() in CODE_EXTENSIONS or fpath.name in CODE_EXTENSIONS:
                    try:
                        size = fpath.stat().st_size
                        if size == 0 or size > 100_000:
                            continue
                        content = fpath.read_text(encoding="utf-8", errors="replace")
                        rel_path = fpath.relative_to(target)
                        snippet = content[:6000] + ("\n... [Truncated]" if len(content) > 6000 else "")
                        entry = f"### File: `{rel_path}`\n```\n{snippet}\n```\n"
                        if total_chars + len(entry) <= max_audit_chars:
                            collected_files.append(entry)
                            total_chars += len(entry)
                    except Exception:
                        continue

        print(f"{Colors.CYAN}[*] Scanned {len(collected_files)} source files ({total_chars} chars). Generating Bug & Improvement Audit...{Colors.RESET}\n")

        audit_prompt = f"""Perform an exhaustive technical code audit of the project located at `{target}`.

### 1. PROJECT DIRECTORY TREE


### 2. SOURCE CODE SNAPSHOTS
{"".join(collected_files)}

---
Produce a comprehensive, actionable Markdown report structured EXACTLY with these sections:
1. **Executive Summary & Architecture Overview**
2. **List of Bugs & Security Vulnerabilities** (Include exact file names, severity `[CRITICAL / HIGH / MEDIUM / LOW]`, root cause, and how to fix each bug)
3. **List of Code & Architecture Improvements** (Performance bottlenecks, refactoring opportunities, error handling, cross-platform compatibility, security hardening, and modern best practices)
4. **Prioritized Action Plan** (A numbered checklist of immediate fixes you can apply right now if asked)

Do NOT call any tools in this turn—analyze the provided source files directly and output the full report."""

        audit_messages = [
            {"role": "system", "content": "You are Aryi, a principal software architect and security auditor."},
            {"role": "user", "content": audit_prompt}
        ]

        report_content = self.call_llm(messages=audit_messages)
        if not report_content:
            return

        self.messages.append({"role": "user", "content": f"Audit the project at {target}"})
        self.messages.append({"role": "assistant", "content": report_content})

        if save_report:
            report_file = target / "ARYI_AUDIT_REPORT.md"
            try:
                header = f"# Aryi Autonomous Audit Report\n* **Project**: `{target}`\n* **Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n* **Model**: `{self.model}`\n\n---\n\n"
                report_file.write_text(header + report_content, encoding="utf-8")
                print(f"\n{Colors.GREEN}[✓] Audit report saved to: {report_file}{Colors.RESET}")
                print(f"{Colors.CYAN}[Tip] You can now tell Aryi: 'Fix the bugs listed in the audit report' in this session!{Colors.RESET}")
            except Exception as e:
                print(f"\n{Colors.RED}[!] Could not save report file: {e}{Colors.RESET}")


# =====================================================================
# INTERACTIVE CLI & ENTRY POINT
# =====================================================================
def print_banner(agent: AryiAgent):
    os_p = agent.os_profile
    models_str = ", ".join(agent.installed_models[:4]) + ("..." if len(agent.installed_models) > 4 else "")
    print(f"""{Colors.HEADER}{Colors.BOLD}
======================================================================
   ___               _  _____           _ _             
  / _ \\             (_)/  __ \\         | (_)            
 / /_\\ \\_ __ _   _   _ | /  \\/ ___   __| |_  __ _  ___  
 |  _  | '__| | | | | || |    / _ \\ / _` | |/ _` |/ _ \\ 
 | | | | |  | |_| | | || \\__/\\ (_) | (_| | | (_| | (_) |
 \\_| |_/_|   \\__, | |_| \\____/\\___/ \\__,_|_|\\__, |\\___/ 
              __/ |                          __/ |      
             |___/                          |___/       
======================================================================{Colors.RESET}
 {Colors.CYAN}OS:{Colors.RESET} {os_p['os']} ({os_p['pkg_manager']}) | {Colors.CYAN}Active Model:{Colors.RESET} {Colors.GREEN}{agent.model}{Colors.RESET}
 {Colors.CYAN}Endpoint:{Colors.RESET} {agent.base_url} | {Colors.CYAN}Installed:{Colors.RESET} {models_str or 'None'}
 {Colors.CYAN}CWD:{Colors.RESET} {os_p['cwd']} | {Colors.CYAN}Auto-Approve:{Colors.RESET} {agent.auto_approve}
 {Colors.DIM}Commands: /audit [path] | /models | /model <name> | /doctor | /cd <path> | /auto | /clear | /exit{Colors.RESET}
""")


def main():
    parser = argparse.ArgumentParser(description="aryiCodigo - Autonomous Coding, System & Project Audit Agent")
    parser.add_argument("prompt", nargs="*", help="One-shot task prompt for Aryi")
    parser.add_argument("-m", "--model", default=DEFAULT_MODEL, help=f"Ollama model name (default: {DEFAULT_MODEL})")
    parser.add_argument("-u", "--url", default=DEFAULT_OLLAMA_URL, help=f"Ollama API URL (default: {DEFAULT_OLLAMA_URL})")
    parser.add_argument("-a", "--audit", metavar="PATH", help="Scan a root directory for bugs and improvements")
    parser.add_argument("-y", "--auto", action="store_true", help="Auto-approve all file writes and shell commands")
    args = parser.parse_args()

    agent = AryiAgent(model=args.model, url=args.url, auto_approve=args.auto)

    # 1. One-shot Audit Mode via CLI
    if args.audit:
        agent.audit_project(args.audit)
        return

    # 2. One-shot Prompt Mode via CLI
    if args.prompt:
        task = " ".join(args.prompt)
        agent.chat(task)
        return

    # 3. Interactive REPL Mode
    print_banner(agent)
    while True:
        try:
            cwd_name = Path.cwd().name or str(Path.cwd())
            user_input = input(f"\n{Colors.BLUE}{Colors.BOLD}[{cwd_name}] You > {Colors.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Colors.GREEN}Goodbye!{Colors.RESET}")
            break

        if not user_input:
            continue

        # Slash command handling
        if user_input.startswith("/"):
            parts = user_input.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            if cmd in ("/exit", "/quit", "/q"):
                print(f"{Colors.GREEN}Shutting down Aryi. Goodbye!{Colors.RESET}")
                break
            elif cmd == "/help":
                print(f"""
{Colors.BOLD}Available Slash Commands:{Colors.RESET}
  {Colors.CYAN}/audit [path]{Colors.RESET}  - Crawl root directory (default: current dir), find bugs & improvements, and save ARYI_AUDIT_REPORT.md
  {Colors.CYAN}/models{Colors.RESET}        - List all locally installed Ollama models
  {Colors.CYAN}/model <name>{Colors.RESET}  - Switch active Ollama model on the fly
  {Colors.CYAN}/doctor{Colors.RESET}        - Run Ollama connection diagnostic and auto-start check
  {Colors.CYAN}/cd <path>{Colors.RESET}     - Change working directory
  {Colors.CYAN}/auto{Colors.RESET}          - Toggle autonomous approval mode on/off
  {Colors.CYAN}/clear{Colors.RESET}         - Reset conversation memory
  {Colors.CYAN}/exit{Colors.RESET}          - Exit Aryi
""")
            elif cmd == "/audit":
                target_dir = arg if arg else "."
                agent.audit_project(target_dir)
            elif cmd == "/models":
                agent.ensure_ollama_ready()
                print(f"{Colors.CYAN}Installed Ollama Models:{Colors.RESET}")
                for idx, m in enumerate(agent.installed_models, 1):
                    active_marker = f" {Colors.GREEN}(active){Colors.RESET}" if m == agent.model else ""
                    print(f"  {idx}. {m}{active_marker}")
            elif cmd == "/model":
                if arg:
                    agent.model = arg.strip()
                    print(f"{Colors.GREEN}[✓] Switched model to: {agent.model}{Colors.RESET}")
                else:
                    print(f"Current model: {agent.model} (Use `/models` to see available tags)")
            elif cmd == "/doctor":
                if agent.ensure_ollama_ready():
                    print(f"{Colors.GREEN}[✓] Ollama is healthy at {agent.base_url} | Active model: {agent.model}{Colors.RESET}")
            elif cmd == "/cd":
                if not arg:
                    print(f"Current directory: {Path.cwd()}")
                else:
                    try:
                        os.chdir(Path(arg).expanduser().resolve())
                        agent.refresh_system_prompt()
                        print(f"{Colors.GREEN}[✓] Changed working directory to: {Path.cwd()}{Colors.RESET}")
                    except Exception as e:
                        print(f"{Colors.RED}[!] Failed to change directory: {e}{Colors.RESET}")
            elif cmd == "/auto":
                agent.auto_approve = not agent.auto_approve
                print(f"{Colors.GREEN}[✓] Auto-approve set to: {agent.auto_approve}{Colors.RESET}")
            elif cmd == "/clear":
                agent.messages = [{"role": "system", "content": build_system_prompt(agent.os_profile)}]
                print(f"{Colors.GREEN}[✓] Conversation memory cleared.{Colors.RESET}")
            else:
                print(f"{Colors.YELLOW}[!] Unknown command '{cmd}'. Type /help for options.{Colors.RESET}")
            continue

        # Standard Autonomous Chat / Action Loop
        agent.chat(user_input)


if __name__ == "__main__":
    main()