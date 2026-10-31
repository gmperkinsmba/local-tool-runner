# Local Tool Runner

First principle: Show each approved local tool. Keep its work bounded and easy to stop.

Local Tool Runner runs a short allowlist of harmless tools in named sessions. Each session has its own process and pseudo-terminal. It also has its own working folder, time limit, and saved output. You can reconnect to active and finished sessions while the server runs.

## Run

Open `~/Applications/Local Tool Runner.app` in Finder. The app bundles Python and starts its loopback service when the window opens. No Python install is needed. You do not need a browser tab or server command. Close the window or press Command-Q to stop the service and any sessions started by this app. Session output and records exist only in memory; isolated session folders remain under `~/.local/share/local-console/sessions`.

The installed app is unsigned. macOS may ask you to confirm the first launch in Privacy & Security. To uninstall, quit Local Tool Runner and move only `~/Applications/Local Tool Runner.app` to Trash. The runtime session folders are separate and are not removed.

**Browser alternative**

The source browser mode uses Python 3.10 or newer and the standard library. I did not test browser mode on Linux.

```sh
python3 server.py
```

Open http://127.0.0.1:8314. The listener binds to loopback. Only the listed profiles can start. The app has no shell or free-form commands. You cannot pass command arguments or process input. You cannot choose an arbitrary path. Stop the source server with Ctrl+C.

**Build from source**

On macOS, use Python 3.12 with the pinned desktop requirements:

```sh
uv venv .desktop-venv --python 3.12
uv pip install --python .desktop-venv/bin/python -r requirements-desktop.lock.txt
.desktop-venv/bin/python build_desktop.py
.desktop-venv/bin/python install_desktop.py
```

The build emits `dist/Local Tool Runner.app` and refuses to replace an app without its ownership marker. Native builds target macOS; Linux builds are not supported or tested here.

## Profiles and limits

- Progress fixture prints ten synthetic progress lines.
- Python runtime report prints the interpreter and platform. It also prints the terminal size.
- Synthetic file checksums print SHA-256 hashes for two fixed sample byte strings.
- Process tree fixture starts a fixed child process to show process-group cleanup.
- Output limit fixture fills a session log so the 64 KiB cap can be seen.

The app allows four active sessions and keeps up to twelve sessions in memory. Choose a 30, 60, or 120 second time limit. Each session has a 64 KiB output cap. Resizing the output panel changes the pseudo-terminal size. Stopped and finished output stays until history is pruned or the server stops.

Session data lives in memory. The working folders default to `~/.local/share/local-console/sessions`; set `LOCAL_CONSOLE_DATA` before startup to choose a runtime folder. No user credentials are passed to child processes. Process environments contain only a system search path and the isolated working folder as `HOME`.

## Test

```sh
python3 -m unittest discover -s tests -v
```

Tests check process isolation and reconnect. They check terminal size, output caps, and time limits. They check the tool allowlist and request rules. They check the four-session limit. They also check cleanup of parent and child processes.

## Limits and safety

The app shows local processes. It does not act as a general terminal. It does not run user-defined commands, arguments, paths, or input. The worker profiles in `worker.py` are original code. They do not form an operating-system sandbox. Do not add a profile that reads or writes user files. Require a separate security review for outside tools.

## Data and license

No user files, credentials, or employer data are included. Original code is MIT licensed; see `LICENSE`.
