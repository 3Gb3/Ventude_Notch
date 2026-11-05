from __future__ import annotations

import os
import platform
import shutil
from datetime import datetime
from typing import Any

from ventude.assistant.tools.base import Tool, obj


def system_info(_args: dict[str, Any]) -> Any:
    """Informações seguras: sem usuário, rede, processos ou variáveis de ambiente."""
    total, _used, free = shutil.disk_usage(os.path.expanduser("~"))
    return {
        "os": f"{platform.system()} {platform.release()}",
        "version": platform.version(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "python": platform.python_version(),
        "disk_total_gb": round(total / 1e9, 1),
        "disk_free_gb": round(free / 1e9, 1),
        "local_time": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def system_tools() -> list[Tool]:
    return [Tool("system_info", "Informações básicas e seguras do sistema.", obj({}), system_info)]
