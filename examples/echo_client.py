import octowebsocket

if __name__ == "__main__":
    octowebsocket.enableTrace(True)
    ws = octowebsocket.create_connection("ws://echo.websocket.events/")
    ws.recv()
    print("Sending 'Hello, World'...")
    ws.send("Hello, World")
    print("Sent")
    print("Receiving...")
    result = ws.recv()
    print(f"Received '{result}'")
    ws.close()
