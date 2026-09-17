"""
Terminal Control — Full terminal access for command execution and system management.
Provides:
  - execute: Run arbitrary shell commands (PowerShell/CMD on Windows, Bash on Unix)
  - list_processes: View active running processes with PID, memory, and CPU usage
  - kill_process: Terminate processes by PID or process name
  - system_info: Inspect system OS, hostname, architecture, CPU, memory, and disk status
"""
from __future__ import annotations

import os
import sys
import time
import subprocess
import platform
from pathlib import Path
from typing import Any

import psutil

_OS = platform.system()  # "Windows" | "Darwin" | "Linux"

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def execute_shell(command: str, cwd: str | None = None, timeout: int = 45) -> dict[str, Any]:
    """Execute a shell command securely and capture full output."""
    if not command or not command.strip():
        return {"success": False, "error": "Command is empty.", "returncode": -1}

    cmd_str = command.strip()
    target_cwd = cwd if cwd and Path(cwd).is_dir() else str(_get_base_dir())

    try:
        if _OS == "Windows":
            # Run in PowerShell with Windows-safe flags
            shell_cmd = ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", cmd_str]
            creationflags = subprocess.CREATE_NO_WINDOW
        else:
            shell_cmd = ["/bin/bash", "-c", cmd_str]
            creationflags = 0

        proc = subprocess.run(
            shell_cmd,
            cwd=target_cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=creationflags if _OS == "Windows" else 0,
            encoding="utf-8",
            errors="replace"
        )

        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()
        success = (proc.returncode == 0)

        # Truncate very long outputs for conversational clarity
        max_chars = 3500
        if len(stdout) > max_chars:
            stdout = stdout[:max_chars] + f"\n... [Truncated {len(stdout) - max_chars} characters]"
        if len(stderr) > max_chars:
            stderr = stderr[:max_chars] + f"\n... [Truncated {len(stderr) - max_chars} characters]"

        return {
            "success": success,
            "returncode": proc.returncode,
            "stdout": stdout or "(no stdout)",
            "stderr": stderr,
            "cwd": target_cwd,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Command timed out after {timeout} seconds.", "returncode": -1}
    except Exception as e:
        return {"success": False, "error": str(e), "returncode": -1}


def get_process_list(filter_name: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """List running processes filtered by name or sorted by memory usage."""
    procs = []
    filter_lower = filter_name.lower().strip() if filter_name else None

    for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
        try:
            info = p.info
            name = info.get('name') or ""
            if filter_lower:
                if filter_lower in name.lower():
                    procs.append({
                        "pid": info['pid'],
                        "name": name,
                        "cpu": round(info.get('cpu_percent') or 0.0, 1),
                        "mem": round(info.get('memory_percent') or 0.0, 1),
                        "status": info.get('status')
                    })
            else:
                procs.append({
                    "pid": info['pid'],
                    "name": name,
                    "cpu": round(info.get('cpu_percent') or 0.0, 1),
                    "mem": round(info.get('memory_percent') or 0.0, 1),
                    "status": info.get('status')
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    if not filter_lower:
        procs.sort(key=lambda x: x["mem"], reverse=True)
    return procs[:limit]


def terminate_process(target: str | int) -> str:
    """Terminate a process by PID or exact/partial name."""
    try:
        pid = int(target)
        p = psutil.Process(pid)
        p_name = p.name()
        p.terminate()
        return f"Process '{p_name}' (PID: {pid}) terminated successfully."
    except ValueError:
        # It's a name
        killed = []
        name_str = str(target).lower().strip()
        for p in psutil.process_iter(['pid', 'name']):
            try:
                if name_str in (p.info['name'] or '').lower():
                    p.terminate()
                    killed.append(f"{p.info['name']} (PID {p.info['pid']})")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        if killed:
            return f"Terminated {len(killed)} process(es): {', '.join(killed)}."
        return f"No active process matching '{target}' was found."
    except psutil.NoSuchProcess:
        return f"Process with PID {target} does not exist."
    except psutil.AccessDenied:
        return f"Access denied: cannot terminate PID {target}. Try running with admin privileges."
    except Exception as e:
        return f"Failed to terminate process {target}: {e}"


def get_system_summary() -> dict[str, Any]:
    """Return OS, hardware, and disk summary."""
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/') if _OS != "Windows" else psutil.disk_usage('C:\\')
    return {
        "os": platform.platform(),
        "hostname": platform.node(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "cpu_count_logical": psutil.cpu_count(logical=True),
        "cpu_usage_pct": psutil.cpu_percent(interval=0.1),
        "ram_total_gb": round(mem.total / (1024 ** 3), 2),
        "ram_used_pct": mem.percent,
        "disk_free_gb": round(disk.free / (1024 ** 3), 2),
        "disk_total_gb": round(disk.total / (1024 ** 3), 2),
    }


def terminal_control(parameters: dict, player=None, speak=None) -> str:
    """Main entrypoint for terminal_control tool."""
    params = parameters or {}
    action = str(params.get("action") or "execute").lower().strip()
    cmd = str(params.get("command") or "").strip()
    cwd = params.get("working_dir")
    timeout = int(params.get("timeout") or 45)
    target = params.get("target") or params.get("pid") or params.get("name") or cmd

    print(f"[Terminal] Action: '{action}' | Command: '{cmd[:60]}'")
    if player and hasattr(player, "write_log"):
        player.write_log(f"[Terminal] {action}: {cmd[:50] or target}")

    if action in ("execute", "run", "cmd", "powershell", "shell"):
        if not cmd:
            return "Error: No command specified for execution."
        res = execute_shell(cmd, cwd=cwd, timeout=timeout)
        if not res["success"]:
            err_msg = res.get("error") or res.get("stderr") or "Command returned non-zero exit code."
            return f"Command failed (Code {res['returncode']}):\n{err_msg}\nStdout:\n{res['stdout']}"
        return f"Command executed successfully (Code 0):\n{res['stdout']}"

    if action in ("list_processes", "processes", "ps", "top"):
        filter_str = str(params.get("filter") or cmd).strip() if (params.get("filter") or cmd) else None
        procs = get_process_list(filter_str, limit=15)
        if not procs:
            return f"No processes found matching '{filter_str}'."
        lines = [f"Top active processes (Total {len(procs)}):"]
        for p in procs:
            lines.append(f"• PID {p['pid']:<6} | {p['name']:<25} | RAM: {p['mem']}% | CPU: {p['cpu']}%")
        return "\n".join(lines)

    if action in ("kill_process", "kill", "terminate", "stop_process"):
        if not target:
            return "Error: Please specify the PID or process name to terminate."
        return terminate_process(target)

    if action in ("system_info", "sys_info", "specs", "hardware_info"):
        info = get_system_summary()
        return (
            f"System Information:\n"
            f"• OS: {info['os']}\n"
            f"• Host: {info['hostname']} ({info['architecture']})\n"
            f"• CPU: {info['cpu_count_logical']} threads ({info['cpu_usage_pct']}% usage)\n"
            f"• RAM: {info['ram_used_pct']}% used of {info['ram_total_gb']} GB\n"
            f"• Storage: {info['disk_free_gb']} GB free of {info['disk_total_gb']} GB"
        )

    return f"Unknown terminal action '{action}'. Supported actions: execute, list_processes, kill_process, system_info."


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "terminal_control",
    "description": (
        "Full terminal access for command execution, system management, and process control. "
        "Use to execute shell commands (pip, git, python, npm, system diagnostics, network commands, script running), "
        "view running processes, terminate processes, and check system specifications."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action to perform: 'execute' (run command) | 'list_processes' | 'kill_process' | 'system_info'"
            },
            "command": {
                "type": "STRING",
                "description": "Shell command line string to run (e.g. 'git status', 'pip install <pkg>', 'dir', 'python script.py')"
            },
            "working_dir": {
                "type": "STRING",
                "description": "Optional working directory path to run the command in"
            },
            "target": {
                "type": "STRING",
                "description": "Target PID or process name for kill_process or list_processes filter"
            },
            "timeout": {
                "type": "INTEGER",
                "description": "Max timeout in seconds (default 45)"
            }
        },
        "required": ["action"]
    },
    "handler": terminal_control,
}
