"""Verify that the test suite rejects broken callback timing (Python 2.7+)."""
from __future__ import print_function
import logging
import unittest
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
import test_monitor as tests


def run():
    logging.disable(logging.CRITICAL)
    mutations = (
        (tests.ConnectionMonitor, '_schedule', tests.MonitorTests,
         'test_sustained_red_triggers_once'),
        (tests.ReconnectController, '_scheduleStateCheck', tests.ReconnectControllerTests,
         'test_login_state_requests_wgc_login_once'),
    )
    for owner, method, case, name in mutations:
        original = getattr(owner, method)
        def delayed(self, delay=None):
            return original(self, 3600.0)
        setattr(owner, method, delayed)
        try:
            result = unittest.TextTestRunner(stream=StringIO()).run(
                unittest.TestSuite([case(name)]))
        finally:
            setattr(owner, method, original)
        if result.errors or len(result.failures) != 1:
            raise AssertionError('Mutation was not rejected cleanly: ' + method)
        if 'callback is not due yet' not in result.failures[0][1]:
            raise AssertionError('Mutation failed for the wrong reason: ' + method)
        print('Rejected one-hour callback mutation: ' + method)


if __name__ == '__main__':
    run()
