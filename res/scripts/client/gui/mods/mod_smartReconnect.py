from .smartReconnect.SmartReconnect import SmartReconnect

_instance = None


def init():
    global _instance
    if _instance is None:
        _instance = SmartReconnect()


def fini():
    global _instance
    if _instance is not None:
        _instance.dispose()
        _instance = None
