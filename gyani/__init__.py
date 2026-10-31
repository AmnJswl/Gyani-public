"""
gyani v2 — Ultra-lightweight personal AI assistant.
Python port of PicoClaw by Sipeed.
"""

__version__ = "2.0.0"
__author__  = "Vivek"

LOGO = "🦞"

from gyani.config  import load_config, save_config, get_active_provider, workspace_path
from gyani.agent   import AgentLoop, HeartbeatService, CronService
from gyani.session import SessionManager

__all__ = [
    "LOGO", "__version__",
    "load_config", "save_config", "get_active_provider", "workspace_path",
    "AgentLoop", "HeartbeatService", "CronService",
    "SessionManager",
]
