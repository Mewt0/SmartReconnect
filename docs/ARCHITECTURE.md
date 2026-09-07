# SmartReconnect architecture

## Problem

During a dead World of Tanks battle connection the client can show the red network/lag indicator while the battle appears frozen, then wait for its normal timeout before returning the player to login.

SmartReconnect aims to shorten that recovery path without patching the executable, manipulating packets, or replacing the game's connection stack.

## Detector

WoT's own battle debug controller reads:

```python
isLaggingNow = BigWorld.statLagDetected()
ping = BigWorld.statPing()
```

SmartReconnect deliberately uses the same native lag signal instead of external ICMP/HTTP probes.

Polling interval: `0.2s`.

## State model

```text
IDLE
  -> MONITORING
  -> LAG_SUSPECTED
  -> RECONNECT_REQUESTED
```

v0.1 stops at `RECONNECT_REQUESTED` and writes `WOULD RECONNECT` to the log.

Future reconnect flow:

```text
RECONNECT_REQUESTED
  -> goToLoginByDisconnectRQ()
  -> wait for LOGIN gameplay state
  -> WGC login on the selected server
  -> WoT rejoins the ongoing arena using its normal reconnect path
```

## False-positive protection

Automatic reconnect must not fire on a brief lag spike. The detector therefore requires a continuous lag state for `LAG_GRACE_PERIOD` seconds. Any healthy sample resets the timer.

The first live validation build intentionally has all network-changing actions disabled.

## Manual fallback

`Ctrl+K` produces a manual reconnect request. In v0.1 it is also diagnostic-only.

## Next milestone

After validating logs on the target client:

1. add a guarded real disconnect through `IGameplayLogic.goToLoginByDisconnectRQ()`;
2. observe `GameplayStateID.LOGIN` rather than sleeping for a guessed delay;
3. start WGC login through the existing login manager;
4. add single-flight protection so one outage cannot start multiple reconnects;
5. stop automatic retries after a failed login until behavior is measured.
