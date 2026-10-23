
# Import os for checking files and getting their names and sizes.
import os

# Import socket to create and manage TCP network connections.
import socket

# Import threading to run networking tasks concurrently.
import threading

# Import uuid to generate a unique ID for each peer.
import uuid

# Import Path to create and manage filesystem paths.
from pathlib import Path

# Import the protocol functions for sending and receiving JSON messages.
from protocol import send_json, recv_json


# Read and send file data in chunks of 64 KB at a time.
# This avoids loading an entire large file into memory.
CHUNK_SIZE = 64 * 1024


class PeerConnection:
    """Store one TCP connection and protect simultaneous sends."""

    def __init__(self, sock, address, peer_id=None,
                 peer_name=None, peer_port=None):

        # Store the TCP socket used to communicate with this peer.
        self.sock = sock

        # Store the peer's network address, usually (IP, port).
        self.address = address

        # Store the peer's unique ID; initially unknown for new connections.
        self.peer_id = peer_id

        # Store the peer's display name.
        self.peer_name = peer_name

        # Store the peer's advertised listening port.
        self.peer_port = peer_port

        # Ensure multiple threads do not send data simultaneously
        # through this connection and mix their message bytes.
        self.send_lock = threading.Lock()

        # Track whether this connection is considered active.
        self.alive = True

    def send_json(self, message):
        # Allow only one sender at a time to use this socket.
        with self.send_lock:

            # Send the dictionary using the shared JSON protocol.
            send_json(self.sock, message)


class P2PNode:

    def __init__(self, peer_name, listen_port, event_callback=None):

        # Generate a unique 8-character hexadecimal peer ID.
        self.peer_id = uuid.uuid4().hex[:8]

        # Store this peer's user-defined name.
        self.peer_name = peer_name

        # Store the TCP port on which this peer will listen.
        self.listen_port = int(listen_port)

        # Store the callback used to report events to the GUI.
        # If no callback is provided, use a function that does nothing.
        self.event_callback = event_callback or (lambda msg: None)

        # The listening server socket will be created when start() runs.
        self.server_socket = None

        # Track whether this peer's networking service is running.
        self.running = False

        # Store the background thread that accepts incoming connections.
        self.accept_thread = None

        # Store active connections using peer IDs as dictionary keys.
        # Format: peer_id -> PeerConnection object.
        self.peers = {}

        # Protect the peer dictionary when multiple threads access it.
        self.peers_lock = threading.Lock()

    def log(self, message):
        # Send an event to the GUI or other registered callback.
        self.event_callback(message)

    def start(self):

        # Do not start the same node twice.
        if self.running:
            return

        # Create an IPv4 TCP socket.
        # AF_INET means IPv4; SOCK_STREAM means TCP.
        self.server_socket = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM
        )

        # Allow the port to be reused after the previous socket closes,
        # subject to the operating system's socket rules.
        self.server_socket.setsockopt(
            socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
        )

        # Listen on all local IPv4 network interfaces.
        # Other computers may connect if the network and firewall allow it.
        self.server_socket.bind(("0.0.0.0", self.listen_port))

        # Allow up to 20 pending connection requests in the listen queue.
        self.server_socket.listen(20)

        # Make accept() wait for at most one second at a time.
        # This allows the loop to notice when self.running becomes False.
        self.server_socket.settimeout(1.0)

        # Mark the node as running.
        self.running = True

        # Create a background thread to accept incoming connections.
        self.accept_thread = threading.Thread(
            target=self._accept_loop,
            daemon=True
        )

        # Start accepting connections without blocking the GUI.
        self.accept_thread.start()

        # Report that the local peer is ready.
        self.log(
            f"[INFO] Peer started: {self.peer_name} "
            f"[{self.peer_id}] listening on port {self.listen_port}"
        )

    def stop(self):

        # Nothing needs to be stopped if the node is already inactive.
        if not self.running:
            return

        # Tell background loops to stop.
        self.running = False

        # Close the listening socket to stop accepting new connections.
        try:
            self.server_socket.close()
        except Exception:
            # Ignore errors if the socket has already been closed.
            pass

        # Lock the peer dictionary while collecting and clearing connections.
        with self.peers_lock:
            connections = list(self.peers.values())
            self.peers.clear()

        # Close every previously registered peer connection.
        for peer in connections:

            try:
                # Attempt to shut down both sending and receiving.
                peer.sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                # The socket may already be disconnected.
                pass

            try:
                # Release the socket resource.
                peer.sock.close()
            except Exception:
                pass

        # Report that the node has stopped.
        self.log("[INFO] Peer stopped.")

    def _accept_loop(self):

        # Keep accepting incoming connections while the node is running.
        while self.running:
            try:
                # Wait for another peer to connect.
                # Returns the new socket and the remote address.
                sock, address = self.server_socket.accept()

                # Remove the listening socket's timeout from this connection.
                sock.settimeout(None)

                # Give this incoming connection its own handler thread.
                thread = threading.Thread(
                    target=self._handle_connection,
                    args=(sock, address, False),
                    daemon=True
                )

                # Start handling the new connection.
                thread.start()

            except socket.timeout:
                # No connection arrived during this interval.
                # Continue checking whether the node is still running.
                continue

            except OSError:
                # Closing the listening socket may cause this error.
                break

            except Exception as exc:
                # Report unexpected errors during connection acceptance.
                self.log(f"[ERROR] Accept failed: {exc}")

    def connect_to_peer(self, ip, port):

        # A local node must be running before it can connect outward.
        if not self.running:
            raise RuntimeError("Start your peer before connecting.")

        # Remove accidental whitespace from the supplied IP or hostname.
        ip = ip.strip()

        # Ensure the remote port is an integer.
        port = int(port)

        # Create a new IPv4 TCP socket for the outgoing connection.
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # Limit how long the connection attempt can wait.
        sock.settimeout(8)

        try:
            # Establish the TCP connection to the remote peer.
            sock.connect((ip, port))

            # Use blocking socket operations after connecting.
            sock.settimeout(None)

            # Create a connection object for the remote peer.
            connection = PeerConnection(sock, (ip, port))

            # Send a HELLO message to introduce this peer.
            connection.send_json({
                "type": "hello",
                "peer_id": self.peer_id,
                "peer_name": self.peer_name,
                "port": self.listen_port,
            })

            # Start a background thread to receive the remote peer's messages.
            thread = threading.Thread(
                target=self._receive_loop,
                args=(connection,),
                daemon=True
            )

            # Start receiving responses and future messages.
            thread.start()

            # Report that the connection attempt has begun.
            self.log(f"[INFO] Connecting to {ip}:{port} ...")

        except Exception:
            # Close the socket if connection setup fails.
            try:
                sock.close()
            except Exception:
                pass

            # Pass the original error back to the caller.
            raise

    def _handle_connection(self, sock, address, outgoing):

        # Wrap the accepted socket in a PeerConnection object.
        connection = PeerConnection(sock, address)

        # This branch handles incoming connections.
        if not outgoing:
            try:
                # Read the first framed JSON message from the remote peer.
                message = recv_json(sock)

                # If the connection closed before a message arrived, stop.
                if message is None:
                    sock.close()
                    return

                # A new incoming peer must introduce itself with HELLO.
                if message.get("type") != "hello":
                    raise ValueError("First message must be HELLO")

                # Save the remote peer's identity and register its connection.
                self._register_peer(connection, message)

                # Send our own identity as confirmation.
                connection.send_json({
                    "type": "hello_ack",
                    "peer_id": self.peer_id,
                    "peer_name": self.peer_name,
                    "port": self.listen_port,
                })

                # Process incoming messages until the connection ends.
                self._receive_loop(connection)

            except Exception as exc:
                # Report problems with the incoming connection.
                self.log(f"[ERROR] Incoming connection {address}: {exc}")

                # Close the socket after an error.
                try:
                    sock.close()
                except Exception:
                    pass

    def _receive_loop(self, connection):

        # Keep reading while the local node and connection are active.
        try:
            while self.running and connection.alive:

                # Read one complete framed JSON message.
                message = recv_json(connection.sock)

                # None indicates that the connection closed before
                # a complete message was received.
                if message is None:
                    break

                # Extract the message type to decide how to handle it.
                msg_type = message.get("type")

                # Handle a HELLO message received over this connection.
                if msg_type == "hello":

                    # Register the remote peer.
                    self._register_peer(connection, message)

                    # Return our identity to acknowledge the introduction.
                    connection.send_json({
                        "type": "hello_ack",
                        "peer_id": self.peer_id,
                        "peer_name": self.peer_name,
                        "port": self.listen_port,
                    })

                # Handle confirmation from a peer we contacted.
                elif msg_type == "hello_ack":

                    # Save the remote peer's identity.
                    self._register_peer(connection, message)

                    # Report the successful peer handshake.
                    self.log(
                        f"[INFO] Connected with "
                        f"{connection.peer_name} [{connection.peer_id}]"
                    )

                # Handle an incoming text message.
                elif msg_type == "text":

                    # Display the sender and the received message.
                    self.log(
                        f"[MESSAGE] "
                        f"{message.get('sender_name', 'Unknown')} -> You: "
                        f"{message.get('message', '')}"
                    )

                # Handle an incoming file-transfer request.
                elif msg_type == "file":

                    # Read the file metadata and receive the raw file bytes.
                    self._receive_file(connection, message)

                else:
                    # Report any message type this implementation does not know.
                    self.log(f"[ERROR] Unknown message type: {msg_type}")

        # Handle common socket and connection failures.
        except (ConnectionResetError, BrokenPipeError, OSError) as exc:
            if self.running:
                self.log(
                    f"[ERROR] Peer "
                    f"{connection.peer_name or connection.address} "
                    f"disconnected: {exc}"
                )

        # Handle other errors, such as malformed protocol messages.
        except Exception as exc:
            if self.running:
                self.log(f"[ERROR] Receive failed: {exc}")

        finally:
            # Always clean up the connection when this loop finishes.
            self._remove_peer(connection)

    def _register_peer(self, connection, message):

        # Read the remote peer's unique ID and convert it to a string.
        connection.peer_id = str(message["peer_id"])

        # Read the peer's name, using Unknown if no name was provided.
        connection.peer_name = str(message.get("peer_name", "Unknown"))

        # Read the peer's advertised listening port.
        connection.peer_port = int(message.get("port", 0))

        # Lock the dictionary to safely update peer information.
        with self.peers_lock:

            # Check whether a connection for this peer ID already exists.
            old = self.peers.get(connection.peer_id)

            # Close the old socket if it belongs to a different connection.
            if old is not None and old is not connection:
                try:
                    old.sock.close()
                except Exception:
                    pass

            # Store the new or current connection under its peer ID.
            self.peers[connection.peer_id] = connection

        # Display the peer's identity and network address.
        self.log(
            f"[INFO] Peer available: {connection.peer_name} "
            f"[{connection.peer_id}] @ "
            f"{connection.address[0]}:{connection.address[1]}"
        )

    def _remove_peer(self, connection):

        # Mark this connection as inactive.
        connection.alive = False

        # Only remove the dictionary entry if this peer has an assigned ID.
        if connection.peer_id:

            # Protect the dictionary while checking and removing the entry.
            with self.peers_lock:

                # Get the currently stored connection for this peer.
                current = self.peers.get(connection.peer_id)

                # Avoid removing a newer connection for the same peer ID.
                if current is connection:
                    self.peers.pop(connection.peer_id, None)

        # Close the connection's socket.
        try:
            connection.sock.close()
        except Exception:
            pass

        # Report the disconnection if the peer's name is known.
        if connection.peer_name:
            self.log(f"[INFO] Disconnected: {connection.peer_name}")

    def get_peers(self):

        # Lock the peer dictionary while reading its current connections.
        with self.peers_lock:

            # Return a new list containing the PeerConnection objects.
            return list(self.peers.values())

    def get_peer_choices(self):

        # Obtain the current list of connected peer objects.
        peers = self.get_peers()

        # Return tuples containing the peer ID, display name, and address.
        # main.py uses this information to populate its connected-peer list.
        return [
            (peer.peer_id, peer.peer_name or "Unknown", peer.address)
            for peer in peers
        ]

    def _get_peer(self, peer_id):

        # Safely find and return a peer connection by its unique ID.
        with self.peers_lock:
            return self.peers.get(peer_id)

    def send_text(self, peer_id, text):

        # Remove leading and trailing spaces from the message.
        text = text.strip()

        # Reject an empty message.
        if not text:
            raise ValueError("Message cannot be empty.")

        # Look up the selected destination peer.
        peer = self._get_peer(peer_id)

        # Reject the operation if the peer is missing or disconnected.
        if not peer or not peer.alive:
            raise ValueError("Selected peer is not connected.")

        # Send the text message as a framed JSON object.
        peer.send_json({
            "type": "text",
            "sender_id": self.peer_id,
            "sender_name": self.peer_name,
            "message": text,
        })

        # Display a local log confirming the send operation.
        self.log(f"[MESSAGE] You -> {peer.peer_name}: {text}")

    def send_file(self, peer_id, file_path):

        # Convert the supplied path to a string.
        file_path = str(file_path)

        # Verify that the selected path refers to an existing regular file.
        if not os.path.isfile(file_path):
            raise FileNotFoundError("File does not exist.")

        # Find the destination peer.
        peer = self._get_peer(peer_id)

        # Ensure the destination is still connected.
        if not peer or not peer.alive:
            raise ValueError("Selected peer is not connected.")

        # Read the total file size in bytes.
        filesize = os.path.getsize(file_path)

        # Extract the filename without its directory path.
        filename = os.path.basename(file_path)

        # Lock the socket for the entire transfer.
        # This prevents another sender from inserting bytes between
        # the file metadata and the raw file data.
        peer.send_lock.acquire()

        try:
            # First send a JSON message describing the incoming file.
            # The receiver needs the size to know when the file ends.
            send_json(peer.sock, {
                "type": "file",
                "sender_id": self.peer_id,
                "sender_name": self.peer_name,
                "filename": filename,
                "filesize": filesize,
            })

            # Track the number of file bytes successfully sent.
            sent = 0

            # Open the source file in binary-read mode.
            # Binary mode preserves the exact bytes of any file type.
            with open(file_path, "rb") as file:

                # Read and send the file until no data remains.
                while True:

                    # Read at most 64 KB from the file.
                    chunk = file.read(CHUNK_SIZE)

                    # An empty chunk means the end of the file was reached.
                    if not chunk:
                        break

                    # Send the entire chunk through the TCP socket.
                    peer.sock.sendall(chunk)

                    # Update the number of bytes sent.
                    sent += len(chunk)

        except Exception:
            # Mark the connection inactive if the transfer fails.
            peer.alive = False

            # Pass the transfer error to the caller.
            raise

        finally:
            # Always release the sending lock, even if an error occurs.
            peer.send_lock.release()

        # Log the completed file transfer.
        self.log(
            f"[FILE] Sent {filename} ({filesize:,} bytes) "
            f"-> {peer.peer_name}"
        )

    def _receive_file(self, connection, metadata):

        # Keep only the filename, removing any supplied directory components.
        # This helps prevent a remote filename from choosing an arbitrary path.
        filename = os.path.basename(
            str(metadata.get("filename", "received_file"))
        )

        # Read the expected file size from the metadata.
        filesize = int(metadata.get("filesize", -1))

        # Reject a negative file size.
        if filesize < 0:
            raise ValueError("Invalid file size.")

        # Save received files inside a local downloads directory.
        downloads = Path("downloads")

        # Create the directory if it does not already exist.
        downloads.mkdir(parents=True, exist_ok=True)

        # Build the destination path using the safe filename.
        target = downloads / filename

        # Avoid overwriting a file that already exists.
        if target.exists():

            # Separate the existing filename into its stem and extension.
            stem = target.stem
            suffix = target.suffix

            # Start adding a numeric suffix to make a unique filename.
            counter = 1

            # Keep trying until a destination filename is available.
            while target.exists():
                target = downloads / f"{stem}_{counter}{suffix}"
                counter += 1

        # Track the number of file bytes that still need to be received.
        remaining = filesize

        # Open the destination file in binary-write mode.
        # This creates the file or truncates it if it already exists.
        with open(target, "wb") as file:

            # Receive data until the expected file size is reached.
            while remaining > 0:

                # Request no more than the remaining bytes or one chunk.
                chunk = connection.sock.recv(
                    min(CHUNK_SIZE, remaining)
                )

                # If the connection closes early, the transfer is incomplete.
                if not chunk:
                    raise ConnectionError(
                        "Connection closed during file transfer."
                    )

                # Write the received bytes to the destination file.
                file.write(chunk)

                # Decrease the remaining byte count.
                remaining -= len(chunk)

        # Report that the file has been received and saved.
        self.log(
            f"[FILE] Received {filename} ({filesize:,} bytes) "
            f"from {connection.peer_name} -> {target}"
        )
