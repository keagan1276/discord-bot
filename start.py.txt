import os
import subprocess
import sys
import time


def start_process(command):
    return subprocess.Popen(
        command,
        stdout=sys.stdout,
        stderr=sys.stderr
    )


bot_process = start_process([
    sys.executable,
    "bot.py"
])

dashboard_process = start_process([
    sys.executable,
    "dashboard/app.py"
])

try:
    while True:
        if bot_process.poll() is not None:
            raise RuntimeError(
                "The Discord bot process stopped."
            )

        if dashboard_process.poll() is not None:
            raise RuntimeError(
                "The dashboard process stopped."
            )

        time.sleep(2)

except KeyboardInterrupt:
    bot_process.terminate()
    dashboard_process.terminate()