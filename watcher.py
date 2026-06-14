import subprocess
import time
import logging
import sys
import os
import json
import httpx
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(message)s"
)
log = logging.getLogger(__name__)

POLL_INTERVAL      = 30
TUNNEL_CHECK       = 300
APP_PROCESS        = None
NGROK_PROCESS      = None
NGROK_DOMAIN       = os.getenv("DOMAIN", "").replace("https://", "").replace("http://", "")
STATE_FILE         = "runtime_state.json"
_last_tunnel_check = 0


def get_local_commit():
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True
    )
    return result.stdout.strip()


def get_remote_commit():
    subprocess.run(["git", "fetch", "origin", "main"], capture_output=True)
    result = subprocess.run(
        ["git", "rev-parse", "origin/main"],
        capture_output=True, text=True
    )
    return result.stdout.strip()


def pull_latest():
    subprocess.run(["git", "pull", "origin", "main"])
    log.info("Pulled latest code")


def install_requirements():
    log.info("Installing requirements...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "-q"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        log.info("Requirements installed")
    else:
        log.error(f"Requirements install failed:\n{result.stderr}")


def _mark_crash_in_state():
    try:
        state = {}
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
        state["crash_detected"] = True
        state["last_shutdown"]  = "crash"
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp, STATE_FILE)
        log.warning("Crash marked in runtime_state.json")
    except Exception as e:
        log.error(f"Could not mark crash: {e}")


def _get_last_mode() -> str:
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
            return state.get("trading_mode", "paper")
    except Exception:
        pass
    return "paper"


def start_ngrok():
    global NGROK_PROCESS
    log.info("Starting ngrok tunnel...")
    NGROK_PROCESS = subprocess.Popen(
        ["ngrok", "http", f"--domain={NGROK_DOMAIN}", "8000"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(3)
    log.info(f"Tunnel live: https://{NGROK_DOMAIN}")


def stop_ngrok():
    global NGROK_PROCESS
    if NGROK_PROCESS:
        NGROK_PROCESS.terminate()
        NGROK_PROCESS.wait()
        log.info("Ngrok stopped")


def restart_ngrok():
    log.warning("Restarting ngrok tunnel...")
    stop_ngrok()
    time.sleep(2)
    start_ngrok()


def check_tunnel_health() -> bool:
    if not NGROK_DOMAIN:
        return True
    try:
        r = httpx.get(f"https://{NGROK_DOMAIN}/api/health", timeout=10)
        return r.status_code == 200
    except Exception as e:
        log.warning(f"Tunnel health check failed: {e}")
        return False


def start_app():
    global APP_PROCESS
    log.info("Starting app...")
    APP_PROCESS = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app",
         "--host", "0.0.0.0",
         "--port", "8000",
         "--log-level", "info"],
        cwd=os.path.dirname(os.path.abspath(__file__))
    )
    log.info(f"App started — PID:{APP_PROCESS.pid}")


def stop_app():
    global APP_PROCESS
    if APP_PROCESS:
        APP_PROCESS.terminate()
        try:
            APP_PROCESS.wait(timeout=15)
        except subprocess.TimeoutExpired:
            APP_PROCESS.kill()
            APP_PROCESS.wait()
        log.info("App stopped")


def _app_crashed() -> bool:
    if APP_PROCESS is None:
        return False
    return APP_PROCESS.poll() is not None


def main():
    global _last_tunnel_check

    log.info("Watcher started")
    start_ngrok()
    install_requirements()
    start_app()

    _last_tunnel_check = time.time()

    while True:
        time.sleep(POLL_INTERVAL)
        now = time.time()

        if _app_crashed():
            exit_code = APP_PROCESS.returncode
            log.error(f"App crashed with exit code {exit_code} — marking crash and restarting")
            _mark_crash_in_state()
            time.sleep(3)
            install_requirements()
            start_app()
            _last_tunnel_check = now
            continue

        try:
            local  = get_local_commit()
            remote = get_remote_commit()

            if local != remote:
                log.info("New commit — updating...")
                stop_app()
                pull_latest()
                install_requirements()
                start_app()
            else:
                log.info("No changes")

        except Exception as e:
            log.error(f"Watcher error: {e}")

        if now - _last_tunnel_check >= TUNNEL_CHECK:
            _last_tunnel_check = now
            try:
                if not check_tunnel_health():
                    log.warning("Tunnel unreachable — restarting ngrok")
                    restart_ngrok()
                    time.sleep(5)
                    if check_tunnel_health():
                        log.info("Tunnel restored")
                    else:
                        log.error("Tunnel still down after restart")
                else:
                    log.info("Tunnel healthy")
            except Exception as e:
                log.error(f"Tunnel check error: {e}")


if __name__ == "__main__":
    main()