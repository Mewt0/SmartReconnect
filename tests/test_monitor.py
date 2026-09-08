"""Offline behavioral tests; no WoT installation or network access required."""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)),
                             'res', 'scripts', 'client', 'gui', 'mods'))

def module(name):
    value = types.ModuleType(name)
    sys.modules[name] = value
    return value

bw = module('BigWorld')
replay = module('BattleReplay')
helpers = module('helpers')
module('skeletons')
module('skeletons.connection_mgr').IConnectionManager = object
module('skeletons.gameplay').IGameplayLogic = object
helpers.dependency = types.ModuleType('dependency')
helpers.dependency.instance = lambda interface: None

from smartReconnect.ConnectionMonitor import ConnectionMonitor
from smartReconnect.ReconnectController import ReconnectController


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.requests = []
        self.pending = {}
        self.serial = 0
        self.now = 0.0
        self.red = True
        self.playing = False
        self.failed = False
        self.connected = True
        self.player = type('Player', (), {'arena': type('Arena', (), {'period': 3})()})()
        bw.callback = self.schedule
        bw.cancelCallback = lambda token: self.pending.pop(token)
        bw.player = lambda: self.player
        bw.timeExact = lambda: self.now
        bw.statPing = lambda: 0.1
        bw.statLagDetected = self.signal
        replay.isPlaying = lambda: self.playing
        self.monitor = ConnectionMonitor(lambda *args: self.requests.append(args))
        self.monitor._connectionMgr = self
        self.monitor.start()

    def isConnected(self):
        return self.connected

    def signal(self):
        if self.failed:
            raise RuntimeError('unreadable sample')
        return self.red

    def schedule(self, delay, callback):
        self.serial += 1
        self.pending[self.serial] = callback
        return self.serial

    def tick(self, now):
        self.now = now
        self.assertEqual(len(self.pending), 1)
        callback = self.pending.pop(next(iter(self.pending)))
        callback()

    def test_sustained_red_triggers_once(self):
        for now in (0, 1, 2.9):
            self.tick(now)
        self.assertEqual(self.requests, [])
        for now in (3, 4, 10, 30):
            self.tick(now)
        self.assertEqual(len(self.requests), 1)

    def test_green_resets_short_spike_and_rearms(self):
        self.tick(0)
        self.red = False
        self.tick(2.9)
        self.red = True
        self.tick(3)
        self.tick(5.9)
        self.assertEqual(self.requests, [])
        self.tick(6)
        self.red = False
        self.tick(7)
        self.red = True
        self.tick(8)
        self.tick(11)
        self.assertEqual(len(self.requests), 2)

    def test_failed_sample_requires_fresh_window(self):
        self.tick(0)
        self.failed = True
        self.tick(2)
        self.failed = False
        self.tick(3)
        self.tick(5.9)
        self.assertEqual(self.requests, [])
        self.tick(6)
        self.assertEqual(len(self.requests), 1)

    def test_replay_is_inert(self):
        self.playing = True
        for now in (0, 3, 10):
            self.tick(now)
        self.assertEqual(self.requests, [])

    def test_error_after_trigger_does_not_rearm(self):
        self.tick(0)
        self.tick(3)
        self.failed = True
        self.tick(4)
        self.failed = False
        self.tick(5)
        self.tick(8)
        self.assertEqual(len(self.requests), 1)
        self.red = False
        self.tick(9)
        self.red = True
        self.tick(10)
        self.tick(13)
        self.assertEqual(len(self.requests), 2)

    def test_green_at_threshold_does_not_trigger(self):
        self.tick(0)
        self.red = False
        self.tick(3)
        self.assertEqual(self.requests, [])

    def test_missing_arena_resets_window(self):
        self.tick(0)
        player = self.player
        self.player = None
        self.tick(2)
        self.player = player
        self.tick(3)
        self.assertEqual(self.requests, [])

    def test_start_stop_and_restart(self):
        self.monitor.start()
        self.tick(0)
        self.monitor.stop()
        self.assertEqual(self.pending, {})
        self.monitor.start()
        self.tick(10)
        self.assertEqual(self.requests, [])
        self.tick(13)
        self.assertEqual(len(self.requests), 1)

    def test_disconnected_state_still_diagnostic(self):
        self.connected = False
        self.tick(0)
        self.tick(3)
        self.assertEqual(len(self.requests), 1)


class GameplayLogicStub(object):
    def __init__(self):
        self.calls = 0
        self.raise_on_call = False

    def goToLoginByDisconnectRQ(self):
        self.calls += 1
        if self.raise_on_call:
            raise RuntimeError('disconnect failed')


class ReconnectControllerTests(unittest.TestCase):
    def setUp(self):
        self.now = 10.0
        self.playing = False
        self.player = type('Player', (), {'arena': type('Arena', (), {'period': 3})()})()
        self.gameplay = GameplayLogicStub()
        bw.player = lambda: self.player
        bw.timeExact = lambda: self.now
        replay.isPlaying = lambda: self.playing
        helpers.dependency.instance = lambda interface: self.gameplay
        self.controller = ReconnectController()

    def test_manual_hotkey_calls_stock_disconnect_once_and_latches_busy(self):
        self.assertTrue(self.controller.requestReconnect('manual-hotkey'))
        self.assertEqual(self.gameplay.calls, 1)
        self.assertTrue(self.controller.busy)

        self.assertFalse(self.controller.requestReconnect('manual-hotkey'))
        self.assertEqual(self.gameplay.calls, 1)

    def test_manual_guard_can_be_released_by_lifecycle(self):
        self.assertTrue(self.controller.requestReconnect('manual-hotkey'))
        self.controller.clearBusy('login-reached')
        self.assertFalse(self.controller.busy)
        self.assertTrue(self.controller.requestReconnect('manual-hotkey'))
        self.assertEqual(self.gameplay.calls, 2)

    def test_manual_rejects_without_active_battle_and_releases_guard(self):
        self.player = None
        self.assertFalse(self.controller.requestReconnect('manual-hotkey'))
        self.assertFalse(self.controller.busy)
        self.assertEqual(self.gameplay.calls, 0)

    def test_manual_rejects_replay_and_releases_guard(self):
        self.playing = True
        self.assertFalse(self.controller.requestReconnect('manual-hotkey'))
        self.assertFalse(self.controller.busy)
        self.assertEqual(self.gameplay.calls, 0)

    def test_manual_rejects_missing_gameplay_logic_and_releases_guard(self):
        helpers.dependency.instance = lambda interface: None
        self.assertFalse(self.controller.requestReconnect('manual-hotkey'))
        self.assertFalse(self.controller.busy)
        self.assertEqual(self.gameplay.calls, 0)

    def test_manual_call_exception_releases_guard(self):
        self.gameplay.raise_on_call = True
        self.assertFalse(self.controller.requestReconnect('manual-hotkey'))
        self.assertFalse(self.controller.busy)
        self.assertEqual(self.gameplay.calls, 1)

    def test_auto_lag_remains_diagnostic_only(self):
        self.assertFalse(self.controller.requestReconnect('auto-lag', 3.1, 999))
        self.assertFalse(self.controller.busy)
        self.assertEqual(self.gameplay.calls, 0)


if __name__ == '__main__':
    unittest.main()
