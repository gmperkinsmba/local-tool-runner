# Local Console

First principle: Show each approved local tool. Keep its work bounded and easy to stop.

Local Console runs a short allowlist of harmless tools in named sessions. Each session has its own process and pseudo-terminal. It also has its own working folder, time limit, and saved output. The interface can reconnect to active and finished sessions while the server runs.

## Run

Requires Python 3 on macOS or Linux. The backend uses only the Python standard library.

```sh
python3 server.py
```

Open http://127.0.0.1:8314. The listener binds to loopback. Only the listed profiles can start. The app has no shell or free-form commands. You cannot pass command arguments or process input. You cannot choose an arbitrary path.

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

Tests check process isolation, reconnect, terminal resize, output limits, and timeouts. They also check allowlist and request boundaries, the four-session limit, and cleanup of parent and child processes.

## Limits and safety

This is a local process viewer, not a general terminal emulator. It does not run user-defined commands, arguments, paths, or input. The worker profiles in `worker.py` are original code. They do not form an operating-system sandbox. Do not add a profile that reads or writes user files. Do not add one that runs an external tool without a separate security review.

## Data and license

No user files, credentials, or employer data are included. Original code is MIT licensed; see `LICENSE`.
