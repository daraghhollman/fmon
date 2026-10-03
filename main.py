import subprocess

class Receiver:
    def __init__(self, audio_device: str = "plughw:0,0"):
        self.audio_device: str = audio_device
        self.rtl_process = None
        self.aplay_process = None
        self.frequency: float | None = None
        self.status = "Idle"

    def tune(self, frequency):
        self.stop()

        self.frequency = frequency
        print(f"Tuning to {frequency / 1e6:.3f} MHz")

        self.play()


    def play(self) -> None:

        if self.frequency is None:
            print("No frequency set")
            return

        self.status = f"Playing, listening on: {self.frequency / 1e6:.3f} MHz"

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
        self.status = "Idle"

        if self.aplay_process:
            self.aplay_process.terminate()
            self.aplay_process.wait()
            self.aplay_process = None

        if self.rtl_process:
            self.rtl_process.terminate()
            self.rtl_process.wait()
            self.rtl_process.stdout.close()
            self.rtl_process = None


receiver = Receiver()


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
            print(receiver.status)

        else:
            print(f"Unknown command: {command}")
            print("")
            print("Commands:")
            print("    status")
            print("    tune [freq (MHz)]")
            print("    quit")
            print("")

finally:
    receiver.stop()
