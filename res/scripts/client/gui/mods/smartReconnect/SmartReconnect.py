import logging

import BigWorld
import BattleReplay
import Keys

from gui import InputHandler
from PlayerEvents import g_playerEvents

from .Config import VERSION, MANUAL_HOTKEY_ENABLED
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

        _logger.info('[SmartReconnect] loaded version=%s diagnostic=true', VERSION)

        # Defensive support for script reloads while already inside an arena.
        player = BigWorld.player()
        if player is not None and hasattr(player, 'arena') and player.arena is not None:
            self._onAvatarBecomePlayer()

    def dispose(self):
        self._monitor.stop()

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
        self._monitor.start()

    def _onAvatarBecomeNonPlayer(self, *args, **kwargs):
        self._inBattle = False
        self._monitor.stop()

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
