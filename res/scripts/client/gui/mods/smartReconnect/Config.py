VERSION = '{{VERSION}}'

# Keep the first live build safe: detector only, no connection-changing action.
DIAGNOSTIC_MODE = True
AUTO_RECONNECT_ENABLED = False
MANUAL_HOTKEY_ENABLED = True

POLL_INTERVAL = 0.2
LAG_GRACE_PERIOD = 3.0
LOGIN_WAIT_TIMEOUT = 15.0
WGC_LOGIN_WAIT_TIMEOUT = 30.0
RETURN_TO_GAME_TIMEOUT = 30.0
COOLDOWN_AFTER_FAILURE = 45.0
STABLE_GREEN_SAMPLES = 3
STABLE_GREEN_MAX_PING = 500
STATE_POLL_INTERVAL = 0.5

# Leave empty to use the current/selected server from the login manager.
SERVER_NAME = None
