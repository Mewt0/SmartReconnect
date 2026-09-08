import logging

import BigWorld
import BattleReplay

from helpers import dependency

from .Config import DIAGNOSTIC_MODE, AUTO_RECONNECT_ENABLED

try:
    from skeletons.gameplay import IGameplayLogic
except Exception:
    IGameplayLogic = None

_logger = logging.getLogger('SmartReconnect')


class ReconnectController(object):

    def __init__(self):
        self._busy = False

    @property
    def busy(self):
        return self._busy

    def requestReconnect(self, reason, elapsed=None, ping=None):
        if self._busy:
            _logger.info(
                '[SmartReconnect] reconnect request ignored; already busy reason=%s',
                str(reason)
            )
            return False

        if reason == 'manual-hotkey':
            return self._requestManualReconnect(reason, elapsed, ping)

        if DIAGNOSTIC_MODE or not AUTO_RECONNECT_ENABLED:
            _logger.warning(
                '[SmartReconnect] WOULD RECONNECT reason=%s elapsed=%s ping=%s',
                str(reason),
                str(elapsed),
                str(ping)
            )
            return False

        # Intentionally not implemented in v0.1. The first live build must prove
        # the detector before any connection-changing action is enabled.
        _logger.error(
            '[SmartReconnect] real reconnect path is disabled in v0.1 reason=%s',
            str(reason)
        )
        return False

    def _requestManualReconnect(self, reason, elapsed=None, ping=None):
        if DIAGNOSTIC_MODE:
            _logger.warning(
                '[SmartReconnect] manual reconnect enabled in diagnostic build reason=%s',
                str(reason)
            )

        self._busy = True
        startedAt = self._now()
        requested = False
        try:
            if not self._isActiveBattle():
                _logger.warning(
                    '[SmartReconnect] manual reconnect rejected; no active battle reason=%s',
                    str(reason)
                )
                return False

            if self._isReplay():
                _logger.warning(
                    '[SmartReconnect] manual reconnect rejected; replay is active reason=%s',
                    str(reason)
                )
                return False

            gameplayLogic = self._getGameplayLogic()
            if gameplayLogic is None:
                _logger.error(
                    '[SmartReconnect] manual reconnect rejected; IGameplayLogic unavailable reason=%s',
                    str(reason)
                )
                return False

            if not hasattr(gameplayLogic, 'goToLoginByDisconnectRQ'):
                _logger.error(
                    '[SmartReconnect] manual reconnect rejected; goToLoginByDisconnectRQ missing reason=%s',
                    str(reason)
                )
                return False

            arenaPeriod = self._arenaPeriod()
            _logger.warning(
                '[SmartReconnect] manual reconnect calling goToLoginByDisconnectRQ reason=%s elapsed=%s ping=%s arenaPeriod=%s startedAt=%.3f',
                str(reason),
                str(elapsed),
                str(ping),
                str(arenaPeriod),
                startedAt
            )
            gameplayLogic.goToLoginByDisconnectRQ()
            _logger.warning(
                '[SmartReconnect] manual reconnect disconnect requested reason=%s duration=%.3fs',
                str(reason),
                max(0.0, self._now() - startedAt)
            )
            requested = True
            return True
        except Exception:
            _logger.exception(
                '[SmartReconnect] manual reconnect failed reason=%s duration=%.3fs',
                str(reason),
                max(0.0, self._now() - startedAt)
            )
            return False
        finally:
            if not requested:
                self.clearBusy('manual-request-not-started')

    def clearBusy(self, reason='external-state-change'):
        if self._busy:
            _logger.info(
                '[SmartReconnect] reconnect guard released reason=%s',
                str(reason)
            )
        self._busy = False

    def _getGameplayLogic(self):
        if IGameplayLogic is None:
            return None
        try:
            return dependency.instance(IGameplayLogic)
        except Exception:
            _logger.exception('[SmartReconnect] failed to resolve IGameplayLogic')
            return None

    def _isReplay(self):
        try:
            return bool(BattleReplay.isPlaying())
        except Exception:
            _logger.exception('[SmartReconnect] failed to read replay state')
            return True

    def _isActiveBattle(self):
        try:
            player = BigWorld.player()
            return player is not None and hasattr(player, 'arena') and player.arena is not None
        except Exception:
            _logger.exception('[SmartReconnect] failed to read battle state')
            return False

    def _arenaPeriod(self):
        try:
            player = BigWorld.player()
            if player is None or not hasattr(player, 'arena') or player.arena is None:
                return None
            return getattr(player.arena, 'period', None)
        except Exception:
            _logger.exception('[SmartReconnect] failed to read arena period')
            return None

    def _now(self):
        try:
            return float(BigWorld.timeExact())
        except Exception:
            return 0.0
