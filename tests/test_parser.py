import unittest
from haproxy_backend_monitor import build_parser

class TestParser(unittest.TestCase):

    def test_default_cooldowns(self):
        parser = build_parser()
        args = parser.parse_args([])
        self.assertEqual(args.alert_cooldown, 300)
        self.assertEqual(args.critical_alert_cooldown, 120)
    
    def test_custom_cooldowns(self):
        parser = build_parser()
        args = parser.parse_args(['--alert-cooldown', '500', '--critical-alert-cooldown', '200'])
        self.assertEqual(args.alert_cooldown, 500)
        self.assertEqual(args.critical_alert_cooldown, 200)

if __name__ == '__main__':
    unittest.main()
