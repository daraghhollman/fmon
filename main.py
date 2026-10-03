import subprocess

FREQUENCY = 103.8e6  # Hz
AUDIO_DEVICE = "plughw:2,0"


def start_radio(frequency):

    command = [
        "rtl_fm",
        "-f",
        str(frequency),
        "-M",
        "wbfm",
        "-s",
        "200k",
        "-r",
        "48000",
    ]

    rtl = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
    )

    aplay = subprocess.Popen(
        [
            "aplay",
            "-D",
            AUDIO_DEVICE,
            "-r",
            "48000",
            "-f",
            "S16_LE",
            "-c",
            "1",
        ],
        stdin=rtl.stdout,
    )

    return rtl, aplay

def stop_radio(rtl, aplay):
    aplay.terminate()
    rtl.terminate()

    aplay.wait()
    rtl.wait()


if __name__ == "__main__":
    print(f"Tuning to {FREQUENCY / 1e6:.3f} MHz")

    rtl, aplay = start_radio((FREQUENCY))

    try:
        aplay.wait()

    except KeyboardInterrupt:
        print("\nStopping radio...")
        stop_radio(rtl, aplay)
