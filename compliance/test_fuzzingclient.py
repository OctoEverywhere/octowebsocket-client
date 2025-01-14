import json
import traceback

import octowebsocket

"""
test_fuzzingclient.py
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

SERVER = "ws://127.0.0.1:8642"
AGENT = "py-websockets-client"


ws = octowebsocket.create_connection(f"{SERVER}/getCaseCount")
count = json.loads(ws.recv())
ws.close()


case = 0
for case in range(1, count + 1):
    url = f"{SERVER}/runCase?case={case}&agent={AGENT}"
    status = octowebsocket.STATUS_NORMAL
    try:
        ws = octowebsocket.create_connection(url)
        while True:
            opcode, msg = ws.recv_data()
            if opcode == octowebsocket.ABNF.OPCODE_TEXT:
                msg.decode("utf-8")
            if opcode in (octowebsocket.ABNF.OPCODE_TEXT, octowebsocket.ABNF.OPCODE_BINARY):
                ws.send(msg, opcode)
    except UnicodeDecodeError:
        # this case is ok.
        status = octowebsocket.STATUS_PROTOCOL_ERROR
    except octowebsocket.WebSocketProtocolException:
        status = octowebsocket.STATUS_PROTOCOL_ERROR
    except octowebsocket.WebSocketPayloadException:
        status = octowebsocket.STATUS_INVALID_PAYLOAD
    except Exception as e:
        # status = websocket.STATUS_PROTOCOL_ERROR
        print(traceback.format_exc())
        print(e)
    finally:
        ws.close(status)

print(f"Ran {case} test cases.")
url = f"{SERVER}/updateReports?agent={AGENT}"
ws = octowebsocket.create_connection(url)
