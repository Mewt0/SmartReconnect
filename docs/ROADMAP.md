# SmartReconnect roadmap

This roadmap is the execution order for the project. Each enabled reconnect milestone is blocked by evidence from the previous one.

## Milestone 0.1 — Diagnostic detector

Tracking issue: #2

Goal: prove the detector on the exact WoT client without changing the connection.

Implementation:

- use the same native signals as the WoT battle debug panel:
  - `BigWorld.statLagDetected()`
  - `BigWorld.statPing()`
- poll every 0.2 seconds
- require a continuous 3-second RED window before producing a decision
- log `IConnectionManager.isConnected()` and `arena.period`
- emit exactly one `WOULD RECONNECT` per continuous outage
- keep all real disconnect/relogin actions disabled

Gate to continue:

- complete `docs/TESTING.md`
- attach exact client build and `python.log` evidence to #2
- prove short RED spikes do not trigger
- prove sustained RED triggers once
- determine whether the useful window is `lag=True` while ConnectionManager still reports connected

## Milestone 0.2 — Manual stock disconnect

Tracking issue: #3

Goal: validate the reconnect controller independently from automatic detection.

Implementation:

- Ctrl+K only
- resolve `IGameplayLogic`
- add single-flight/busy guard
- reject replay
- validate current client state
- call `goToLoginByDisconnectRQ()`
- log all guards and state transitions
- automatic RED trigger remains diagnostic-only

Gate to continue:

- repeated Ctrl+K cannot start duplicate disconnects
- stock cleanup reaches the expected login transition
- no replay action
- no executable/socket manipulation

## Milestone 0.3 — LOGIN observer + WGC relogin

Tracking issue: #4

Goal: complete a manual end-to-end reconnect.

Implementation:

- capture the selected/current server before disconnect
- observe `GameplayStateID.LOGIN` using `IGameplayLogic.addOneshotObserver()`
- no fixed sleeps/magic delays
- invoke supported `ILoginManager` WGC login flow
- handle WGC unavailable, rejected login and expired token as terminal/non-looping outcomes
- reset controller state after success/failure

Gate to continue:

- Ctrl+K can disconnect, reach real LOGIN state and initiate exactly one WGC login attempt
- successful login returns through WoT's normal ongoing-battle reconnect path
- failed login leaves the user in a safe login state without an infinite loop

## Milestone 0.4 — Automatic sustained-RED reconnect

Tracking issue: #5

Goal: connect the validated detector to the validated reconnect controller.

Implementation:

- RED must remain continuous beyond the configured grace period
- immediately re-check `IConnectionManager.isConnected()` before forced disconnect
- reject replay and non-reconnectable client states
- one outage -> one automatic attempt
- preserve Ctrl+K manual fallback
- conservative cooldown / retry policy

Recommended initial defaults:

```text
autoReconnect = true
lagGracePeriod = 3.0s (subject to v0.1 telemetry)
pollInterval = 0.2s
maxAutomaticAttemptsPerOutage = 1
manualHotkey = Ctrl+K
```

Gate to continue:

- brief RED spikes never disconnect
- sustained RED triggers once
- stock timeout race does not double-disconnect
- long internet outage does not loop

## Milestone 0.5 — Hardening

Tracking issue: #6

Goal: make all transitions bounded and predictable.

Target controller state machine:

```text
IDLE
  -> MONITORING
  -> LAG_SUSPECTED
  -> RECONNECTING
  -> WAITING_LOGIN
  -> CONNECTING
  -> MONITORING

Terminal/error paths:
  -> LOGIN_IDLE
  -> COOLDOWN
  -> IDLE
```

Required edge cases:

- threshold-boundary RED->GREEN race
- WoT disconnects itself before SmartReconnect acts
- battle ends during reconnect
- arena changes
- prebattle/loading/afterbattle
- postmortem/spectator
- repeated outages
- WGC unavailable or token rejected
- long local internet outage
- server outage/restart
- clean client shutdown/mod fini

Every transition must be reconstructable from `python.log`.

## Milestone 1.0 — Release engineering

Tracking issue: #7

Goal: ship a reproducible and clearly versioned `.wotmod`.

Implementation:

- reproducible Python 2-compatible build
- CI syntax/build check
- tag -> release artifact
- exact WoT build compatibility table
- installation/configuration/troubleshooting docs
- release notes
- Fair Play review before release

## Architecture rules

1. Prefer current `izeberg/wot-src` call sites over guessed APIs.
2. Verify version-sensitive behavior against `sources/version.xml`.
3. Use stock WoT state/events instead of external ping probes or magic delays.
4. First implementation of any connection-changing behavior must be manually triggered or diagnostic-only.
5. No executable patching, packet manipulation, hidden battle data, combat automation or Fair Play bypasses.
6. One PR should represent one coherent milestone/behavior change where practical.

## Current status

- PR #1: diagnostic v0.1 scaffold
- #2: first live-validation gate
- #3: manual reconnect
- #4: LOGIN/WGC relogin
- #5: automatic reconnect
- #6: hardening
- #7: release pipeline
