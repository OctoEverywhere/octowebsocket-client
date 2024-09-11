import array
import os
import struct
import sys
from threading import Lock
from typing import Callable, Optional, Union

from ._exceptions import WebSocketPayloadException, WebSocketProtocolException
from ._utils import validate_utf8

"""
_abnf.py
websocket - WebSocket client library for Python

Copyright 2024 engn33r

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

try:
    # If wsaccel is available, use compiled routines to mask data.
    # wsaccel only provides around a 10% speed boost compared
    # to the websocket-client _mask() implementation.
    # Note that wsaccel is unmaintained.
    from wsaccel.xormask import XorMaskerSimple

    def _mask(mask_value: array.array, data_value: array.array) -> bytes:
        mask_result: bytes = XorMaskerSimple(mask_value).process(data_value)
        return mask_result

except ImportError:
    # wsaccel is not available, use websocket-client _mask()
    native_byteorder = sys.byteorder

    def _mask(mask_value: array.array, data_value: array.array) -> bytes:
        datalen = len(data_value)
        int_data_value = int.from_bytes(data_value, native_byteorder)
        int_mask_value = int.from_bytes(
            mask_value * (datalen // 4) + mask_value[: datalen % 4], native_byteorder
        )
        return (int_data_value ^ int_mask_value).to_bytes(datalen, native_byteorder)


__all__ = [
    "ABNF",
    "continuous_frame",
    "frame_buffer",
    "STATUS_NORMAL",
    "STATUS_GOING_AWAY",
    "STATUS_PROTOCOL_ERROR",
    "STATUS_UNSUPPORTED_DATA_TYPE",
    "STATUS_STATUS_NOT_AVAILABLE",
    "STATUS_ABNORMAL_CLOSED",
    "STATUS_INVALID_PAYLOAD",
    "STATUS_POLICY_VIOLATION",
    "STATUS_MESSAGE_TOO_BIG",
    "STATUS_INVALID_EXTENSION",
    "STATUS_UNEXPECTED_CONDITION",
    "STATUS_BAD_GATEWAY",
    "STATUS_TLS_HANDSHAKE_ERROR",
]

# closing frame status codes.
STATUS_NORMAL = 1000
STATUS_GOING_AWAY = 1001
STATUS_PROTOCOL_ERROR = 1002
STATUS_UNSUPPORTED_DATA_TYPE = 1003
STATUS_STATUS_NOT_AVAILABLE = 1005
STATUS_ABNORMAL_CLOSED = 1006
STATUS_INVALID_PAYLOAD = 1007
STATUS_POLICY_VIOLATION = 1008
STATUS_MESSAGE_TOO_BIG = 1009
STATUS_INVALID_EXTENSION = 1010
STATUS_UNEXPECTED_CONDITION = 1011
STATUS_SERVICE_RESTART = 1012
STATUS_TRY_AGAIN_LATER = 1013
STATUS_BAD_GATEWAY = 1014
STATUS_TLS_HANDSHAKE_ERROR = 1015

VALID_CLOSE_STATUS = (
    STATUS_NORMAL,
    STATUS_GOING_AWAY,
    STATUS_PROTOCOL_ERROR,
    STATUS_UNSUPPORTED_DATA_TYPE,
    STATUS_INVALID_PAYLOAD,
    STATUS_POLICY_VIOLATION,
    STATUS_MESSAGE_TOO_BIG,
    STATUS_INVALID_EXTENSION,
    STATUS_UNEXPECTED_CONDITION,
    STATUS_SERVICE_RESTART,
    STATUS_TRY_AGAIN_LATER,
    STATUS_BAD_GATEWAY,
)


class ABNF:
    """
    ABNF frame class.
    See http://tools.ietf.org/html/rfc5234
    and http://tools.ietf.org/html/rfc6455#section-5.2
    """

    # operation code values.
    OPCODE_CONT = 0x0
    OPCODE_TEXT = 0x1
    OPCODE_BINARY = 0x2
    OPCODE_CLOSE = 0x8
    OPCODE_PING = 0x9
    OPCODE_PONG = 0xA

    # available operation code value tuple
    OPCODES = (
        OPCODE_CONT,
        OPCODE_TEXT,
        OPCODE_BINARY,
        OPCODE_CLOSE,
        OPCODE_PING,
        OPCODE_PONG,
    )

    # opcode human readable string
    OPCODE_MAP = {
        OPCODE_CONT: "cont",
        OPCODE_TEXT: "text",
        OPCODE_BINARY: "binary",
        OPCODE_CLOSE: "close",
        OPCODE_PING: "ping",
        OPCODE_PONG: "pong",
    }

    # data length threshold.
    LENGTH_7 = 0x7E
    LENGTH_16 = 1 << 16
    LENGTH_63 = 1 << 63

    def __init__(
        self,
        fin: int = 0,
        rsv1: int = 0,
        rsv2: int = 0,
        rsv3: int = 0,
        opcode: int = OPCODE_TEXT,
        mask_value: int = 1,
        data: Union[str, bytes, None] = "",
        data_start_offset_bytes: Union[int, None] = None,
        data_msg_length_bytes: Union[int, None] = None
    ) -> None:
        """
        Constructor for ABNF. Please check RFC for arguments.
        """
        self.fin = fin
        self.rsv1 = rsv1
        self.rsv2 = rsv2
        self.rsv3 = rsv3
        self.opcode = opcode
        self.mask_value = mask_value
        if data is None:
            data = ""
        self.data = data
        self.data_start_offset_bytes = 0 if data_start_offset_bytes is None else data_start_offset_bytes
        self.data_msg_length_bytes = len(self.data) if data_msg_length_bytes is None else data_msg_length_bytes
        self.get_mask_key = os.urandom

    def validate(self, skip_utf8_validation: bool = False) -> None:
        """
        Validate the ABNF frame.

        Parameters
        ----------
        skip_utf8_validation: skip utf8 validation.
        """
        if self.rsv1 or self.rsv2 or self.rsv3:
            raise WebSocketProtocolException("rsv is not implemented, yet")

        if self.opcode not in ABNF.OPCODES:
            raise WebSocketProtocolException("Invalid opcode %r", self.opcode)

        if self.opcode == ABNF.OPCODE_PING and not self.fin:
            raise WebSocketProtocolException("Invalid ping frame.")

        if self.opcode == ABNF.OPCODE_CLOSE:
            l = len(self.data)
            if not l:
                return
            if l == 1 or l >= 126:
                raise WebSocketProtocolException("Invalid close frame.")
            if l > 2 and not skip_utf8_validation and not validate_utf8(self.data[2:]):
                raise WebSocketProtocolException("Invalid close frame.")

            code = 256 * int(self.data[0]) + int(self.data[1])
            if not self._is_valid_close_status(code):
                raise WebSocketProtocolException("Invalid close opcode %r", code)

    @staticmethod
    def _is_valid_close_status(code: int) -> bool:
        return code in VALID_CLOSE_STATUS or (3000 <= code < 5000)

    def __str__(self) -> str:
        return f"fin={self.fin} opcode={self.opcode} data={self.data}"

    @staticmethod
    def create_frame(data: Union[bytes, str], opcode: int, fin: int = 1, use_frame_mask: bool = True, data_start_offset_bytes: Union[int, None] = None, data_msg_length_bytes: Union[int, None] = None) -> "ABNF":
        """
        Create frame to send text, binary and other data.

        Parameters
        ----------
        data: str
            data to send. This is string value(byte array).
            If opcode is OPCODE_TEXT and this value is unicode,
            data value is converted into unicode string, automatically.
        opcode: int
            operation code. please see OPCODE_MAP.
        fin: int
            fin flag. if set to 0, create continue fragmentation.
        use_frame_mask: bool
            Whether to mask the data in the websocket frame sent. Default is True.
        """
        if opcode == ABNF.OPCODE_TEXT and isinstance(data, str):
            if data_start_offset_bytes is not None:
                raise ValueError("data_start_offset_bytes must be None if data is str")
            data = data.encode("utf-8")
            data_start_offset_bytes = None
            data_msg_length_bytes = None

        # OctoChange
        # From the websocket rfc, a mask must be set if send data from client.
        # However, computing the mask adds a measurable amount of overhead and is unnecessary if SSL is being used to secure the connection.
        # Most modern web servers will accept unmasked data when sent over SSL, thus making this optional can help performance.
        mask_value = 1 if use_frame_mask else 0
        return ABNF(fin, 0, 0, 0, opcode, mask_value, data, data_start_offset_bytes, data_msg_length_bytes)

    def format(self) -> memoryview:
        """
        Format this object to string(byte array) to send data to server.
        """
        if any(x not in (0, 1) for x in [self.fin, self.rsv1, self.rsv2, self.rsv3]):
            raise ValueError("not 0 or 1")
        if self.opcode not in ABNF.OPCODES:
            raise ValueError("Invalid OPCODE")

        if isinstance(self.data, str):
            self.data = self.data.encode("utf-8")
            self.data_start_offset_bytes = 0
            self.data_msg_length_bytes = len(self.data)

        if self.data_msg_length_bytes >= ABNF.LENGTH_63:
            raise ValueError("data is too long")

        frame_header = chr(
            self.fin << 7
            | self.rsv1 << 6
            | self.rsv2 << 5
            | self.rsv3 << 4
            | self.opcode
        ).encode("latin-1")
        if self.data_msg_length_bytes < ABNF.LENGTH_7:
            frame_header += chr(self.mask_value << 7 | self.data_msg_length_bytes).encode("latin-1")
        elif self.data_msg_length_bytes < ABNF.LENGTH_16:
            frame_header += chr(self.mask_value << 7 | 0x7E).encode("latin-1")
            frame_header += struct.pack("!H", self.data_msg_length_bytes)
        else:
            frame_header += chr(self.mask_value << 7 | 0x7F).encode("latin-1")
            frame_header += struct.pack("!Q", self.data_msg_length_bytes)

        # If the data needs to be masked, mask it. There's no way to avoid copying the data here.
        if self.mask_value:
            mask_key = self.get_mask_key(4)
            self.data = self._get_masked(mask_key)
            self.data_start_offset_bytes = 0
            self.data_msg_length_bytes = len(self.data)

        # If there'e enough space in the data buffer, write the frame header there without copying.
        frame_header_len = len(frame_header)
        if frame_header_len < self.data_start_offset_bytes:
            self.data[self.data_start_offset_bytes-frame_header_len:self.data_start_offset_bytes] = frame_header
            self.data_start_offset_bytes -= frame_header_len
            self.data_msg_length_bytes += frame_header_len
        else:
            # Otherwise, copy the data to a new buffer.
            self.data = frame_header + self.data
            self.data_start_offset_bytes = 0
            self.data_msg_length_bytes = len(self.data)

        # Return a memoryview of the data buffer that contains the frame.
        return memoryview(self.data)[self.data_start_offset_bytes:self.data_start_offset_bytes+self.data_msg_length_bytes]


    def _get_masked(self, mask_key: Union[str, bytes]) -> bytes:
        s = ABNF.mask(mask_key, self.data)

        if isinstance(mask_key, str):
            mask_key = mask_key.encode("utf-8")

        return mask_key + s

    @staticmethod
    def mask(mask_key: Union[str, bytes], data: Union[str, bytes]) -> bytes:
        """
        Mask or unmask data. Just do xor for each byte

        Parameters
        ----------
        mask_key: bytes or str
            4 byte mask.
        data: bytes or str
            data to mask/unmask.
        """
        if data is None:
            data = ""

        if isinstance(mask_key, str):
            mask_key = mask_key.encode("latin-1")

        if isinstance(data, str):
            data = data.encode("latin-1")

        return _mask(array.array("B", mask_key), array.array("B", data))


class frame_buffer:
    _HEADER_MASK_INDEX = 5
    _HEADER_LENGTH_INDEX = 6

    def __init__(
        self, recv_into_fn: Callable[[Union[bytearray, memoryview]], int], skip_utf8_validation: bool
    ) -> None:
        self.recv_into = recv_into_fn
        self.skip_utf8_validation = skip_utf8_validation
        self.clear()
        self.lock = Lock()

    def clear(self) -> None:
        self.header: Optional[tuple] = None
        self.length: Optional[int] = None
        self.mask_value: Union[bytes, str, None] = None

    def has_received_header(self) -> bool:
        return self.header is None

    def recv_header(self) -> None:
        header_buffer = self.recv_strict(2)
        b1 = header_buffer[0]
        fin = b1 >> 7 & 1
        rsv1 = b1 >> 6 & 1
        rsv2 = b1 >> 5 & 1
        rsv3 = b1 >> 4 & 1
        opcode = b1 & 0xF
        b2 = header_buffer[1]
        has_mask = b2 >> 7 & 1
        length_bits = b2 & 0x7F
        self.header = (fin, rsv1, rsv2, rsv3, opcode, has_mask, length_bits)

    def has_mask(self) -> Union[bool, int]:
        if not self.header:
            return False
        header_val: int = self.header[frame_buffer._HEADER_MASK_INDEX]
        return header_val

    def has_received_length(self) -> bool:
        return self.length is None

    def recv_length(self) -> None:
        bits = self.header[frame_buffer._HEADER_LENGTH_INDEX]
        length_bits = bits & 0x7F
        if length_bits == 0x7E:
            v = self.recv_strict(2)
            self.length = struct.unpack("!H", v)[0]
        elif length_bits == 0x7F:
            v = self.recv_strict(8)
            self.length = struct.unpack("!Q", v)[0]
        else:
            self.length = length_bits

    def has_received_mask(self) -> bool:
        return self.mask_value is None

    def recv_mask(self) -> None:
        self.mask_value = self.recv_strict(4) if self.has_mask() else ""

    def recv_frame(self) -> ABNF:
        with self.lock:
            # Header
            if self.has_received_header():
                self.recv_header()
            (fin, rsv1, rsv2, rsv3, opcode, has_mask, _) = self.header

            # Frame length
            if self.has_received_length():
                self.recv_length()
            length = self.length

            # Mask
            if self.has_received_mask():
                self.recv_mask()
            mask_value = self.mask_value

            # Payload
            payload = self.recv_strict(length)
            if has_mask:
                payload = ABNF.mask(mask_value, payload)

            # Reset for next frame
            self.clear()

            frame = ABNF(fin, rsv1, rsv2, rsv3, opcode, has_mask, payload)
            frame.validate(self.skip_utf8_validation)

        return frame

    def recv_strict(self, bufsize: int) -> bytes:
        shortage = bufsize
        # Allocate the full buffer size we are using, we will copy from the socket directly into it.
        buffer = bytearray(bufsize)
        with memoryview(buffer) as view:
            recv_so_far_bytes = 0
            while shortage > 0:
                # Limit buffer size that we pass to socket.recv() to avoid
                # fragmenting the heap -- the number of bytes recv() actually
                # reads is limited by socket buffer and is relatively small,
                # yet passing large numbers repeatedly causes lots of large
                # buffers allocated and then shrunk, which results in
                # fragmentation. 131072 is the default TCP buffer size on most Linux systems.
                this_read_size_bytes = min(131072, shortage)

                # Slicing the view isn't a copy, but it's sending a view of just that chunk of the buffer.
                # As long as the buffer is under 16384, this recv_into will fill the full buffer in the first call.
                bytes_read = self.recv_into(view[recv_so_far_bytes:recv_so_far_bytes+this_read_size_bytes])
                recv_so_far_bytes += bytes_read
                shortage -= bytes_read

            return buffer


class continuous_frame:
    def __init__(self, fire_cont_frame: bool, skip_utf8_validation: bool) -> None:
        self.fire_cont_frame = fire_cont_frame
        self.skip_utf8_validation = skip_utf8_validation
        self.cont_data: Optional[list] = None
        self.recving_frames: Optional[int] = None

    def is_building(self) -> bool:
        return self.cont_data is not None

    def validate(self, frame: ABNF) -> None:
        if not self.recving_frames and frame.opcode == ABNF.OPCODE_CONT:
            raise WebSocketProtocolException("Illegal frame")
        if self.recving_frames and frame.opcode in (
            ABNF.OPCODE_TEXT,
            ABNF.OPCODE_BINARY,
        ):
            raise WebSocketProtocolException("Illegal frame")

    def add(self, frame: ABNF) -> None:
        if self.cont_data:
            self.cont_data[1] += frame.data
        else:
            if frame.opcode in (ABNF.OPCODE_TEXT, ABNF.OPCODE_BINARY):
                self.recving_frames = frame.opcode
            self.cont_data = [frame.opcode, frame.data]

        if frame.fin:
            self.recving_frames = None

    def is_fire(self, frame: ABNF) -> Union[bool, int]:
        return frame.fin or self.fire_cont_frame

    def extract(self, frame: ABNF) -> tuple:
        data = self.cont_data
        self.cont_data = None
        frame.data = data[1]
        if (
            not self.fire_cont_frame
            and data[0] == ABNF.OPCODE_TEXT
            and not self.skip_utf8_validation
            and not validate_utf8(frame.data)
        ):
            raise WebSocketPayloadException(f"cannot decode: {repr(frame.data)}")
        return data[0], frame