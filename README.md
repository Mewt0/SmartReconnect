# SmartReconnect

SmartReconnect is an experimental World of Tanks client mod intended to shorten recovery from a dead battle connection.

## Current milestone

**v0.1 is diagnostic-only. It does not disconnect or reconnect automatically.**

The first build validates the same lag signal used by WoT's battle debug panel before any connection-changing action is enabled.

It polls:

- `BigWorld.statLagDetected()`
- `BigWorld.statPing()`

Default behavior:

1. Normal connection -> monitor remains idle.
2. Lag indicator becomes red -> start a timer.
3. Three consecutive valid healthy samples -> reset the timer. Unreadable samples break the healthy streak.
4. Indicator remains red for 3 seconds -> write `WOULD RECONNECT` to `python.log`.
5. No network action is performed in diagnostic mode.

`Ctrl+K` is also detected as a manual reconnect request, but in diagnostic mode it only logs `WOULD RECONNECT`.

## Planned reconnect path

`RED -> grace period -> goToLoginByDisconnectRQ() -> LOGIN state -> WGC login -> ongoing battle`

The reconnect controller will use WoT's own gameplay and login services rather than terminating the process or manipulating sockets directly.

## Project layout

```text
SmartReconnect/
├── README.md
├── .gitignore
├── meta.xml
├── build.sh
├── docs/
│   └── ARCHITECTURE.md
└── res/scripts/client/gui/mods/
    ├── mod_smartReconnect.py
    └── smartReconnect/
        ├── __init__.py
        ├── Config.py
        ├── ConnectionMonitor.py
        ├── ReconnectController.py
        └── SmartReconnect.py
```

## Build

Requires a Python 2 environment compatible with the WoT client mod pipeline plus `zip` and a POSIX shell.

```bash
./build.sh -v 0.1.0
```

The result is written to the repository root as:

```text
mewt0.smartReconnect_0.1.0.wotmod
```

Copy it into:

```text
World_of_Tanks/mods/<current-game-version>/
```

Then inspect `python.log` for lines beginning with `[SmartReconnect]`.

## Diagnostic test

A successful first test should look roughly like this:

```text
[SmartReconnect] battle monitor started
[SmartReconnect] RED started ping=...
[SmartReconnect] RED elapsed=1.0s ping=...
[SmartReconnect] RED elapsed=2.0s ping=...
[SmartReconnect] RED threshold reached elapsed=3.0s
[SmartReconnect] WOULD RECONNECT reason=auto-lag
```

Three consecutive healthy samples with a valid ping and a connected client reset the lag episode. A shorter GREEN blip does not rearm the detector. Diagnostic mode blocks both manual and automatic network actions.

## Offline QA

Run `python -B -m unittest discover -s tests -v` with Python 2.7 (the payload runtime); Python 3 is also supported for offline tests. Tests validate callback deadlines, avatar lifecycle integration, diagnostic guards, recovery, and timeout cleanup. They do not replace validation against actual WoT gameplay/login interfaces.

The optional real reconnect path requires `DIAGNOSTIC_MODE = False`. Automatic requests additionally require `AUTO_RECONNECT_ENABLED = True`. Expected avatar teardown during a reconnect preserves the login watchdog; a failed return is bounded by timeouts.
