"""
Smell-Reg - Fragrance Regulatory Compliance
Native desktop application launcher using pywebview
"""
import sys
import subprocess
import threading
import time
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

import webview


def start_streamlit():
    """Start Streamlit server in background."""
    subprocess.run(
        [
            sys.executable, "-m", "streamlit", "run",
            str(PROJECT_ROOT / "ui" / "app.py"),
            "--server.port", "8501",
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false",
        ],
        cwd=str(PROJECT_ROOT),
    )


def main():
    # Start Streamlit in background thread
    server_thread = threading.Thread(target=start_streamlit, daemon=True)
    server_thread.start()

    # Wait for Streamlit to start (it takes a bit longer)
    time.sleep(3)

    # Create native window
    window = webview.create_window(
        title="Smell-Reg - Regulatory Compliance",
        url="http://127.0.0.1:8501",
        width=1400,
        height=900,
        resizable=True,
        min_size=(1000, 700),
    )

    # Start webview (blocks until window is closed)
    webview.start()


if __name__ == "__main__":
    main()
