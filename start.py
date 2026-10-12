
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "backend")
    env["DEBATECHECK_API_URL"] = "http://127.0.0.1:8002"

    port = os.getenv("PORT", "8501")

    backend = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "app.api.main:app",
            "--host", "127.0.0.1",
            "--port", "8002",
        ],
        cwd=ROOT / "backend",
        env=env,
    )

    try:
        time.sleep(2)

        if backend.poll() is not None:
            raise RuntimeError("Backend failed to start.")

        frontend = subprocess.Popen(
            [
                sys.executable, "-m", "streamlit",
                "run", "frontend/app.py",
                "--server.address", "0.0.0.0",
                "--server.port", port,
                "--server.headless", "true",
            ],
            cwd=ROOT,
            env=env,
        )

        try:
            frontend.wait()
        finally:
            if frontend.poll() is None:
                frontend.terminate()

    finally:
        if backend.poll() is None:
            backend.terminate()
            try:
                backend.wait(timeout=5)
            except subprocess.TimeoutExpired:
                backend.kill()


if __name__ == "__main__":
    main()

