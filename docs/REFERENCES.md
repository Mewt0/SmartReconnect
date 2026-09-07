# SmartReconnect research references

This document is the working source map for SmartReconnect. Prefer these sources over guesses when changing client-facing logic.

## 1. Decompiled WoT client — primary technical reference

Repository: https://github.com/izeberg/wot-src

Primary files currently used by SmartReconnect research:

- `sources/res/scripts/client/gui/battle_control/controllers/debug_ctrl.py`
  - WoT battle debug panel polling loop.
  - Reads `BigWorld.statLagDetected()` and `BigWorld.statPing()` every 0.2 seconds.
  - This is the primary evidence for how the in-battle lag/red-lamp state is computed.

- `sources/res/scripts/client/gui/Scaleform/daapi/view/battle/shared/debug_panel.py`
  - Python-side debug panel state.
  - Tracks `_isLaggingNow` and forwards changes to Scaleform.

- `sources-as3/gui_battle/scripts/net/wg/gui/battle/views/debugPanel/DebugPanel.as`
  - Scaleform implementation of the red/green network indicator.
  - Toggles `lagOnlineSpr` / `lagOfflineSpr` from the lag boolean.

- `sources/res/scripts/client/gameplay/delegator.py`
  - Current implementation of `IGameplayLogic`.
  - `goToLoginByDisconnectRQ()` prepares WGC login, then performs the normal request-disconnect path.

- `sources/res/scripts/client/skeletons/gameplay.py`
  - Interface and gameplay state IDs.
  - Includes `GameplayStateID.LOGIN` and `goToLoginByDisconnectRQ()`.

- `sources/res/scripts/client/connection_mgr.py`
  - Current client connection manager.
  - Provides `disconnect()`, `isConnected()`, `isDisconnected()` and connection events.
  - Also contains WoT's login retry/backoff implementation.

- `sources/res/scripts/client/skeletons/connection_mgr.py`
  - Public client-side interface for connection state and events.

- `sources/res/scripts/client/gui/login/Manager.py`
  - WGC/token login flow.
  - Provides `tryPrepareWGCLogin()` and `tryWgcLogin(serverName=None)`.

- `sources/res/scripts/client/gui/login/Servers.py`
  - Login server selection state.
  - Exposes the selected server data used by the login flow.

- `sources/res/scripts/client/gui/app_loader/observers.py`
  - Gameplay-state-driven UI transitions.
  - Useful for waiting for the real `LOGIN` state instead of using arbitrary sleeps.

- `sources/version.xml`
  - Always check this before trusting findings as version-current.

### Version rule

Treat `izeberg/wot-src` as highly useful but not guaranteed byte-identical to the user's installed client. Re-check `sources/version.xml` and validate critical behavior in `python.log` on the exact target client before enabling destructive or connection-changing actions.

## 2. WoT modding documentation

Community documentation: https://wgmods.dev/docs/wot

Use primarily for:

- `.wotmod` package layout
- `meta.xml`
- Python client-mod packaging conventions
- general mod-loading behavior

This is a secondary reference for internal APIs; the decompiled client remains primary for version-specific behavior.

## 3. Open-source WoT mods — implementation references

### FastReconnect

Repository: https://github.com/Pruszko/FastReconnect

Use for:

- historical proof that a client mod can intentionally trigger the normal disconnect/login transition
- manual `Ctrl+K` reconnect UX reference

Do not copy old API calls blindly; verify them against the current client first.

### WotStat mods

Repositories:

- https://github.com/wotstat/wotstat-vegetation
- https://github.com/wotstat/wotstat-positions

Use for:

- modern `.wotmod` project layout
- `mod_*.py` entrypoint style (`init()` / `fini()`)
- build scripts and Python 2 `.pyc` packaging
- current event/hotkey patterns

## 4. Official Wargaming public API

Developer portal: https://developers.wargaming.net/

This is a web/public-data API, not the internal WoT client mod API. It is useful for account, vehicle, clan and related external data, but is not currently required for SmartReconnect's network recovery logic.

## 5. Fair Play / prohibited-mod rules

Official policy: https://worldoftanks.eu/en/content/guide/fair-play/prohibited-mods/

SmartReconnect should remain a connection-recovery utility only. It must not expose hidden battle information, automate combat decisions, alter aiming/shooting behavior, or provide prohibited gameplay advantages.

## 6. Current SmartReconnect API map

| Purpose | Client API / class | Status |
|---|---|---|
| Detect WoT's lag/red-lamp state | `BigWorld.statLagDetected()` | Confirmed in current client source |
| Read displayed battle ping | `BigWorld.statPing()` | Confirmed in current client source |
| Poll cadence reference | `DebugController` (`0.2s`) | Confirmed |
| Check connection state | `IConnectionManager.isConnected()` | Confirmed |
| Normal disconnect | `IConnectionManager.disconnect()` | Confirmed |
| Request disconnect + return toward login | `IGameplayLogic.goToLoginByDisconnectRQ()` | Confirmed |
| Wait for actual login state | `GameplayStateID.LOGIN` + gameplay observer | Confirmed |
| Prepare WGC login | `ILoginManager.tryPrepareWGCLogin()` | Confirmed |
| Start WGC login | `ILoginManager.tryWgcLogin()` | Confirmed |
| Recover ongoing arena after relogin | Stock WoT reconnect flow | Confirmed to exist; live SmartReconnect integration still pending |

## 7. Development rule for this repository

For every connection-changing feature:

1. Find the current client implementation in `izeberg/wot-src`.
2. Find at least one stock WoT call site using the same API when practical.
3. Keep the first implementation diagnostic-only.
4. Validate behavior on the exact client build through `python.log`.
5. Only then enable the real reconnect action.

This rule is intentionally conservative because a false reconnect in a live battle is worse than waiting for the stock timeout.
