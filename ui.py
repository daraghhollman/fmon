from __future__ import annotations

import argparse
import curses
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------
# Tunables
# --------------------------------------------------------------------------
ROW_ASPECT = 0.75   # block height relative to block width (terminal cells are ~2x taller than wide)
MAX_SCALE = 14      # cap on horizontal block size
CORE_KEYS = {"status", "frequency", "last-updated"}

# --------------------------------------------------------------------------
# 5x7 block font. '#' = filled pixel. Glyphs may differ in width.
# --------------------------------------------------------------------------
GLYPH_H = 7
GLYPHS: dict[str, list[str]] = {
    "0": [" ### ", "#   #", "#  ##", "# # #", "##  #", "#   #", " ### "],
    "1": ["  #  ", " ##  ", "  #  ", "  #  ", "  #  ", "  #  ", " ### "],
    "2": [" ### ", "#   #", "    #", "   # ", "  #  ", " #   ", "#####"],
    "3": [" ### ", "#   #", "    #", "  ## ", "    #", "#   #", " ### "],
    "4": ["   # ", "  ## ", " # # ", "#  # ", "#####", "   # ", "   # "],
    "5": ["#####", "#    ", "#### ", "    #", "    #", "#   #", " ### "],
    "6": [" ### ", "#    ", "#    ", "#### ", "#   #", "#   #", " ### "],
    "7": ["#####", "    #", "   # ", "  #  ", " #   ", " #   ", " #   "],
    "8": [" ### ", "#   #", "#   #", " ### ", "#   #", "#   #", " ### "],
    "9": [" ### ", "#   #", "#   #", " ####", "    #", "    #", " ### "],
    ".": ["  ", "  ", "  ", "  ", "  ", "##", "##"],
    "-": ["     ", "     ", "     ", "#####", "     ", "     ", "     "],
    "G": [" ### ", "#   #", "#    ", "# ###", "#   #", "#   #", " ### "],
    "M": ["#   #", "## ##", "# # #", "# # #", "#   #", "#   #", "#   #"],
    "H": ["#   #", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"],
    "k": ["#   #", "#  # ", "# #  ", "##   ", "# #  ", "#  # ", "#   #"],
    "z": ["     ", "     ", "#####", "   # ", "  #  ", " #   ", "#####"],
}

# Colour pair ids
C_GREEN, C_YELLOW, C_RED, C_CYAN, C_WHITE = 1, 2, 3, 4, 5
STATUS_COLORS = {
    "running": C_GREEN,
    "scanning": C_GREEN,
    "idle": C_YELLOW,
    "stopped": C_RED,
    "error": C_RED,
}


# --------------------------------------------------------------------------
# State handling
# --------------------------------------------------------------------------
def read_state(path: Path) -> dict[str, Any] | None:
    """Parsed state, or None if unreadable (missing / caught mid-write)."""
    try:
        with open(path) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def poll(path: Path, state, last_sig):
    """Re-read the file only when mtime/size changed. Returns (state, sig)."""
    try:
        st = path.stat()
    except OSError:
        return None, None  # file missing
    sig = (st.st_mtime_ns, st.st_size)
    if sig != last_sig:
        new = read_state(path)
        if new is not None:  # a failed read keeps old state and retries next tick
            return new, sig
    return state, last_sig


def age_seconds(state: dict[str, Any]) -> float | None:
    try:
        ts = dt.datetime.fromisoformat(state["last-updated"])
        return (dt.datetime.now() - ts).total_seconds()
    except (KeyError, ValueError, TypeError):
        return None


def split_frequency(value: Any) -> tuple[str, str]:
    """Frequency in Hz -> (digits, unit)."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return "---", ""
    for scale, fmt, unit in ((1e9, "{:.4f}", "GHz"), (1e6, "{:.3f}", "MHz"), (1e3, "{:.1f}", "kHz")):
        if abs(value) >= scale:
            return fmt.format(value / scale), unit
    return f"{value:.0f}", "Hz"


# --------------------------------------------------------------------------
# Drawing helpers
# --------------------------------------------------------------------------
def put(scr, y: int, x: int, text: str, attr: int = 0) -> None:
    """addstr that clips to the screen and never raises."""
    h, w = scr.getmaxyx()
    if not (0 <= y < h) or x >= w:
        return
    if x < 0:
        text, x = text[-x:], 0
    text = text[: w - x]
    if text:
        try:
            scr.addstr(y, x, text, attr)
        except curses.error:
            pass


def put_centered(scr, y: int, text: str, attr: int = 0) -> None:
    _, w = scr.getmaxyx()
    put(scr, y, max(0, (w - len(text)) // 2), text, attr)


def big_rows(text: str) -> list[str]:
    glyphs = [GLYPHS.get(ch, GLYPHS["-"]) for ch in text]
    return [" ".join(g[r] for g in glyphs) for r in range(GLYPH_H)]


def big_width(text: str) -> int:
    return len(big_rows(text)[0])


def draw_big(scr, y: int, text: str, sx: int, sy: int, attr: int) -> None:
    """Draw `text` in block font, horizontally centred, top at row y."""
    _, w = scr.getmaxyx()
    rows = big_rows(text)
    x0 = max(0, (w - len(rows[0]) * sx) // 2)
    for r, line in enumerate(rows):
        for m in re.finditer(r"#+", line):
            x = x0 + m.start() * sx
            run = " " * ((m.end() - m.start()) * sx)
            for k in range(sy):
                put(scr, y + r * sy + k, x, run, attr | curses.A_REVERSE)


def init_colors() -> None:
    curses.start_color()
    try:
        curses.use_default_colors()
        bg = -1
    except curses.error:
        bg = curses.COLOR_BLACK
    for pid, c in (
        (C_GREEN, curses.COLOR_GREEN),
        (C_YELLOW, curses.COLOR_YELLOW),
        (C_RED, curses.COLOR_RED),
        (C_CYAN, curses.COLOR_CYAN),
        (C_WHITE, curses.COLOR_WHITE),
    ):
        curses.init_pair(pid, c, bg)


def col(pid: int) -> int:
    return curses.color_pair(pid)


# --------------------------------------------------------------------------
# Screen
# --------------------------------------------------------------------------
def draw(scr, state: dict[str, Any] | None, path: Path, stale_after: float) -> None:
    scr.erase()
    h, w = scr.getmaxyx()

    if h < 16 or w < 24:
        put(scr, 0, 0, "Terminal too small", col(C_YELLOW))
        scr.refresh()
        return

    put_centered(scr, 0, "RTL-SDR", col(C_WHITE) | curses.A_BOLD)

    if state is None:
        put_centered(scr, h // 2, "Waiting for log file...", col(C_YELLOW) | curses.A_BOLD)
        put_centered(scr, h // 2 + 1, str(path), col(C_WHITE) | curses.A_DIM)
        scr.refresh()
        return

    age = age_seconds(state)
    stale = age is not None and age > stale_after

    # ---- status banner (rows 2-4) ----------------------------------------
    status = str(state.get("status", "unknown"))
    s_col = C_RED if stale else STATUS_COLORS.get(status.lower(), C_CYAN)
    banner = col(s_col) | curses.A_REVERSE
    for r in (2, 3, 4):
        put(scr, r, 1, " " * (w - 2), banner)
    put_centered(scr, 3, status.upper(), banner | curses.A_BOLD)

    # ---- frequency (centre of screen) ---------------------------------------
    digits, unit = split_frequency(state.get("frequency"))
    sx = max(1, min(MAX_SCALE, (w - 2) // big_width(digits)))
    sy = max(1, min(max(7, h // 3) // GLYPH_H, round(sx * ROW_ASPECT)))
    su_x, su_y = max(1, sx // 2), max(1, sy // 2)

    freq_h = GLYPH_H * sy
    unit_h = GLYPH_H * su_y if unit else 0
    block_h = freq_h + (1 + unit_h if unit else 0)
    y0 = max(6, (h - block_h) // 2)

    f_col = col(C_RED if stale else C_CYAN) | curses.A_BOLD
    draw_big(scr, y0, digits, sx, sy, f_col)
    if unit:
        draw_big(scr, y0 + freq_h + 1, unit, su_x, su_y, col(C_WHITE))

    # ---- extra keys below the frequency -------------------------------------
    y = y0 + block_h + 2
    for key, value in state.items():
        if key in CORE_KEYS or y >= h - 3:
            continue
        label = key.replace("-", " ").capitalize()
        put_centered(scr, y, f"{label}: {value}", col(C_WHITE))
        y += 1

    # ---- footer -------------------------------------------------------------
    if age is None:
        put_centered(scr, h - 2, f"Updated: {state.get('last-updated', '-')}", col(C_WHITE))
    elif stale:
        put_centered(scr, h - 2, f"STALE - no update for {age:.0f}s", col(C_RED) | curses.A_BOLD)
    else:
        put_centered(scr, h - 2, f"Updated {age:.1f}s ago", col(C_GREEN))
    put_centered(scr, h - 1, f"{path.name}  |  q to quit", col(C_WHITE) | curses.A_DIM)

    scr.refresh()


def run(scr, args: argparse.Namespace) -> None:
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    init_colors()
    scr.timeout(int(args.interval * 1000))  # getch() doubles as our frame timer

    state, sig = None, None
    while True:
        state, sig = poll(args.log_file, state, sig)
        draw(scr, state, args.log_file, args.stale_after)
        if scr.getch() in (ord("q"), ord("Q"), 27):
            return


def main() -> None:
    p = argparse.ArgumentParser(description="Watch an rtlsdr backend state file.")
    p.add_argument("log_file", type=Path, help="JSON file written by the backend")
    p.add_argument("--interval", type=float, default=0.1, help="refresh/poll interval (s)")
    p.add_argument("--stale-after", type=float, default=5.0, help="seconds before data is flagged stale")
    args = p.parse_args()
    try:
        curses.wrapper(run, args)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
