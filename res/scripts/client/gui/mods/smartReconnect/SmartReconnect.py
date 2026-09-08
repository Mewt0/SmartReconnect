import logging

import BigWorld
import BattleReplay
import Keys

from gui import InputHandler
from PlayerEvents import g_playerEvents

from .Config import (
    VERSION,
    DIAGNOSTIC_MODE,
    MANUAL_HOTKEY_ENABLED,
    AUTO_RECONNECT_ENABLED,
    POLL_INTERVAL,
    LAG_GRACE_PERIOD,
    LOGIN_WAIT_TIMEOUT,
    WGC_LOGIN_WAIT_TIMEOUT,
    RETURN_TO_GAME_TIMEOUT,
    COOLDOWN_AFTER_FAILURE,
    STABLE_GREEN_SAMPLES,
)
from .ConnectionMonitor import ConnectionMonitor
from .ReconnectController import ReconnectController

_logger = logging.getLogger('SmartReconnect')


class SmartReconnect(object):

    def __init__(self):
        self._controller = ReconnectController()
        self._monitor = ConnectionMonitor(self._onReconnectRequested)
        self._inBattle = False

        g_playerEvents.onAvatarBecomePlayer += self._onAvatarBecomePlayer
        g_playerEvents.onAvatarBecomeNonPlayer += self._onAvatarBecomeNonPlayer
        InputHandler.g_instance.onKeyUp += self._onKeyUp

        _logger.info(
            '[SmartReconnect] loaded version=%s diagnostic=%s autoReconnect=%s poll=%.1fs redThreshold=%.1fs loginTimeout=%.1fs wgcTimeout=%.1fs returnTimeout=%.1fs cooldown=%.1fs stableGreenSamples=%s',
            VERSION,
            str(DIAGNOSTIC_MODE),
            str(AUTO_RECONNECT_ENABLED),
            POLL_INTERVAL,
            LAG_GRACE_PERIOD,
            LOGIN_WAIT_TIMEOUT,
            WGC_LOGIN_WAIT_TIMEOUT,
            RETURN_TO_GAME_TIMEOUT,
            COOLDOWN_AFTER_FAILURE,
            str(STABLE_GREEN_SAMPLES)
        )

        # Defensive support for script reloads while already inside an arena.
        player = BigWorld.player()
        if player is not None and hasattr(player, 'arena') and player.arena is not None:
            self._onAvatarBecomePlayer()

    def dispose(self):
        self._monitor.stop()
        self._controller.clearBusy('dispose')

        try:
            g_playerEvents.onAvatarBecomePlayer -= self._onAvatarBecomePlayer
        except Exception:
            pass
        try:
            g_playerEvents.onAvatarBecomeNonPlayer -= self._onAvatarBecomeNonPlayer
        except Exception:
            pass
        try:
            InputHandler.g_instance.onKeyUp -= self._onKeyUp
        except Exception:
            pass

        _logger.info('[SmartReconnect] disposed')

    def _onAvatarBecomePlayer(self, *args, **kwargs):
        if BattleReplay.isPlaying():
            return
        self._inBattle = True
        self._controller.onBattleEntered()
        self._monitor.start()

    def _onAvatarBecomeNonPlayer(self, *args, **kwargs):
        self._inBattle = False
        self._monitor.stop()
        self._controller.onBattleExited()

    def _onReconnectRequested(self, reason, elapsed=None, ping=None):
        self._controller.requestReconnect(reason, elapsed, ping)

    def _onKeyUp(self, event):
        if not MANUAL_HOTKEY_ENABLED:
            return
        if BattleReplay.isPlaying():
            return
        if event.key != Keys.KEY_K:
            return
        if not event.isCtrlDown():
            return

        _logger.warning('[SmartReconnect] Ctrl+K manual reconnect requested')
        self._controller.requestReconnect('manual-hotkey')
