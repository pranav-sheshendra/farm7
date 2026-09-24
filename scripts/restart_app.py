"""Restart only this workspace's web server, preserving notebook and Ollama."""
from pathlib import Path
import psutil

root = Path(__file__).resolve().parents[1]
for process in psutil.process_iter(['pid', 'cmdline']):
    args = process.info['cmdline'] or []
    if len(args) == 2 and args[1] in {'app.py', 'serve.py'} and str(root).lower() in args[0].lower():
        try:
            for child in process.children(recursive=True):
                child.terminate()
            process.terminate()
        except psutil.NoSuchProcess:
            pass
