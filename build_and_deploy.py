#!/usr/bin/env python3
"""
build_and_deploy.py

Interactive terminal menu for running build/deploy steps in sequence.
Each step is defined as a dict with optional keys:
  text         - display label (also used as command if no 'command' key)
  command      - shell command to run
  help         - informational note shown in the menu and before running
  input        - optional string fed to the subprocess stdin (UTF-8). Use embedded
                 newlines for multiple prompts (e.g. ``"y\\n"``). If omitted, the
                 command inherits this process's stdin/stdout/stderr.
  auto_advance - if true, on success automatically run the next step
  on_error     - array of shell commands to run synchronously when the step fails

Any other key whose name starts with ``comment`` (e.g. ``comment``, ``comment_note``,
``comment1``, ``comment2``, etc.) is ignored; use those for documentation in the JSON only.

Placeholders ``{{NAME}}`` in text, command, help, and input are replaced using
the module-level ``variable_definitions`` map (e.g. {{PID}}, {{DATE}}, {{TIME}}).

Steps without a 'text' key are display-only section lines (usually just 'help');
they are skipped by navigation and cannot be run.
"""

import argparse
import json
import logging
import logging.handlers
import os
import pwd
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import termios
import tty
from collections.abc import Callable
from datetime import datetime

# Linux: rsyslog (etc.) exposes /dev/log. macOS syslogd uses /var/run/syslog.
_SYSLOG_SOCKET = '/var/run/syslog' if sys.platform == 'darwin' else '/dev/log'

try:
    _handler: logging.Handler = logging.handlers.SysLogHandler(address=_SYSLOG_SOCKET)
    _handler.setFormatter(logging.Formatter('%(name)s: %(message)s'))
except OSError as exc:
    raise SystemExit(f'Fatal: cannot open syslog socket {_SYSLOG_SOCKET}: {exc}') from exc
log = logging.getLogger('build_and_deploy')
log.addHandler(_handler)
log.setLevel(logging.INFO)

# The value to be used in {{TMPDIR}} substitutions (set in main() after mkdtemp).
temporary_directory: str | None = None

# Values may be literal strings or zero-argument callables returning a string (evaluated when used).
VariableDefinitions = dict[str, str | Callable[[], str]]

variable_definitions: VariableDefinitions = {
    'PID': lambda: str(os.getpid()),
    'DATE': lambda: datetime.now().strftime('%Y-%m-%d'),
    'TIME': lambda: datetime.now().strftime('%H:%M:%S'),
    'TMPDIR': lambda: temporary_directory if temporary_directory is not None else '/tmp',
}

_VAR_PATTERN = re.compile(r'\{\{([A-Za-z0-9_]+)\}\}')

# Build session context shared with the signal handler (populated in Menu.run_menu).
_session_context: dict = {}


def normalize_step_name(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9]+', '_', text)
    text = re.sub(r'_+', '_', text)
    return text.strip('_')


def _get_username() -> str:
    try:
        return pwd.getpwuid(os.getuid()).pw_name
    except (KeyError, AttributeError):
        return str(os.getuid())


_KV_LOG_FIELD_ORDER = (
    'pid',
    'event',
    'exit_code',
    'step_name',
    'step_num',
    'deploy_type',
    'build_name',
    'build_directory',
    'user',
)

# Visible placeholders for named control characters; everything else gets <CTRL>.
_CTRL_PLACEHOLDERS: dict[str, str] = {
    '\x00': '<NUL>',
    '\t': '<TAB>',
    '\n': '<NL>',
    '\r': '<CR>',
    '\x0b': '<VT>',
    '\x0c': '<FF>',
}
_CTRL_RE = re.compile(r'[\x00-\x1f\x7f]')


def _replace_ctrl(m: re.Match) -> str:
    return _CTRL_PLACEHOLDERS.get(m.group(0), '<CTRL>')


def _sanitize_log_value(sval: str) -> str:
    """Sanitize a string value for k=v syslog output.

    Applied in strict order:
    1. Control chars (0x00-0x1f, 0x7f) → visible placeholder.  Named chars get
       descriptive tags (<NL>, <TAB>, etc.); others get <CTRL>.  Embedded
       newlines are the most dangerous vector: they would split a single syslog
       event across multiple lines, letting an attacker inject fake log entries.
    2. Remaining whitespace (plain space, Unicode whitespace) → '_'.  After
       step 1 only non-control whitespace can remain.  Eliminating it ensures
       the awk-based report parser (which splits on spaces) always sees each
       key=value pair as a single token, closing the log-injection path.
    3. Backslash → '\\\\' (must precede quote escaping to avoid double-escaping).
    4. Double-quote → '\\"' (for humanlog / hl compatibility).

    Integer values bypass this function entirely (see make_kv_log).
    """
    sval = _CTRL_RE.sub(_replace_ctrl, sval)  # step 1: control chars → placeholders
    sval = re.sub(r'\s', '_', sval)  # step 2: remaining whitespace → _
    sval = sval.replace('\\', '\\\\')  # step 3: backslash
    sval = sval.replace('"', '\\"')  # step 4: double-quote
    return sval


def make_kv_log(prefix: str, **fields: object) -> str:
    priority = {key: i for i, key in enumerate(_KV_LOG_FIELD_ORDER)}
    ordered = sorted(
        fields.items(), key=lambda kv: (priority.get(kv[0], len(_KV_LOG_FIELD_ORDER)), kv[0])
    )
    parts = [prefix]
    for key, value in ordered:
        if value is None:
            continue
        if isinstance(value, int):
            parts.append(f'{key}={value}')
        else:
            parts.append(f'{key}={_sanitize_log_value(str(value))}')
    return ' '.join(parts)


# ─────────────────────────────────────────────
# Terminal helpers
# ─────────────────────────────────────────────


class Style:
    """ANSI SGR escape codes for styled terminal output."""

    # fmt: off
    RESET   = "\033[0m"
    REVERSE = "\033[7m"  # highlighted row
    DIM     = "\033[2m"
    BOLD    = "\033[1m"
    YELLOW  = "\033[33m"
    GREEN   = "\033[32m"
    RED     = "\033[31m"
    CYAN    = "\033[36m"
    # fmt: on


def get_term_width() -> int:
    """Return current terminal width (re-queried on each call to handle resizes)."""
    return shutil.get_terminal_size((80, 24)).columns


class Screen:
    """Terminal screen buffer and clear helpers."""

    @staticmethod
    def enter_alternate() -> None:
        """Use the terminal alternate buffer so the previous screen restores on exit."""
        print('\033[?1049h', end='', flush=True)

    @staticmethod
    def leave_alternate() -> None:
        """Return to the main screen buffer (undo enter_alternate)."""
        print('\033[?1049l', end='', flush=True)

    @staticmethod
    def clear() -> None:
        print('\033[2J\033[H', end='', flush=True)


class Keyboard:
    """Raw stdin keypress reads (including escape sequences)."""

    @staticmethod
    def read_key() -> str:
        """Read a single keypress (including escape sequences) from stdin."""
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = os.read(fd, 1).decode('utf-8', errors='replace')
            if ch == '\x1b':
                # Read the next two bytes of the escape sequence directly.
                # They arrive immediately after the escape byte, so no timeout needed.
                try:
                    ch += os.read(fd, 1).decode('utf-8', errors='replace')
                    ch += os.read(fd, 1).decode('utf-8', errors='replace')
                except OSError:
                    pass
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


# ─────────────────────────────────────────────
# Command execution
# ─────────────────────────────────────────────


class Command:
    """Run shell steps; child stdout/stderr use this process's terminal."""

    @staticmethod
    def run(
        step: dict,
        *,
        deploy_type: str,
        build_name: str,
        build_directory: str,
        step_num: int,
        is_on_error: bool = False,
        suppress_pre_separator: bool = False,
        suppress_post_separator: bool = False,
        suppress_command_header: bool = False,
    ) -> int:
        """
        Run the command for a step.
        Returns the exit code.
        """
        defs = variable_definitions or {}
        text = interpolate_variables(step.get('text', ''), defs)
        command = interpolate_variables(step.get('command', text), defs)
        stdin_raw = step.get('input')  # optional string fed to stdin
        stdin_ = interpolate_variables(stdin_raw, defs) if isinstance(stdin_raw, str) else stdin_raw
        help_ = interpolate_variables(step.get('help', ''), defs)

        common = dict(
            pid=os.getpid(),
            step_num=step_num,
            deploy_type=deploy_type,
            build_name=build_name,
            build_directory=build_directory,
            user=_get_username(),
        )

        # Help-only entries are notifications, not runnable steps.
        if not text and help_:
            log.info(
                make_kv_log(
                    'build_event', event='notify', step_name=normalize_step_name(help_), **common
                )
            )
            print(f'\n{Style.YELLOW}ℹ  {help_}{Style.RESET}\n')
            return 0

        step_name = normalize_step_name(text)
        ev = 'on_error_' if is_on_error else ''

        log.info(make_kv_log('build_event', event=f'{ev}start', step_name=step_name, **common))

        if help_:
            print(f'\n{Style.YELLOW}ℹ  {help_}{Style.RESET}\n')

        exit_code = 1
        if not suppress_command_header:
            print(f'{Style.BOLD}>>> {command}{Style.RESET}')
        if not suppress_pre_separator:
            print('─' * min(get_term_width(), 72))

        # Run via subprocess: when `input` is set, feed stdin through a pipe; leave
        # stdout/stderr inherited so the child writes directly to the terminal (no
        # Python-side buffering of output).
        if stdin_ is not None:
            proc = subprocess.Popen(
                command,
                shell=True,
                stdin=subprocess.PIPE,
            )
            proc.communicate(input=stdin_.encode('utf-8'))
            exit_code = proc.returncode if proc.returncode is not None else 1
        else:
            exit_code = subprocess.call(command, shell=True)

        if not suppress_post_separator:
            print('─' * min(get_term_width(), 72))

        if exit_code == 0:
            log.info(
                make_kv_log('build_event', event=f'{ev}complete', step_name=step_name, **common)
            )
        else:
            log.info(
                make_kv_log(
                    'build_event',
                    event=f'{ev}failed',
                    step_name=step_name,
                    exit_code=exit_code,
                    **common,
                )
            )

        return exit_code


# ─────────────────────────────────────────────
# Menu
# ─────────────────────────────────────────────


class Menu:
    """Interactive step menu: render, navigate, run steps."""

    @staticmethod
    def _step_display_text(step: dict) -> str:
        """Return the label text shown in the menu for a step."""
        return interpolate_variables(step.get('text', ''), variable_definitions)

    @staticmethod
    def _step_help_text(step: dict) -> str:
        return interpolate_variables(step.get('help', ''), variable_definitions)

    @staticmethod
    def _is_noop(step: dict) -> bool:
        """True for steps that are display/comment only (no text key)."""
        return 'text' not in step

    @staticmethod
    def _step_status_prefix(step_index: int, step_status: dict[int, bool]) -> str:
        """Two visible columns: green ✓ (last success), red ✗ (last failure), or blank."""
        if step_index not in step_status:
            return '  '
        if step_status[step_index]:
            return f'{Style.GREEN}✓{Style.RESET} '
        return f'{Style.RED}✗{Style.RESET} '

    @staticmethod
    def draw_menu(
        steps: list,
        selected: int,
        mode_label: str,
        max_length: int,
        step_status: dict[int, bool],
    ) -> None:
        Screen.clear()
        header = f'[ {mode_label} ]  ↑/↓ or j/k to move, ENTER to run, q to quit'
        print(f'{Style.BOLD}{header}{Style.RESET}')
        print()
        tmp = temporary_directory if temporary_directory is not None else '/tmp'
        print(f'{Style.BOLD}Working Directory:{Style.RESET} {os.getcwd()}')
        print(f'{Style.BOLD}Temporary Directory:{Style.RESET} {tmp}')
        print()

        max_length += 2  # One leading and one trailing space

        for i, step in enumerate(steps):
            label = Menu._step_display_text(step)
            help_ = Menu._step_help_text(step)
            is_noop = Menu._is_noop(step)
            is_sel = i == selected

            if is_noop:
                # Comment/notice line – always dimmed, never selectable
                note = f'  ─── {help_} ───'
                print(f'{Style.DIM}{Style.YELLOW}{note}{Style.RESET}')
                continue

            # Build display row
            row_label = f' {label}'
            suffix = f'  {Style.DIM}({help_}){Style.RESET}' if help_ else ''

            pref = Menu._step_status_prefix(i, step_status)
            if is_sel:
                print(
                    f' {pref}{Style.REVERSE}{row_label:{max_length}}{Style.RESET}{suffix}', end=''
                )
                print()
            else:
                print(f' {pref}{row_label}{suffix}')

        print()

    @staticmethod
    def next_runnable(steps: list, current: int) -> int:
        """Return the index of the next step that isn't a noop, wrapping if needed."""
        n = len(steps)
        idx = current + 1
        while idx < n and Menu._is_noop(steps[idx]):
            idx += 1
        return idx if idx < n else current

    @staticmethod
    def _navigate_up(steps: list, selected: int) -> int:
        new = selected - 1
        while new >= 0 and Menu._is_noop(steps[new]):
            new -= 1
        if new < 0:
            new = len(steps) - 1
            while new > selected and Menu._is_noop(steps[new]):
                new -= 1
        return new

    @staticmethod
    def _navigate_down(steps: list, selected: int) -> int:
        new = selected + 1
        while new < len(steps) and Menu._is_noop(steps[new]):
            new += 1
        if new >= len(steps):
            new = 0
            while new < selected and Menu._is_noop(steps[new]):
                new += 1
        return new

    @staticmethod
    def _run_steps_until_menu_return(
        steps: list,
        selected: int,
        *,
        deploy_type: str,
        build_name: str,
        build_directory: str,
        step_status: dict[int, bool],
    ) -> int:
        """Run step(s) starting at selected; return selected index when returning to the menu."""
        visited: set[int] = set()
        while True:
            if selected in visited:
                print(
                    f'\n{Style.YELLOW}⚠  Auto-advance cycle detected at step {selected}. '
                    f'Returning to menu.{Style.RESET}'
                )
                Keyboard.read_key()
                return selected
            visited.add(selected)
            step = steps[selected]
            Screen.clear()
            exit_code = Command.run(
                step,
                deploy_type=deploy_type,
                build_name=build_name,
                build_directory=build_directory,
                step_num=selected + 1,
            )
            step_status[selected] = exit_code == 0

            if exit_code != 0:
                on_error = step.get('on_error')
                if on_error and isinstance(on_error, list):
                    print(f'\n{Style.YELLOW}Running on_error commands…{Style.RESET}\n')
                    for cmd in on_error:
                        if isinstance(cmd, str):
                            Command.run(
                                {'command': cmd, 'text': cmd},
                                deploy_type=deploy_type,
                                build_name=build_name,
                                build_directory=build_directory,
                                step_num=selected + 1,
                                is_on_error=True,
                                suppress_pre_separator=True,
                                suppress_post_separator=True,
                                suppress_command_header=True,
                            )
                    print()
                print(
                    f'\n{Style.RED}⚠  Step exited with code {exit_code}.{Style.RESET}  '
                    'Press any key to return to menu…'
                )
                Keyboard.read_key()
                return selected

            advanced = Menu.next_runnable(steps, selected)
            if advanced == selected:
                print(
                    f'\n{Style.GREEN}✓  Step complete.{Style.RESET}  '
                    'Press any key to continue to the next step…'
                )
                Keyboard.read_key()
                return selected

            selected = advanced
            if not step.get('auto_advance'):
                print(
                    f'\n{Style.GREEN}✓  Step complete.{Style.RESET}  '
                    'Press any key to continue to the next step…'
                )
                Keyboard.read_key()
                return selected

            next_step = steps[selected]
            if next_step.get('text') == '-- quit --':
                log.info(make_kv_log('build_event', event='user-quit-menu', **_session_context))
                sys.exit(0)

    @staticmethod
    def run_menu(
        steps: list, mode_label: str, *, deploy_type: str, build_name: str, build_directory: str
    ) -> None:
        Screen.enter_alternate()
        global _session_context
        _session_context = dict(
            pid=os.getpid(),
            user=_get_username(),
            deploy_type=deploy_type,
            build_name=build_name,
            build_directory=build_directory,
        )
        try:
            selected = 0
            log.info(make_kv_log('build_event', event='program-start', **_session_context))

            max_length = max(len(Menu._step_display_text(step)) for step in steps)
            step_status: dict[int, bool] = {}
            while selected < len(steps) and Menu._is_noop(steps[selected]):
                selected += 1

            while True:
                Menu.draw_menu(steps, selected, mode_label, max_length, step_status)

                key = Keyboard.read_key()

                if key in ('\x1b[A', '\x1b[D', 'k', 'K'):  # Up / Left (vi: k)
                    selected = Menu._navigate_up(steps, selected)

                elif key in ('\x1b[B', '\x1b[C', 'j', 'J'):  # Down / Right (vi: j)
                    selected = Menu._navigate_down(steps, selected)

                elif key in ('q', 'Q', '\x03'):  # q / Ctrl-C
                    log.info(
                        make_kv_log('build_event', event='user-quit-keypress', **_session_context)
                    )
                    sys.exit(0)

                elif key in ('\r', '\n'):  # Enter
                    step = steps[selected]

                    if Menu._is_noop(step):
                        continue

                    label = step.get('text', '')

                    if label == '-- quit --':
                        log.info(
                            make_kv_log('build_event', event='user-quit-menu', **_session_context)
                        )
                        sys.exit(0)

                    selected = Menu._run_steps_until_menu_return(
                        steps,
                        selected,
                        deploy_type=deploy_type,
                        build_name=build_name,
                        build_directory=build_directory,
                        step_status=step_status,
                    )
        finally:
            Screen.leave_alternate()


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────


def interpolate_variables(text: str, definitions: VariableDefinitions) -> str:
    """Replace ``{{NAME}}`` placeholders; unknown names are left unchanged."""

    def repl(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in definitions:
            return match.group(0)
        value = definitions[name]
        if callable(value):
            return str(value())
        return str(value)

    return _VAR_PATTERN.sub(repl, text)


def verify_json_signature(json_path: str) -> None:
    """Verify a detached GPG signature for ``json_path``.

    The signature file is ``json_path`` with ``.sig`` appended (e.g.
    ``config.json`` → ``config.json.sig``), in the same directory.

    On failure, prints to stderr and terminates the process with exit code 1.
    """

    sig_path = json_path + '.sig'
    if not os.path.isfile(sig_path):
        print(
            f'ERROR: Signature file not found (expected adjacent to JSON): {sig_path}',
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        result = subprocess.run(
            ['gpg', '--verify', sig_path, json_path],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        print(
            'ERROR: gpg not found on PATH; cannot verify JSON signature.',
            file=sys.stderr,
        )
        sys.exit(1)
    except OSError as exc:
        print(f'ERROR: Could not run gpg: {exc}', file=sys.stderr)
        sys.exit(1)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or '').strip()
        msg = f'ERROR: GPG signature verification failed for {json_path}.'
        if detail:
            msg = f'{msg}\n{detail}'
        print(msg, file=sys.stderr)
        sys.exit(1)


def load_config(config_path: list[str], json_file: str | None = None) -> dict:
    """
    Load config from a JSON file. If ``json_file`` resolves to an existing path
    (relative or absolute), that file is used. Otherwise the basename of
    ``json_file`` (default ``build_and_deploy_vanguard.json``) is searched for
    in each directory listed in ``config_path``, in order, then in this script's
    directory; the first match wins.
    Exits with code 1 if the file is missing or invalid.
    """

    json_file = json_file or 'build_and_deploy_vanguard.json'
    explicit = os.path.abspath(os.path.expanduser(json_file))
    script_dir = os.path.dirname(os.path.abspath(__file__))
    search_dirs = [os.path.expanduser(d) for d in config_path] + [script_dir]

    if os.path.isfile(explicit):
        json_path = explicit
    else:
        basename = os.path.basename(json_file)
        json_path = None
        for d in search_dirs:
            candidate = os.path.join(d, basename)
            if os.path.isfile(candidate):
                json_path = candidate
                break
        if json_path is None:
            searched = [os.path.join(d, basename) for d in search_dirs]
            print(
                f'ERROR: Steps file not found: {basename}\n'
                f'  Tried as path: {explicit}\n'
                f'  Searched: {", ".join(searched)}',
                file=sys.stderr,
            )
            sys.exit(1)

    verify_json_signature(json_path)

    try:
        with open(json_path) as f:
            config = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f'ERROR: Could not read {json_path}: {e}', file=sys.stderr)
        sys.exit(1)

    if not isinstance(config, dict):
        print(
            f'ERROR: Expected top-level JSON object in {json_path}, got {type(config).__name__}',
            file=sys.stderr,
        )
        sys.exit(1)
    if 'steps' not in config or not isinstance(config.get('steps'), dict):
        print(f'ERROR: Missing or invalid "steps" key in {json_path}', file=sys.stderr)
        sys.exit(1)

    return config


def _ensure_quit_step(steps: list) -> None:
    """
    Ensure the step list ends with the quit sentinel step.
    Mutates the list in place.
    """
    if not isinstance(steps, list):
        raise TypeError(f'Expected a list of steps, got {type(steps).__name__}')
    if steps and isinstance(steps[-1], dict) and steps[-1].get('text') == '-- quit --':
        return
    steps.append({'text': '-- quit --'})


def _make_temp_directory(suffix: str | None = None, prefix: str | None = None) -> str:
    if os.path.isdir('/tmp'):
        tmp_dir = '/tmp'
    else:
        tmp_dir = os.environ.get('TMPDIR')
    if tmp_dir:
        return tempfile.mkdtemp(dir=os.path.expanduser(tmp_dir), suffix=suffix, prefix=prefix)
    return tempfile.mkdtemp(prefix=prefix, suffix=suffix)


def _cleanup_temp_directory() -> None:
    """Remove the process temp dir created in main(); safe if already gone."""
    path = temporary_directory
    if not path or not os.path.isdir(path):
        return
    try:
        shutil.rmtree(path)
    except OSError:
        pass


_cleaning_up = False


def _on_signal(signum: int, _frame) -> None:
    """Restore terminal and remove temp dir before exiting on common signals."""
    global _cleaning_up
    if _cleaning_up:
        return
    _cleaning_up = True
    try:
        Screen.leave_alternate()
    except OSError:
        pass
    if _session_context:
        try:
            sig_name = signal.Signals(signum).name
        except ValueError:
            sig_name = str(signum)
        log.info(make_kv_log('build_event', event=f'received-{sig_name}', **_session_context))
    _cleanup_temp_directory()
    sys.exit(128 + signum)


def _register_signal_handlers() -> None:
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGABRT):
        try:
            signal.signal(sig, _on_signal)
        except (OSError, AttributeError):
            pass


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description='Interactive build-and-deploy menu.')
    parser.add_argument(
        '-b',
        '--backend-only',
        action='store_true',
        help='Use backend-only step list',
    )
    parser.add_argument(
        '-d',
        '--directory',
        default=None,
        metavar='DIR',
        help='Working directory for steps (overrides settings.build_directory in JSON)',
    )
    parser.add_argument(
        '-s',
        '--skip_directory_check',
        action='store_true',
        help='Do not change directory on startup (ignores -d and JSON build_directory)',
    )
    parser.add_argument(
        '-f',
        '--json_file',
        default=None,
        help='Path to a JSON file containing step definitions (overrides build_and_deploy_vanguard.json)',
    )
    parser.add_argument(
        '-r',
        '--run',
        action='store_true',
        help='Run the interactive menu (required; without this flag, help is printed and the program exits)',
    )
    args = parser.parse_args()

    if not args.run:
        parser.print_help()
        sys.exit(0)

    config_path = ['/usr/local/etc', '~/etc']

    config = load_config(config_path, args.json_file)

    settings = config.get('settings') or {}

    build_name = settings.get('build_name', 'build_and_deploy')
    build_directory = settings.get('build_directory', '')

    global temporary_directory
    temporary_directory = _make_temp_directory(prefix=build_name, suffix=str(os.getpid()))

    _register_signal_handlers()

    try:
        build_type: str | None = None
        deploy_type: str | None = None

        if args.backend_only:
            steps = config.get('steps', {}).get('backend')
            build_type = 'BACKEND ONLY'
            deploy_type = 'backend'
        else:
            steps = config.get('steps', {}).get('full')
            build_type = 'FULL DEPLOY'
            deploy_type = 'full'

        if not steps:
            print(f'ERROR: No steps found for {build_type}.')
            sys.exit(1)

        _ensure_quit_step(steps)

        if not args.skip_directory_check:
            from_cli = args.directory
            from_json = settings.get('build_directory')
            if from_cli is not None and str(from_cli).strip() != '':
                build_dir = from_cli.strip()
            elif from_json is not None and str(from_json).strip() != '':
                build_dir = from_json.strip()
            else:
                print(
                    'ERROR: Set settings.build_directory in the JSON file, or pass -d/--directory.',
                    file=sys.stderr,
                )
                sys.exit(1)
            build_dir = os.path.expanduser(build_dir)
            target = os.path.realpath(os.path.abspath(build_dir))
            cwd_real = os.path.realpath(os.getcwd())
            if cwd_real != target:
                os.chdir(target)
            build_directory = target

        Menu.run_menu(
            steps,
            build_type,
            deploy_type=deploy_type,
            build_name=build_name,
            build_directory=build_directory,
        )
    finally:
        global _cleaning_up
        if not _cleaning_up:
            _cleaning_up = True
            _cleanup_temp_directory()


if __name__ == '__main__':
    main()
