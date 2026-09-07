import logging

import BigWorld
import BattleReplay

from helpers import dependency
from skeletons.connection_mgr import IConnectionManager

from .Config import POLL_INTERVAL, LAG_GRACE_PERIOD

_logger = logging.getLogger('SmartReconnect')


class ConnectionMonitor(object):

    def __init__(self, reconnectCallback):
        self._reconnectCallback = reconnectCallback
        self._connectionMgr = dependency.instance(IConnectionManager)
        self._callbackID = None
        self._running = False
        self._lagSince = None
        self._triggered = False
        self._lastLoggedSecond = -1

    def start(self):
        if self._running:
            return
        self._running = True
        self._resetLagState()
        _logger.info('[SmartReconnect] battle monitor started')
        self._schedule(0.0)

    def stop(self):
        self._running = False
        if self._callbackID is not None:
            try:
                BigWorld.cancelCallback(self._callbackID)
            except Exception:
                _logger.exception('[SmartReconnect] failed to cancel monitor callback')
            self._callbackID = None
        self._resetLagState()
        _logger.info('[SmartReconnect] battle monitor stopped')

    def _schedule(self, delay=None):
        if not self._running:
            return
        if delay is None:
            delay = POLL_INTERVAL
        self._callbackID = BigWorld.callback(delay, self._tick)

    def _tick(self):
        self._callbackID = None
        if not self._running:
            return

        try:
            if BattleReplay.isPlaying():
                self._resetLagState()
                return

            player = BigWorld.player()
            if player is None or not hasattr(player, 'arena') or player.arena is None:
                self._resetLagState()
                return

            isLagging = bool(BigWorld.statLagDetected())
            ping = BigWorld.statPing()
            now = BigWorld.timeExact()
            connected = self._readConnectedState()
            arenaPeriod = getattr(player.arena, 'period', None)

            if isLagging:
                self._handleLag(now, ping, connected, arenaPeriod)
            else:
                self._handleHealthy(ping, connected, arenaPeriod)
        except Exception:
            _logger.exception('[SmartReconnect] monitor tick failed')
        finally:
            self._schedule()

    def _readConnectedState(self):
        try:
            return bool(self._connectionMgr.isConnected())
        except Exception:
            _logger.exception('[SmartReconnect] failed to read connection manager state')
            return None

    def _handleLag(self, now, ping, connected, arenaPeriod):
        if self._lagSince is None:
            self._lagSince = now
            self._triggered = False
            self._lastLoggedSecond = -1
            _logger.warning(
                '[SmartReconnect] RED started ping=%s connected=%s arenaPeriod=%s',
                str(ping),
                str(connected),
                str(arenaPeriod)
            )

        elapsed = max(0.0, now - self._lagSince)
        wholeSecond = int(elapsed)
        if wholeSecond != self._lastLoggedSecond:
            self._lastLoggedSecond = wholeSecond
            _logger.warning(
                '[SmartReconnect] RED elapsed=%.1fs ping=%s connected=%s arenaPeriod=%s',
                elapsed,
                str(ping),
                str(connected),
                str(arenaPeriod)
            )

        if elapsed >= LAG_GRACE_PERIOD and not self._triggered:
            self._triggered = True
            _logger.warning(
                '[SmartReconnect] RED threshold reached elapsed=%.1fs connected=%s arenaPeriod=%s',
                elapsed,
                str(connected),
                str(arenaPeriod)
            )
            self._reconnectCallback('auto-lag', elapsed, ping)

    def _handleHealthy(self, ping, connected, arenaPeriod):
        if self._lagSince is not None:
            elapsed = max(0.0, BigWorld.timeExact() - self._lagSince)
            _logger.info(
                '[SmartReconnect] GREEN recovered after %.1fs ping=%s connected=%s arenaPeriod=%s; timer reset',
                elapsed,
                str(ping),
                str(connected),
                str(arenaPeriod)
            )
        self._resetLagState()

    def _resetLagState(self):
        self._lagSince = None
        self._triggered = False
        self._lastLoggedSecond = -1
