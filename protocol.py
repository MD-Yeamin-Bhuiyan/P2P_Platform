
# Import json to convert Python dictionaries into JSON strings and back.
import json

# Import struct to convert integers into a fixed-size binary header.
import struct


# The header is 4 bytes long and stores the size of the JSON message.
HEADER_SIZE = 4

# Set the maximum size of a JSON/control message to 10 MB.
# This limit applies to protocol messages, not the raw file contents.
MAX_MESSAGE_SIZE = 10 * 1024 * 1024


def recvall(sock, n):
    """
    Receive exactly n bytes from a TCP socket.

    TCP does not guarantee that one recv() call returns all requested
    bytes, so this function keeps receiving until n bytes are collected.

    Returns None if the connection closes before all bytes arrive.
    """

    # Create a mutable byte array to collect incoming data.
    data = bytearray()

    # Continue receiving until we have collected n bytes.
    while len(data) < n:

        # Receive only the number of bytes that are still needed.
        chunk = sock.recv(n - len(data))

        # An empty result means the remote side closed the connection.
        if not chunk:
            return None

        # Add the newly received bytes to the collected data.
        data.extend(chunk)

    # Convert the bytearray into immutable bytes and return it.
    return bytes(data)


def send_json(sock, message):
    """
    Send a Python dictionary as a framed JSON message.

    The receiver first reads a 4-byte header to learn the payload size,
    then reads the JSON payload itself.
    """

    # Convert the Python object into a JSON string.
    # ensure_ascii=False allows non-ASCII characters to remain readable.
    payload = json.dumps(message, ensure_ascii=False).encode("utf-8")

    # Reject messages that exceed the allowed JSON message size.
    if len(payload) > MAX_MESSAGE_SIZE:
        raise ValueError("JSON message is too large")

    # Pack the payload length into 4 bytes.
    # !I means unsigned 32-bit integer in network byte order (big-endian).
    header = struct.pack("!I", len(payload))

    # Send the header and JSON payload together.
    # sendall() continues sending until all bytes have been sent
    # or an error occurs.
    sock.sendall(header + payload)


def recv_json(sock):
    """
    Receive one framed JSON message from a TCP socket.

    Returns the decoded Python object, or None if the connection closes
    before the complete message is received.
    """

    # First, receive the fixed-size header containing the payload length.
    header = recvall(sock, HEADER_SIZE)

    # If no complete header arrives, treat it as a closed connection.
    if header is None:
        return None

    # Decode the 4-byte header into an unsigned integer.
    # [0] selects the integer from the returned tuple.
    length = struct.unpack("!I", header)[0]

    # Reject zero-length messages and messages larger than the limit.
    if length <= 0 or length > MAX_MESSAGE_SIZE:
        raise ValueError("Invalid JSON message length")

    # Receive exactly the number of payload bytes specified by the header.
    payload = recvall(sock, length)

    # If the connection closes before the payload is complete, return None.
    if payload is None:
        return None

    # Decode the UTF-8 bytes into a string, then parse the JSON string
    # into a Python object, usually a dictionary.
    return json.loads(payload.decode("utf-8"))
