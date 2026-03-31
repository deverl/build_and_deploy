# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

An interactive terminal menu tool for running build/deploy steps in sequence. The Python version (`build_and_deploy.py`) is the primary implementation; `_bash/build_and_deploy.sh` is the original bash prototype.

The tool reads step definitions from a JSON config file and presents a navigable TUI menu. Each step runs a shell command, and the cursor auto-advances on success.

## Running

```bash
# Run with default config (build_and_deploy_vanguard.json)
./build_and_deploy.py -r

# Run with a specific config file
./build_and_deploy.py -r -f test.json

# Backend-only mode
./build_and_deploy.py -r -b

# Skip directory change (useful for local dev/testing)
./build_and_deploy.py -r -s

# Specify working directory
./build_and_deploy.py -r -d /path/to/project
```

The `-r` flag is required to actually launch the menu; without it, help is printed.

## Linting

```bash
ruff check build_and_deploy.py
ruff format build_and_deploy.py
```

Ruff config: 100 char line length, single quotes, space indent.

## Architecture

**Single-file Python app** (`build_and_deploy.py`) with these key classes:
- `Menu` — TUI rendering, keyboard navigation (vi keys j/k supported), step execution loop
- `Command` — runs shell commands via subprocess; supports piped `input` for non-interactive prompts
- `Screen` — alternate terminal buffer management
- `Keyboard` — raw keypress reading including escape sequences

**JSON config format** (e.g. `build_and_deploy_vanguard.json`):
- `settings.build_name` — used for temp directory naming
- `settings.build_directory` — working directory for steps
- `steps.full` / `steps.backend` — arrays of step objects

**Step object keys**: `text` (menu label), `command` (shell command, defaults to text), `help` (info note), `input` (stdin string), `auto_advance` (skip pause on success), `on_error` (array of recovery commands). Keys starting with `comment` are ignored.

**Variable interpolation**: `{{PID}}`, `{{DATE}}`, `{{TIME}}`, `{{TMPDIR}}` are expanded in text/command/help/input fields. `TMPDIR` points to a per-process temp directory that is cleaned up on exit.

Config file search order: explicit path → `config_path` directories (`/usr/local/etc`, `~/etc`) → script's own directory.
