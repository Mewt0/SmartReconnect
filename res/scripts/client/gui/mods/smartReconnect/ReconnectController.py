import logging

import BigWorld
import BattleReplay

from helpers import dependency

from .Config import (
    DIAGNOSTIC_MODE,
    AUTO_RECONNECT_ENABLED,
    LOGIN_WAIT_TIMEOUT,
    WGC_LOGIN_WAIT_TIMEOUT,
    RETURN_TO_GAME_TIMEOUT,
    COOLDOWN_AFTER_FAILURE,
    STATE_POLL_INTERVAL,
    SERVER_NAME,
)

try:
    from skeletons.gameplay import IGameplayLogic
except Exception:
    IGameplayLogic = None
try:
    from skeletons.gameplay import GameplayStateID
except Exception:
    GameplayStateID = None
try:
    from skeletons.gui_login_manager import ILoginManager
except Exception:
    try:
        from skeletons.login import ILoginManager
    except Exception:
        ILoginManager = None

_logger = logging.getLogger('SmartReconnect')

STATE_IDLE = 'IDLE'
STATE_RED_DETECTED = 'RED_DETECTED'
STATE_THRESHOLD_REACHED = 'THRESHOLD_REACHED'
STATE_DISCONNECT_REQUESTED = 'DISCONNECT_REQUESTED'
STATE_LOGIN_WAIT = 'LOGIN_WAIT'
STATE_WGC_LOGIN_REQUESTED = 'WGC_LOGIN_REQUESTED'
STATE_WGC_LOGIN_WAIT = 'WGC_LOGIN_WAIT'
STATE_RETURNING_TO_GAME = 'RETURNING_TO_GAME'
STATE_RECOVERED = 'RECOVERED'
STATE_FAILED = 'FAILED'
STATE_ABORTED = 'ABORTED'
STATE_COOLDOWN = 'COOLDOWN'


class ReconnectController(object):

    def __init__(self):
        self._state = STATE_IDLE
        self._attemptID = 0
        self._attemptStartedAt = None
        self._stateStartedAt = None
        self._source = None
        self._cooldownUntil = 0.0
        self._callbackID = None

    @property
    def busy(self):
        return self._state not in (
            STATE_IDLE,
            STATE_RECOVERED,
            STATE_FAILED,
            STATE_ABORTED,
            STATE_COOLDOWN,
        )

    @property
    def state(self):
        return self._state

    @property
    def attemptID(self):
        return self._attemptID

    def requestReconnect(self, reason, elapsed=None, ping=None):
        now = self._now()
        if self.busy:
            _logger.info(
                '[SmartReconnect] reconnect request ignored; already busy attempt=%s state=%s reason=%s',
                str(self._attemptID),
                str(self._state),
                str(reason)
            )
            return False

        if self._state == STATE_COOLDOWN and now < self._cooldownUntil:
            _logger.warning(
                '[SmartReconnect] reconnect request ignored; cooldown active remaining=%.1fs reason=%s',
                max(0.0, self._cooldownUntil - now),
                str(reason)
            )
            return False

        if reason != 'manual-hotkey' and (DIAGNOSTIC_MODE or not AUTO_RECONNECT_ENABLED):
            _logger.warning(
                '[SmartReconnect] WOULD RECONNECT reason=%s elapsed=%s ping=%s',
                str(reason),
                str(elapsed),
                str(ping)
            )
            return False

        return self._startAttempt(reason, elapsed, ping)

    def clearBusy(self, reason='external-state-change'):
        self._cancelStateCheck()
        if self._state != STATE_IDLE:
            self._transition(STATE_IDLE, reason)

    def onBattleEntered(self):
        if self._state == STATE_RETURNING_TO_GAME:
            self._recover('battle-entered')

    def onBattleExited(self):
        if self.busy:
            self._abort('battle-ended')

    def _startAttempt(self, reason, elapsed=None, ping=None):
        if DIAGNOSTIC_MODE:
            _logger.warning(
                '[SmartReconnect] reconnect path enabled in diagnostic build reason=%s',
                str(reason)
            )

        self._attemptID += 1
        self._source = reason
        self._attemptStartedAt = self._now()
        self._transition(STATE_RED_DETECTED if reason == 'auto-lag' else STATE_THRESHOLD_REACHED, reason)
        if reason == 'auto-lag':
            self._transition(
                STATE_THRESHOLD_REACHED,
                'red-threshold elapsed=%s ping=%s' % (str(elapsed), str(ping))
            )

        try:
            rejectReason = self._preflightRejectReason()
            if rejectReason is not None:
                self._abort(rejectReason)
                return False

            gameplayLogic = self._getGameplayLogic()
            if gameplayLogic is None:
                self._fail('IGameplayLogic unavailable')
                return False
            if not hasattr(gameplayLogic, 'goToLoginByDisconnectRQ'):
                self._fail('goToLoginByDisconnectRQ missing')
                return False

            arenaPeriod = self._arenaPeriod()
            self._transition(STATE_DISCONNECT_REQUESTED, 'request-stock-disconnect')
            _logger.warning(
                '[SmartReconnect] attempt=%s source=%s calling goToLoginByDisconnectRQ elapsed=%s ping=%s arenaPeriod=%s startedAt=%.3f',
                str(self._attemptID),
                str(reason),
                str(elapsed),
                str(ping),
                str(arenaPeriod),
                self._attemptStartedAt
            )
            gameplayLogic.goToLoginByDisconnectRQ()
            _logger.warning(
                '[SmartReconnect] attempt=%s source=%s disconnect requested duration=%.3fs',
                str(self._attemptID),
                str(reason),
                self._duration()
            )
            self._transition(STATE_LOGIN_WAIT, 'disconnect-requested')
            self._scheduleStateCheck(STATE_POLL_INTERVAL)
            return True
        except Exception:
            _logger.exception(
                '[SmartReconnect] attempt=%s reconnect failed source=%s duration=%.3fs',
                str(self._attemptID),
                str(reason),
                self._duration()
            )
            self._fail('exception during disconnect request')
            return False

    def _tickState(self):
        self._callbackID = None
        try:
            if self._state == STATE_LOGIN_WAIT:
                self._tickLoginWait()
            elif self._state == STATE_WGC_LOGIN_WAIT:
                self._tickWgcLoginWait()
            elif self._state == STATE_RETURNING_TO_GAME:
                self._tickReturnToGame()
        except Exception:
            _logger.exception(
                '[SmartReconnect] attempt=%s state tick failed state=%s',
                str(self._attemptID),
                str(self._state)
            )
            self._fail('state tick exception')

    def _tickLoginWait(self):
        if self._stateElapsed() > LOGIN_WAIT_TIMEOUT:
            self._fail('LOGIN timeout')
            return
        if self._isLoginState():
            self._transition(STATE_WGC_LOGIN_REQUESTED, 'login-reached')
            self._requestWgcLogin()
            return
        self._scheduleStateCheck(STATE_POLL_INTERVAL)

    def _requestWgcLogin(self):
        loginManager = self._getLoginManager()
        if loginManager is None:
            self._fail('ILoginManager unavailable')
            return
        if not hasattr(loginManager, 'tryWgcLogin'):
            self._fail('tryWgcLogin missing')
            return

        serverName = self._serverName(loginManager)
        if serverName is None:
            self._fail('server name unavailable')
            return

        _logger.warning(
            '[SmartReconnect] attempt=%s source=%s calling tryWgcLogin server=%s duration=%.3fs',
            str(self._attemptID),
            str(self._source),
            str(serverName),
            self._duration()
        )
        try:
            loginManager.tryWgcLogin(serverName)
        except Exception:
            _logger.exception(
                '[SmartReconnect] attempt=%s tryWgcLogin failed server=%s',
                str(self._attemptID),
                str(serverName)
            )
            self._fail('tryWgcLogin exception')
            return
        self._transition(STATE_WGC_LOGIN_WAIT, 'wgc-login-requested')
        self._scheduleStateCheck(STATE_POLL_INTERVAL)

    def _tickWgcLoginWait(self):
        if self._stateElapsed() > WGC_LOGIN_WAIT_TIMEOUT:
            self._fail('WGC login timeout')
            return
        if self._isActiveBattle():
            self._recover('battle-restored')
            return
        if not self._isLoginState():
            self._transition(STATE_RETURNING_TO_GAME, 'left-login')
            self._scheduleStateCheck(STATE_POLL_INTERVAL)
            return
        self._scheduleStateCheck(STATE_POLL_INTERVAL)

    def _tickReturnToGame(self):
        if self._stateElapsed() > RETURN_TO_GAME_TIMEOUT:
            self._fail('return-to-game timeout')
            return
        if self._isActiveBattle():
            self._recover('battle-restored')
            return
        self._scheduleStateCheck(STATE_POLL_INTERVAL)

    def _recover(self, reason):
        self._cancelStateCheck()
        self._transition(STATE_RECOVERED, reason)
        _logger.warning(
            '[SmartReconnect] attempt=%s recovered duration=%.3fs',
            str(self._attemptID),
            self._duration()
        )
        self.clearBusy('recovered')

    def _fail(self, reason):
        self._cancelStateCheck()
        self._transition(STATE_FAILED, reason)
        self._cooldown(reason)

    def _abort(self, reason):
        self._cancelStateCheck()
        self._transition(STATE_ABORTED, reason)
        self.clearBusy('aborted')

    def _cooldown(self, reason):
        self._cooldownUntil = self._now() + COOLDOWN_AFTER_FAILURE
        self._transition(STATE_COOLDOWN, reason)
        _logger.warning(
            '[SmartReconnect] attempt=%s cooldown %.1fs reason=%s',
            str(self._attemptID),
            COOLDOWN_AFTER_FAILURE,
            str(reason)
        )

    def _preflightRejectReason(self):
        if not self._isActiveBattle():
            return 'no active battle'
        if self._isReplay():
            return 'replay is active'
        return None

    def _getGameplayLogic(self):
        if IGameplayLogic is None:
            return None
        try:
            return dependency.instance(IGameplayLogic)
        except Exception:
            _logger.exception('[SmartReconnect] failed to resolve IGameplayLogic')
            return None

    def _getLoginManager(self):
        if ILoginManager is None:
            return None
        try:
            return dependency.instance(ILoginManager)
        except Exception:
            _logger.exception('[SmartReconnect] failed to resolve ILoginManager')
            return None

    def _isLoginState(self):
        gameplayLogic = self._getGameplayLogic()
        if gameplayLogic is None:
            return False
        currentState = None
        for name in ('state', 'currentState', 'gameplayStateID'):
            if hasattr(gameplayLogic, name):
                try:
                    currentState = getattr(gameplayLogic, name)
                    break
                except Exception:
                    pass
        for method in ('getState', 'getCurrentState', 'getStateID'):
            if currentState is None and hasattr(gameplayLogic, method):
                try:
                    currentState = getattr(gameplayLogic, method)()
                    break
                except Exception:
                    pass
        loginState = getattr(GameplayStateID, 'LOGIN', 'LOGIN') if GameplayStateID is not None else 'LOGIN'
        return currentState == loginState or str(currentState) == str(loginState)

    def _serverName(self, loginManager):
        if SERVER_NAME:
            return SERVER_NAME
        for method in ('getSelectedServerName', 'getCurrentServerName', 'getServerName'):
            if hasattr(loginManager, method):
                try:
                    value = getattr(loginManager, method)()
                    if value:
                        return value
                except Exception:
                    _logger.exception('[SmartReconnect] failed to read server through %s', method)
        for name in ('serverName', 'currentServerName', 'selectedServerName'):
            if hasattr(loginManager, name):
                try:
                    value = getattr(loginManager, name)
                    if value:
                        return value
                except Exception:
                    pass
        return None

    def _scheduleStateCheck(self, delay):
        self._cancelStateCheck()
        self._callbackID = BigWorld.callback(delay, self._tickState)

    def _cancelStateCheck(self):
        if self._callbackID is None:
            return
        try:
            BigWorld.cancelCallback(self._callbackID)
        except Exception:
            _logger.exception('[SmartReconnect] failed to cancel state callback')
        self._callbackID = None

    def _transition(self, nextState, reason):
        previous = self._state
        self._state = nextState
        self._stateStartedAt = self._now()
        _logger.warning(
            '[SmartReconnect] attempt=%s source=%s state %s -> %s reason=%s duration=%.3fs',
            str(self._attemptID),
            str(self._source),
            str(previous),
            str(nextState),
            str(reason),
            self._duration()
        )

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

    def _duration(self):
        if self._attemptStartedAt is None:
            return 0.0
        return max(0.0, self._now() - self._attemptStartedAt)

    def _stateElapsed(self):
        if self._stateStartedAt is None:
            return 0.0
        return max(0.0, self._now() - self._stateStartedAt)
