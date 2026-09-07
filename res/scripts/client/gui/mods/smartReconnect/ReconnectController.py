import logging

from .Config import DIAGNOSTIC_MODE, AUTO_RECONNECT_ENABLED

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
