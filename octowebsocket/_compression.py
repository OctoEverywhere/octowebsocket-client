"""
_compression.py
websocket - WebSocket client library for Python

Implements helpers for handling the permessage-deflate WebSocket
extension defined in RFC 7692.
"""

from __future__ import annotations

import zlib
from typing import Dict, Optional

__all__ = ["PerMessageDeflate", "parse_permessage_deflate"]

# RFC 7692, Section 7.2.2 defines that a Z_SYNC_FLUSH adds 0x00 0x00 0xff 0xff
_ZLIB_FLUSH_MARKER = b"\x00\x00\xff\xff"


class PerMessageDeflate:
    """Stateful helper to apply permessage-deflate compression."""

    def __init__(
        self,
        server_no_context_takeover: bool = False,
        client_no_context_takeover: bool = False,
        server_max_window_bits: Optional[int] = None,
        client_max_window_bits: Optional[int] = None,
    ) -> None:
        self.server_no_context_takeover = server_no_context_takeover
        self.client_no_context_takeover = client_no_context_takeover
        self.server_max_window_bits = server_max_window_bits
        self.client_max_window_bits = client_max_window_bits

        self._compressor = self._create_compressobj()
        self._decompressor = self._create_decompressobj()

    def _create_compressobj(self) -> zlib.compressobj:
        wbits = -self.client_max_window_bits if self.client_max_window_bits else -zlib.MAX_WBITS
        return zlib.compressobj(wbits=wbits)

    def _create_decompressobj(self) -> zlib.decompressobj:
        wbits = -self.server_max_window_bits if self.server_max_window_bits else -zlib.MAX_WBITS
        return zlib.decompressobj(wbits=wbits)

    def reset_compressor(self) -> None:
        self._compressor = self._create_compressobj()

    def reset_decompressor(self) -> None:
        self._decompressor = self._create_decompressobj()

    def compress(self, payload: bytes) -> bytes:
        if self.client_no_context_takeover:
            self.reset_compressor()
        compressed = self._compressor.compress(payload)
        compressed += self._compressor.flush(zlib.Z_SYNC_FLUSH)
        # Strip the trailing marker per RFC 7692 Section 7.2.2.
        if compressed.endswith(_ZLIB_FLUSH_MARKER):
            compressed = compressed[: -len(_ZLIB_FLUSH_MARKER)]
        return compressed

    def decompress(self, payload: bytes) -> bytes:
        if self.server_no_context_takeover:
            self.reset_decompressor()
        # Append the marker before inflating per RFC 7692 Section 7.2.2.
        return self._decompressor.decompress(payload + _ZLIB_FLUSH_MARKER)


def parse_permessage_deflate(header_value: str) -> Optional[Dict[str, object]]:
    """Parse a Sec-WebSocket-Extensions header for permessage-deflate options."""

    if not header_value:
        return None

    for extension in header_value.split(","):
        params = [token.strip() for token in extension.split(";") if token.strip()]
        if not params:
            continue
        if params[0].lower() != "permessage-deflate":
            continue

        options: Dict[str, object] = {}
        for token in params[1:]:
            if "=" in token:
                key, value = token.split("=", 1)
                value = value.strip().strip('"')
                if value.isdigit():
                    options[key.strip()] = int(value)
                else:
                    options[key.strip()] = value
            else:
                options[token] = True
        return options

    return None
