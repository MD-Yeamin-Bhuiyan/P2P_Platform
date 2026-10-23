# UAP P2P Network — TCP Communication and File Sharing

A lightweight peer-to-peer network implementation for CSE 433 (Blockchain & Distributed Security Lab).

## Features

- Each peer acts as both TCP server and TCP client.
- Peer name and listening port configuration.
- Direct peer-to-peer TCP connection.
- HELLO / HELLO_ACK handshake.
- Connected peer list.
- Text messaging.
- Binary file transfer for text, image, audio, video, PDF, ZIP, and other ordinary files.
- File transfer uses metadata followed by raw bytes.
- Large files are transferred in 64 KB chunks.
- Multiple peer connections are handled with threads.
- Received files are saved in `downloads/`.
- Basic error handling for invalid IP/port, refused connections, missing files, and disconnects.
- Tkinter GUI.
- No third-party packages are required.

## Requirements

- Python 3.9+
- Windows, Linux, or macOS
- Python standard library: `socket`, `threading`, `tkinter`, etc.

## Project structure

```text
P2P_Network/
├── main.py
├── p2p_node.py
├── protocol.py
├── requirements.txt
├── README.md
└── downloads/
```

## Run

Open a terminal in this directory:

```bash
python main.py
```

## Test on one computer

1. Start one copy:
   - Name: Alice
   - Port: 5000

2. Start a second copy:
   - Name: Bob
   - Port: 5001

3. From Bob, connect to:
   - IP: `127.0.0.1`
   - Port: `5000`

4. Select Alice in Bob's connected-peer list and send a message.

5. Test file transfer with an image, audio/video file, PDF, ZIP, etc.

## Test on two computers

Both computers should be on the same LAN/Wi-Fi.

Example:

```text
Computer A:
IP: 192.168.1.10
Port: 5000

Computer B:
IP: 192.168.1.11
Port: 5001
```

Start Alice on A at port 5000. Start Bob on B at port 5001. Bob connects to `192.168.1.10:5000`.

If Windows Firewall asks for permission, allow Python on the private network.

## Test three peers

Example:

```text
Alice   5000
Bob     5001
Charlie 5002
```

Connect the peers and demonstrate:

- Alice -> Bob text
- Bob -> Charlie text
- Charlie -> Alice text
- file transfers between different pairs

## Protocol

Application-level control messages use:

```text
[4-byte big-endian length][JSON payload]
```

Example HELLO:

```json
{
  "type": "hello",
  "peer_id": "a83f21c4",
  "peer_name": "Alice",
  "port": 5000
}
```

Example text:

```json
{
  "type": "text",
  "sender_id": "a83f21c4",
  "sender_name": "Alice",
  "message": "Hello Bob!"
}
```

File transfer:

```text
[framed JSON file metadata]
[exactly filesize raw bytes]
```

The receiver uses the `filesize` field to know exactly how many bytes belong to the file.

## Important viva point

This is a P2P application, but it is intentionally a small educational system. It does not implement blockchain, cryptocurrency, DHT, BitTorrent, NAT traversal, WebRTC, authentication, encryption, databases, or cloud deployment.

## Demonstration checklist

1. Start Peer A.
2. Start Peer B.
3. Connect B to A.
4. Show connected peers.
5. Send A -> B text.
6. Send B -> A text.
7. Send an image.
8. Send an audio/video file.
9. Start Peer C.
10. Connect C.
11. Demonstrate communication involving C.
