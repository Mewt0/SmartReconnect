# SmartReconnect testing plan

This document defines the gate between diagnostic v0.1 and any real reconnect action.

## Principle

v0.1 must never intentionally disconnect the client. Its only job is to prove that the detector identifies the same sustained outage the player sees as the red network indicator.

Do not enable real reconnect until the acceptance criteria below are met on the exact target WoT client build.

## Expected log fields

During a lag episode, `python.log` should include:

- `ping`
- `connected` from `IConnectionManager.isConnected()`
- `arenaPeriod`
- elapsed RED duration
- the final `WOULD RECONNECT` decision

Example:

```text
[SmartReconnect] RED started ping=... connected=True arenaPeriod=...
[SmartReconnect] RED elapsed=1.0s ping=... connected=True arenaPeriod=...
[SmartReconnect] RED elapsed=2.0s ping=... connected=True arenaPeriod=...
[SmartReconnect] RED threshold reached elapsed=3.0s connected=True arenaPeriod=...
[SmartReconnect] WOULD RECONNECT reason=auto-lag elapsed=... ping=...
```

The most important observation is whether the red-lamp signal becomes sustained while `IConnectionManager` still reports `connected=True`. That is the window SmartReconnect is intended to shorten.

## Test matrix

| ID | Scenario | Expected result |
|---|---|---|
| D01 | Start client and enter a normal battle/training arena | Mod loads; monitor starts once; no exceptions |
| D02 | Stable connection for several minutes | No `WOULD RECONNECT` |
| D03 | Very short RED/lag spike below 3 seconds | `RED started`, then `GREEN recovered`; timer resets; no reconnect request |
| D04 | Sustained RED longer than 3 seconds | Exactly one `RED threshold reached` and one `WOULD RECONNECT` for the outage |
| D05 | RED remains active for 10+ seconds | No repeated `WOULD RECONNECT` for the same continuous outage |
| D06 | RED -> GREEN -> RED again | First episode resets; second episode starts a fresh timer |
| D07 | Leave battle normally | Monitor stops and callback is cancelled |
| D08 | Enter another battle | Monitor starts cleanly with no stale RED state |
| D09 | Play a replay | Detector and Ctrl+K reconnect logic remain inactive |
| D10 | Press Ctrl+K outside replay | Diagnostic manual request is logged; no network action occurs |
| D11 | ConnectionManager becomes disconnected before the 3-second gate | Log captures `connected=False`; v0.1 still performs no network action |
| D12 | Client shutdown/mod fini | No callback or event-unsubscribe exceptions |

## Controlled outage test

Prefer a training environment when possible so testing does not affect a normal match.

For detector validation, briefly interrupt only the test machine's own network connection long enough for WoT's red indicator to remain active beyond the configured 3-second threshold, then restore it. The v0.1 mod must only log the decision and must not alter the connection itself.

Record the relevant `python.log` section from a few seconds before RED starts until the connection recovers or the stock client times out.

## Acceptance criteria for v0.1

All of the following must be true before work moves to an enabled reconnect controller:

1. No import/init exceptions on the target client.
2. The monitor starts and stops with the battle lifecycle without duplicate callbacks.
3. Short RED spikes below the threshold never generate `WOULD RECONNECT`.
4. Sustained RED generates exactly one `WOULD RECONNECT` per continuous outage.
5. The log demonstrates the relationship between `statLagDetected()` and `IConnectionManager.isConnected()` during a real outage.
6. Replay behavior is inert.
7. Ctrl+K produces only a diagnostic request in v0.1.
8. No network-changing code path exists in the installed diagnostic build.

## Evidence to save

For every live-test session keep:

- WoT client version/build
- SmartReconnect version
- relevant `python.log` excerpt
- whether the visible indicator was red/green
- approximate duration of the outage
- whether WoT recovered by itself or reached the stock timeout

These observations will be used to choose the final grace-period and guards for v0.3 auto reconnect.

## Next gate: v0.2 manual reconnect

After v0.1 passes, implement only the manually initiated reconnect path first:

```text
Ctrl+K
 -> validate state
 -> single-flight guard
 -> goToLoginByDisconnectRQ()
 -> observe real LOGIN state
```

Automatic RED-triggered disconnect remains disabled during this milestone. This isolates reconnect-controller correctness from detector correctness.
