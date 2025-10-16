import unittest

from octowebsocket._compression import PerMessageDeflate, parse_permessage_deflate


class TestPerMessageDeflate(unittest.TestCase):
    def test_compress_roundtrip(self):
        compressor = PerMessageDeflate()
        payload = b"hello world" * 4
        compressed = compressor.compress(payload)
        self.assertNotEqual(compressed, payload)
        inflated = compressor.decompress(compressed)
        self.assertEqual(inflated, payload)

    def test_parse_header(self):
        header = (
            "permessage-deflate; server_no_context_takeover; "
            "client_no_context_takeover; server_max_window_bits=12; "
            "client_max_window_bits=10"
        )
        params = parse_permessage_deflate(header)
        self.assertIsNotNone(params)
        assert params is not None
        self.assertTrue(params.get("server_no_context_takeover"))
        self.assertTrue(params.get("client_no_context_takeover"))
        self.assertEqual(params.get("server_max_window_bits"), 12)
        self.assertEqual(params.get("client_max_window_bits"), 10)

    def test_parse_multiple_extensions(self):
        header = (
            "permessage-deflate; server_no_context_takeover, "
            "foo; bar=baz"
        )
        params = parse_permessage_deflate(header)
        self.assertIsNotNone(params)
        assert params is not None
        self.assertTrue(params.get("server_no_context_takeover"))


if __name__ == "__main__":
    unittest.main()
