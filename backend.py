import datetime as dt
import json
import subprocess
import threading
from pathlib import Path
from typing import Any


class Receiver:
    def __init__(
        self,
        log_file: Path = Path("./log.json"),
        audio_device: str = "plughw:0,0",
        log_interval: float = 1.0,
    ):
        self.audio_device: str = audio_device
        self.rtl_process = None
        self.aplay_process = None
        self.frequency: float | None = None
        self.status = "idle"
        self.log_file: Path = log_file

        self.log_interval = log_interval
        self._lock = threading.Lock()
        self._stop_logging = threading.Event()
        self._log_thread: threading.Thread | None = None

    def start_logging(self) -> None:
        if self._log_thread and self._log_thread.is_alive():
            return

        self._stop_logging.clear()
        self._log_thread = threading.Thread(target=self._log_loop, daemon=True)
        self._log_thread.start()

    def stop_logging(self) -> None:
        self._stop_logging.set()
        if self._log_thread:
            self._log_thread.join()
            self._log_thread = None

    def _log_loop(self) -> None:
        # wait() returns True when the event is set, so this exits promptly
        while not self._stop_logging.wait(self.log_interval):
            self.log()

    def tune(self, frequency):
        self.stop()

        self.frequency = frequency
        print(f"Tuning to {frequency / 1e6:.3f} MHz")

        self.play()

    def play(self) -> None:

        if self.frequency is None:
            print("No frequency set")
            return

        self.status = f"playing"

        self.rtl_process = subprocess.Popen(
            [
                "rtl_fm",
                "-f",
                str(self.frequency),
                "-M",
                "wbfm",
                "-s",
                "200k",
                "-r",
                "48000",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

        self.aplay_process = subprocess.Popen(
            [
                "aplay",
                "-D",
                self.audio_device,
                "-r",
                "48000",
                "-f",
                "S16_LE",
                "-c",
                "1",
            ],
            stdin=self.rtl_process.stdout,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def stop(self) -> None:
        self.status = "idle"

        if self.aplay_process:
            self.aplay_process.terminate()
            self.aplay_process.wait()
            self.aplay_process = None

        if self.rtl_process:
            self.rtl_process.terminate()
            self.rtl_process.wait()
            self.rtl_process.stdout.close()
            self.rtl_process = None

    def print_status(self) -> None:
        match self.status:
            case "idle":
                print("Idle")

            case "playing":
                print(f"Playing, listening on: {self.frequency / 1e6} MHz")

            case _:
                print("Status unknown")

    def log(self) -> None:
        """Writes current state to logfile to be read by UI"""

        state: dict[str, Any] = {
            "last-updated": str(dt.datetime.now()),
            "status": self.status,
            "frequency": self.frequency,
        }

        with self._lock:
            tmp = self.log_file.with_suffix(".tmp")

            with open(tmp, "w") as f:
                json.dump(state, f)

            tmp.replace(self.log_file)


receiver = Receiver()
receiver.start_logging()

# Headless interface
try:
    while True:
        command = input("> ").strip()

        exit_commands = ["quit", "exit"]
        if command in exit_commands:
            break

        elif command.startswith("tune "):
            frequency_input = float(command.split()[1])
            receiver.tune(frequency_input * 1e6)

        elif command == "status":
            receiver.print_status()

        else:
            print(f"Unknown command: {command}")
            print("")
            print("Commands:")
            print("    status")
            print("    tune [freq (MHz)]")
            print("    quit")
            print("")

        # Log after each command so we can update the UI
        receiver.log()

finally:
    receiver.stop_logging()
    receiver.stop()
    receiver.log()
