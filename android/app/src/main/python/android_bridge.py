"""Starts and manages the FastAPI backend inside the Android app (Chaquopy)."""
import os
import threading
import time

_server = None
_thread = None


def is_running() -> bool:
    return _thread is not None and _thread.is_alive() and _server is not None and not _server.should_exit


def start_server(api_id, api_hash, data_dir, port=8000):
    global _server, _thread
    os.environ["API_ID"] = str(api_id)
    os.environ["API_HASH"] = str(api_hash)
    # Absolute path => session file lives in the app's private storage
    os.environ["SESSION_NAME"] = os.path.join(data_dir, "telegram_session")

    if _thread is not None and _thread.is_alive():
        if _server is not None and _server.should_exit:
            # Wait briefly for previous server instance to finish shutting down
            for _ in range(30):
                if not _thread.is_alive():
                    break
                time.sleep(0.1)
        if _thread.is_alive():
            import config
            import telegram_service

            new_id = int(api_id)
            new_hash = str(api_hash)
            if config.API_ID != new_id or config.API_HASH != new_hash:
                config.API_ID = new_id
                config.API_HASH = new_hash
                telegram_service.API_ID = new_id
                telegram_service.API_HASH = new_hash
                telegram_service.client = None
            return "already running"

    import uvicorn
    import main

    config = uvicorn.Config(main.app, host="127.0.0.1", port=int(port), log_level="info")
    _server = uvicorn.Server(config)
    _thread = threading.Thread(target=_server.run, daemon=True)
    _thread.start()
    return "started"


def stop_server():
    global _server, _thread
    if _server is not None:
        _server.should_exit = True
    if _thread is not None and _thread.is_alive():
        for _ in range(30):
            if not _thread.is_alive():
                break
            time.sleep(0.1)
    return "stopped"
