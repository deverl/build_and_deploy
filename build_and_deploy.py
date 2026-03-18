#!/usr/bin/env python3
"""
build_and_deploy.py

Interactive terminal menu for running build/deploy steps in sequence.
Each step is defined as a dict with optional keys:
  text         - display label (also used as command if no 'command' key)
  command      - shell command to run
  help         - informational note shown in the menu and before running
  input        - string to feed as stdin to the command (e.g. "n\n")
  auto_advance - if true, on success automatically run the next step
  on_error     - array of shell commands to run synchronously when the step fails

Steps with only a 'help' key are display-only (no-op on Enter).
"""

import argparse
import json
import os
import pty
import select
import shutil
import subprocess
import sys
import termios
import tty

# ─────────────────────────────────────────────
# Terminal helpers
# ─────────────────────────────────────────────

# ANSI codes
RESET      = "\033[0m"
REVERSE    = "\033[7m"       # highlighted row
DIM        = "\033[2m"
BOLD       = "\033[1m"
YELLOW     = "\033[33m"
GREEN      = "\033[32m"
RED        = "\033[31m"
CYAN       = "\033[36m"

TERM_WIDTH = shutil.get_terminal_size((80, 24)).columns


def clear():
    print("\033[2J\033[H", end="", flush=True)


def read_key() -> str:
    """Read a single keypress (including escape sequences) from stdin."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = os.read(fd, 1).decode("latin-1")
        if ch == "\x1b":
            # Read the next two bytes of the escape sequence directly.
            # They arrive immediately after the escape byte, so no timeout needed.
            try:
                ch += os.read(fd, 1).decode("latin-1")
                ch += os.read(fd, 1).decode("latin-1")
            except OSError:
                pass
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


# ─────────────────────────────────────────────
# Menu rendering
# ─────────────────────────────────────────────

def _step_display_text(step: dict) -> str:
    """Return the label text shown in the menu for a step."""
    return step.get("text", "")


def _step_help_text(step: dict) -> str:
    return step.get("help", "")


def _is_noop(step: dict) -> bool:
    """True for steps that are display/comment only (no text key)."""
    return "text" not in step


def draw_menu(steps: list, selected: int, mode_label: str) -> None:
    clear()
    header = f"[ {mode_label} ]  ↑/↓ to move, ENTER to run, q to quit"
    print(f"{BOLD}{header}{RESET}")
    print()

    for i, step in enumerate(steps):
        label   = _step_display_text(step)
        help_   = _step_help_text(step)
        is_noop = _is_noop(step)
        is_sel  = (i == selected)

        if is_noop:
            # Comment/notice line – always dimmed, never selectable
            note = f"  ─── {help_} ───"
            print(f"{DIM}{YELLOW}{note}{RESET}")
            continue

        # Build display row
        row_label = f"  {label}"
        suffix    = f"  {DIM}({help_}){RESET}" if help_ else ""

        if is_sel:
            # Pad to terminal width so the highlight bar stretches across
            print(f"{REVERSE}{row_label}{RESET}{suffix}", end="")
            print()
        else:
            print(f"{row_label}{suffix}")

    print()


# ─────────────────────────────────────────────
# Command execution
# ─────────────────────────────────────────────

def run_command(step: dict) -> int:
    """
    Run the command for a step, streaming output live.
    Returns the exit code.
    """
    text    = step.get("text", "")
    command = step.get("command", text)
    stdin_  = step.get("input")       # optional string fed to stdin
    help_   = step.get("help", "")

    if help_:
        print(f"\n{YELLOW}ℹ  {help_}{RESET}\n")

    print(f"{BOLD}>>> {command}{RESET}")
    print("─" * min(TERM_WIDTH, 72))

    if stdin_ is not None:
        # Feed preset input; use PIPE for stdin
        result = subprocess.run(
            command,
            shell=True,
            executable="/bin/bash",
            input=stdin_.encode(),
        )
        exit_code = result.returncode
    else:
        # Stream output live via a PTY so programs that check isatty() behave normally
        exit_code = _run_with_pty(command)

    print("─" * min(TERM_WIDTH, 72))
    return exit_code


def _run_with_pty(command: str) -> int:
    """Run command in a pseudo-terminal so interactive output works correctly."""
    pid, master_fd = pty.fork()

    if pid == 0:
        # Child
        os.execvp("/bin/bash", ["/bin/bash", "-c", command])
        sys.exit(1)

    # Parent: relay output from child PTY to stdout
    try:
        while True:
            try:
                rlist, _, _ = select.select([master_fd], [], [], 0.1)
            except (ValueError, OSError):
                break
            if rlist:
                try:
                    data = os.read(master_fd, 4096)
                except OSError:
                    break
                if not data:
                    break
                sys.stdout.buffer.write(data)
                sys.stdout.buffer.flush()
    finally:
        os.close(master_fd)

    _, status = os.waitpid(pid, 0)
    return os.waitstatus_to_exitcode(status)


# ─────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────

def next_runnable(steps: list, current: int) -> int:
    """Return the index of the next step that isn't a noop, wrapping if needed."""
    n = len(steps)
    idx = current + 1
    while idx < n and _is_noop(steps[idx]):
        idx += 1
    return idx if idx < n else current


def run_menu(steps: list, mode_label: str) -> None:
    selected = 0
    # Advance past any leading noop steps
    while selected < len(steps) and _is_noop(steps[selected]):
        selected += 1

    while True:
        draw_menu(steps, selected, mode_label)

        key = read_key()

        # Navigation
        if key in ("\x1b[A", "\x1b[D"):   # Up / Left
            new = selected - 1
            while new >= 0 and _is_noop(steps[new]):
                new -= 1
            if new < 0:
                # Wrap: find the last selectable step
                new = len(steps) - 1
                while new > selected and _is_noop(steps[new]):
                    new -= 1
            selected = new

        elif key in ("\x1b[B", "\x1b[C"):  # Down / Right
            new = selected + 1
            while new < len(steps) and _is_noop(steps[new]):
                new += 1
            if new >= len(steps):
                # Wrap: find the first selectable step
                new = 0
                while new < selected and _is_noop(steps[new]):
                    new += 1
            selected = new

        elif key in ("q", "Q", "\x03"):    # q / Ctrl-C
            clear()
            sys.exit(0)

        elif key in ("\r", "\n", ""):       # Enter
            step = steps[selected]

            if _is_noop(step):
                continue

            label = step.get("text", "")

            if label == "-- quit --":
                clear()
                sys.exit(0)

            # Run the step (and possibly more if auto_advance)
            while True:
                step = steps[selected]
                clear()
                exit_code = run_command(step)

                if exit_code != 0:
                    on_error = step.get("on_error")
                    if on_error and isinstance(on_error, list):
                        print(f"\n{YELLOW}Running on_error commands…{RESET}\n")
                        for cmd in on_error:
                            if isinstance(cmd, str):
                                run_command({"command": cmd})
                        print()
                    print(f"\n{RED}⚠  Step exited with code {exit_code}.{RESET}  "
                          "Press any key to return to menu…")
                    read_key()
                    break

                advanced = next_runnable(steps, selected)
                if advanced == selected:
                    print(f"\n{GREEN}✓  Step complete.{RESET}  "
                          "Press any key to continue to the next step…")
                    read_key()
                    break

                selected = advanced  # Always select next item on success
                if not step.get("auto_advance"):
                    print(f"\n{GREEN}✓  Step complete.{RESET}  "
                          "Press any key to continue to the next step…")
                    read_key()
                    break

                next_step = steps[selected]
                if next_step.get("text") == "-- quit --":
                    clear()
                    sys.exit(0)
                # Loop to run the next step


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

def load_steps() -> tuple:
    """
    Load step lists from build_and_deploy.json in the same directory
    as this script. Exits with code 1 if the file is missing or invalid.
    Returns (vanguard_dir, steps_full, steps_backend).
    """
    json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "build_and_deploy.json")
    if not os.path.exists(json_path):
        print(f"ERROR: Steps file not found: {json_path}", file=sys.stderr)
        sys.exit(1)
    try:
        with open(json_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"ERROR: Could not read {json_path}: {e}", file=sys.stderr)
        sys.exit(1)
    steps_data = data.get("steps")
    if not steps_data or not isinstance(steps_data, dict):
        print(f"ERROR: {json_path} must contain a \"steps\" object.", file=sys.stderr)
        sys.exit(1)

    dirs = data.get("dirs")
    if not dirs or not isinstance(dirs, dict):
        print(f'ERROR: {json_path} must contain a "dirs" object.', file=sys.stderr)
        sys.exit(1)
    vanguard_dir = dirs.get("vanguard")
    if not vanguard_dir or not isinstance(vanguard_dir, str):
        print(f'ERROR: {json_path} "dirs" must contain a "vanguard" string.',
              file=sys.stderr)
        sys.exit(1)

    full = steps_data.get("full")
    backend = steps_data.get("backend")
    if not full or not backend:
        print(f"ERROR: {json_path} \"steps\" must contain \"full\" and \"backend\" arrays.",
              file=sys.stderr)
        sys.exit(1)
    return vanguard_dir, full, backend


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Interactive build-and-deploy menu."
    )
    parser.add_argument(
        "-b", "--backend-only",
        action="store_true",
        help="Use backend-only step list",
    )
    args = parser.parse_args()

    vanguard_dir, steps_full, steps_backend = load_steps()

    # Compare resolved paths so symlinks don't trip the check.
    cwd_real = os.path.realpath(os.getcwd())
    vanguard_real = os.path.realpath(vanguard_dir)
    if cwd_real != vanguard_real:
        print(f"ERROR: You must be in the {vanguard_real} directory to use this script.")
        sys.exit(1)

    if args.backend_only:
        run_menu(steps_backend, "BACKEND ONLY")
    else:
        run_menu(steps_full, "FULL DEPLOY")


if __name__ == "__main__":
    main()
