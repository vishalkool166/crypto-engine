import subprocess
import time
import logging
import sys
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(message)s"
)
log = logging.getLogger(__name__)

POLL_INTERVAL = 30
APP_PROCESS   = None
NGROK_PROCESS = None
NGROK_DOMAIN  = "small-salaried-study.ngrok-free.dev"

def get_local_commit():
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True
    )
    return result.stdout.strip()

def get_remote_commit():
    subprocess.run(
        ["git", "fetch", "origin", "main"],
        capture_output=True
    )
    result = subprocess.run(
        ["git", "rev-parse", "origin/main"],
        capture_output=True, text=True
    )
    return result.stdout.strip()

def pull_latest():
    subprocess.run(["git", "pull", "origin", "main"])
    log.info("Pulled latest code")

def start_ngrok():
    global NGROK_PROCESS
    log.info("Starting ngrok tunnel...")
    NGROK_PROCESS = subprocess.Popen(
        ["ngrok", "http",
         f"--domain={NGROK_DOMAIN}",
         "8000"],
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

def start_app():
    global APP_PROCESS
    log.info("Starting app...")
    APP_PROCESS = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=os.path.dirname(os.path.abspath(__file__))
    )
    log.info(f"App started — PID:{APP_PROCESS.pid}")

def stop_app():
    global APP_PROCESS
    if APP_PROCESS:
        APP_PROCESS.terminate()
        APP_PROCESS.wait()
        log.info("App stopped")

def main():
    log.info("Watcher started")
    start_ngrok()
    start_app()

    while True:
        time.sleep(POLL_INTERVAL)
        try:
            local  = get_local_commit()
            remote = get_remote_commit()

            if local != remote:
                log.info("New commit — updating...")
                stop_app()
                pull_latest()
                start_app()
            else:
                log.info("No changes")

        except Exception as e:
            log.error(f"Watcher error: {e}")

if __name__ == "__main__":
    main()