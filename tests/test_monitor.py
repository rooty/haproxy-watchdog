import unittest
from unittest.mock import patch, MagicMock
import time
from haproxy_backend_monitor import Monitor, Snap, WinCounters

class TestMonitor(unittest.TestCase):

    def setUp(self):
        self.cfg = MagicMock()
        self.cfg.alert_cooldown = 300
        self.cfg.critical_alert_cooldown = 120
        self.cfg.interval = 5
        self.cfg.window = 600
        self.cfg.flap_threshold = 3
        self.cfg.chkfail_threshold = 2
        self.cfg.chkdown_threshold = 1
        self.cfg.resp5xx_threshold = 5
        self.cfg.critical_flap_threshold = 6
        self.cfg.critical_chkfail_threshold = 4
        self.cfg.critical_chkdown_threshold = 2
        self.cfg.critical_5xx_threshold = 20
        self.cfg.telegram_bot_token = "test_token"
        self.cfg.telegram_chat_id = "test_chat"
        self.monitor = Monitor(self.cfg)

    def _set_warning_state(self, backend_name):
        self.monitor.backend_prev_level = {backend_name: 'none'}
        self.monitor.win_counters = {backend_name: WinCounters(flaps=5)}

    def _set_critical_state(self, backend_name):
        self.monitor.backend_prev_level = {backend_name: 'none'}
        self.monitor.win_counters = {backend_name: WinCounters(flaps=10)}

    @patch('haproxy_backend_monitor.urlopen')
    def test_send_telegram_respects_warning_cooldown(self, mock_urlopen):
        self._set_warning_state('backend1')

        # First warning
        self.monitor._maybe_alert({'backend1': Snap(status='UP')})
        self.assertEqual(mock_urlopen.call_count, 1)

        # Second call while cooldown active should not send
        self.monitor.last_alert_time['warning'] = time.monotonic()
        self.monitor._maybe_alert({'backend1': Snap(status='UP')})
        self.assertEqual(mock_urlopen.call_count, 1)

    @patch('haproxy_backend_monitor.urlopen')
    def test_send_telegram_respects_critical_cooldown(self, mock_urlopen):
        self._set_critical_state('backend2')

        # First critical
        self.monitor._maybe_alert({'backend2': Snap(status='DOWN')})
        self.assertEqual(mock_urlopen.call_count, 1)

        # Second call while cooldown active should not send
        self.monitor.last_alert_time['critical'] = time.monotonic()
        self.monitor._maybe_alert({'backend2': Snap(status='DOWN')})
        self.assertEqual(mock_urlopen.call_count, 1)

    @patch('haproxy_backend_monitor.urlopen')
    def test_send_telegram_after_cooldown_expired(self, mock_urlopen):
        self._set_warning_state('backend3')
        self.monitor.last_alert_time['warning'] = time.monotonic() - 400

        self.monitor._maybe_alert({'backend3': Snap(status='UP')})
        self.assertEqual(mock_urlopen.call_count, 1)

    @patch('haproxy_backend_monitor.urlopen')
    def test_no_telegram_if_not_configured(self, mock_urlopen):
        self.cfg.telegram_bot_token = ""
        self.cfg.telegram_chat_id = ""
        self._set_critical_state('backend4')

        self.monitor._maybe_alert({'backend4': Snap(status='DOWN')})
        self.assertEqual(mock_urlopen.call_count, 0)

if __name__ == '__main__':
    unittest.main()
