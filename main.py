import subprocess

FREQUENCY = 103.8e6  # Hz
AUDIO_DEVICE = "plughw:2,0"


class Receiver:
    def __init__(self, audio_device: str = "plughw:2,0"):
        self.audio_device: str = audio_device
        self.rtl_process = None
        self.aplay_process = None
        self.frequency = None

    def tune(self, frequency):
        self.stop()

        self.frequency = frequency
        print(f"Tuning to {frequency / 1e6:.3f} MHz")

        self.play()


    def play(self) -> None:
        self.rtl = subprocess.Popen(
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
        )

        self.aplay = subprocess.Popen(
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
            stdin=self.rtl.stdout,
        )

    def stop(self) -> None:
        if self.aplay:
            self.aplay.terminate()
            self.aplay.wait()
            self.aplay = None

        if self.rtl:
            self.rtl.terminate()
            self.rtl.wait()
            self.rtl = None


receiver = Receiver()


try:
    receiver.tune(103.8e6)

    input("Press Enter to stop")

finally:
    receiver.stop()
