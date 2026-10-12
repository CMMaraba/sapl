import unittest

from sapl.modern_components.client_ip import client_ip, parse_ip


class ClientIpTests(unittest.TestCase):
    def test_header_priority_is_preserved(self):
        meta = {
            "HTTP_X_FORWARDED_FOR": "203.0.113.7, 10.3.150.20",
            "HTTP_X_REAL_IP": "198.51.100.1",
            "REMOTE_ADDR": "127.0.0.1",
        }
        self.assertEqual(client_ip(meta), "203.0.113.7")
        del meta["HTTP_X_FORWARDED_FOR"]
        self.assertEqual(client_ip(meta), "198.51.100.1")
        del meta["HTTP_X_REAL_IP"]
        self.assertEqual(client_ip(meta), "127.0.0.1")
        self.assertEqual(client_ip({}), "0.0.0.0")

    def test_masks_match_former_ratelimit_defaults(self):
        self.assertEqual(client_ip({"REMOTE_ADDR": "2001:db8:1:2:3:4:5:6"}), "2001:db8:1:2::")
        self.assertEqual(client_ip({"REMOTE_ADDR": "203.0.113.7"}, ipv4_mask=24), "203.0.113.0")

    def test_malformed_headers_never_raise(self):
        # Values that made the former code (and django-ratelimit 3.0.1) raise ValueError.
        cases = {
            "unknown": "127.0.0.1",
            "1.2.3.4:5678": "1.2.3.4",
            " 1.2.3.4": "1.2.3.4",
            "1.2.3.4 , 5.6.7.8": "1.2.3.4",
            "[::1]": "::",
            "[2001:db8::1]:80": "2001:db8::",
            "fe80::1%eth0": "fe80::",
            "unknown, 5.6.7.8": "5.6.7.8",
            "not-an-ip, also-bad": "127.0.0.1",
            ",": "127.0.0.1",
        }
        for header, expected in cases.items():
            with self.subTest(header=header):
                meta = {"HTTP_X_FORWARDED_FOR": header, "REMOTE_ADDR": "127.0.0.1"}
                self.assertEqual(client_ip(meta), expected)

    def test_invalid_real_ip_and_remote_addr_fall_back(self):
        self.assertEqual(
            client_ip({"HTTP_X_REAL_IP": "a,b", "REMOTE_ADDR": "192.0.2.9"}), "192.0.2.9"
        )
        self.assertEqual(client_ip({"REMOTE_ADDR": ""}), "0.0.0.0")
        self.assertEqual(client_ip({"REMOTE_ADDR": "garbage"}), "0.0.0.0")

    def test_parse_ip_rejects_unterminated_brackets(self):
        self.assertIsNone(parse_ip("[2001:db8::1"))
        self.assertIsNone(parse_ip(None))


if __name__ == "__main__":
    unittest.main()
