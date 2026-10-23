# Import socket for network-related operations, such as validating hostnames.
import socket

# Import threading to run network operations in background threads.
import threading

# Import Tkinter to create the graphical user interface (GUI).
import tkinter as tk

# Import file dialog, message box, and themed GUI widgets.
from tkinter import filedialog, messagebox, ttk

# Import the P2PNode class that handles the networking functionality.
from p2p_node import P2PNode


# Define the main application class.
class P2PApp:

    # Constructor: runs when a P2PApp object is created.
    def __init__(self, root):

        # Store the main Tkinter window.
        self.root = root

        # Set the title displayed at the top of the window.
        self.root.title("UAP P2P Network - TCP File & Message Sharing")

        # Set the initial window width and height.
        self.root.geometry("900x650")

        # Set the minimum window width and height.
        self.root.minsize(800, 560)

        # Store the networking node.
        # None means that the local peer has not started yet.
        self.node = None

        # Dictionary that maps peer-list positions to peer IDs.
        self.peer_map = {}

        # Create and arrange all GUI components.
        self._build_ui()

        # Call on_close() when the user clicks the window close button.
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # Create all GUI elements and arrange them in the window.
    def _build_ui(self):

        # Create a labeled section for the local peer's information.
        top = ttk.LabelFrame(self.root, text="My Peer")
        top.pack(fill="x", padx=10, pady=8)

        # Display the label for the local peer's name.
        ttk.Label(top, text="Name:").grid(row=0, column=0, padx=5, pady=8)

        # Create a text variable with Alice as the default peer name.
        self.name_var = tk.StringVar(value="Alice")

        # Create an input field for entering the peer's name.
        ttk.Entry(top, textvariable=self.name_var, width=18).grid(
            row=0, column=1
        )

        # Display the label for the local listening port.
        ttk.Label(top, text="Port:").grid(row=0, column=2, padx=5)

        # Set the default listening port to 5000.
        self.port_var = tk.StringVar(value="5000")

        # Create an input field for changing the listening port.
        ttk.Entry(top, textvariable=self.port_var, width=10).grid(
            row=0, column=3
        )

        # Create a button that calls start_peer() when clicked.
        self.start_btn = ttk.Button(
            top, text="Start Peer", command=self.start_peer
        )
        self.start_btn.grid(row=0, column=4, padx=8)

        # Create a Stop button.
        # It remains disabled until the peer starts successfully.
        self.stop_btn = ttk.Button(
            top, text="Stop", command=self.stop_peer, state="disabled"
        )
        self.stop_btn.grid(row=0, column=5)

        # Create a labeled section for connecting to another peer.
        connect = ttk.LabelFrame(self.root, text="Connect to Another Peer")
        connect.pack(fill="x", padx=10, pady=8)

        # Display the label for the remote peer's IP address.
        ttk.Label(connect, text="IP:").grid(row=0, column=0, padx=5, pady=8)

        # Set the default remote IP to localhost.
        # 127.0.0.1 means the same computer.
        self.ip_var = tk.StringVar(value="127.0.0.1")

        # Create an input field for the remote IP address or hostname.
        ttk.Entry(connect, textvariable=self.ip_var, width=20).grid(
            row=0, column=1
        )

        # Display the label for the remote peer's port.
        ttk.Label(connect, text="Port:").grid(row=0, column=2, padx=5)

        # Set the default remote port to 5001.
        # This can be used when two peers run on the same computer.
        self.remote_port_var = tk.StringVar(value="5001")

        # Create an input field for the remote peer's port.
        ttk.Entry(connect, textvariable=self.remote_port_var, width=10).grid(
            row=0, column=3
        )

        # Create a button that calls connect_peer() when clicked.
        ttk.Button(
            connect, text="Connect", command=self.connect_peer
        ).grid(row=0, column=4, padx=8)

        # Create a frame to hold the peer list and event log.
        middle = ttk.Frame(self.root)
        middle.pack(fill="both", expand=True, padx=10, pady=8)

        # Create a section for displaying connected peers.
        peer_frame = ttk.LabelFrame(middle, text="Connected Peers")
        peer_frame.pack(side="left", fill="y", padx=(0, 8))

        # Create a listbox to display the connected peers.
        self.peer_list = tk.Listbox(peer_frame, width=32, height=20)
        self.peer_list.pack(fill="y", padx=8, pady=8)

        # Create a section for messages, connection events, and errors.
        log_frame = ttk.LabelFrame(middle, text="Messages / Events")
        log_frame.pack(side="left", fill="both", expand=True)

        # Create a text area for displaying log messages.
        # The disabled state prevents direct editing by the user.
        self.log_text = tk.Text(log_frame, wrap="word", state="disabled")
        self.log_text.pack(fill="both", expand=True, padx=8, pady=8)

        # Create the bottom section for sending messages and files.
        bottom = ttk.Frame(self.root)
        bottom.pack(fill="x", padx=10, pady=(0, 10))

        # Display the label for the message input field.
        ttk.Label(bottom, text="Send Text:").grid(row=0, column=0, padx=5)

        # Create a variable to store the message entered by the user.
        self.message_var = tk.StringVar()

        # Create the message input field.
        message_entry = ttk.Entry(bottom, textvariable=self.message_var)
        message_entry.grid(row=0, column=1, sticky="ew", padx=5)

        # Allow the user to press Enter to send a message.
        # The lambda function calls send_text() when Return is pressed.
        message_entry.bind("<Return>", lambda event: self.send_text())

        # Create a button for sending the typed text message.
        ttk.Button(
            bottom, text="Send", command=self.send_text
        ).grid(row=0, column=2, padx=5)

        # Create a button for selecting and sending a file.
        ttk.Button(
            bottom, text="Choose File & Send", command=self.send_file
        ).grid(row=0, column=3, padx=5)

        # Allow the message input field to expand when the window is resized.
        bottom.columnconfigure(1, weight=1)

        # Create the variable used by the status bar.
        self.status_var = tk.StringVar(value="Peer not started.")

        # Display the status bar at the bottom of the window.
        ttk.Label(
            self.root,
            textvariable=self.status_var,
            relief="sunken",
            anchor="w"
        ).pack(fill="x", side="bottom")

    # Safely send a log message to the GUI.
    def log(self, message):

        # Use Tkinter's event loop to update the GUI on the main thread.
        # This is important because networking threads may call this method.
        self.root.after(0, self._append_log, message)

    # Insert a message into the log area and refresh the peer list.
    def _append_log(self, message):

        # Temporarily enable the text area so text can be inserted.
        self.log_text.configure(state="normal")

        # Insert the new message at the end, followed by a newline.
        self.log_text.insert("end", message + "\n")

        # Automatically scroll to the latest message.
        self.log_text.see("end")

        # Disable the text area again to prevent editing.
        self.log_text.configure(state="disabled")

        # Refresh the list of connected peers.
        self.refresh_peers()

    # Start the local peer.
    def start_peer(self):

        # If a node already exists, do not start another one.
        if self.node:
            return

        # Read the peer name and remove leading/trailing spaces.
        name = self.name_var.get().strip()

        # Make sure the peer name is not empty.
        if not name:
            messagebox.showerror("Error", "Enter a peer name.")
            return

        # Validate the listening port entered by the user.
        try:

            # Convert the port from a string into an integer.
            port = int(self.port_var.get())

            # Port numbers must be between 1 and 65535.
            if not 1 <= port <= 65535:
                raise ValueError

        # Handle non-numeric or out-of-range port values.
        except ValueError:
            messagebox.showerror(
                "Error", "Enter a valid port (1-65535)."
            )
            return

        # Try to create and start the local networking node.
        try:

            # Create a P2PNode with the peer name, port, and logging callback.
            self.node = P2PNode(name, port, self.log)

            # Start the node's networking service.
            self.node.start()

            # Disable the Start Peer button after a successful start.
            self.start_btn.config(state="disabled")

            # Enable the Stop button.
            self.stop_btn.config(state="normal")

            # Show the peer name, unique ID, and listening port.
            self.status_var.set(
                f"Running as {name} [{self.node.peer_id}] on port {port}"
            )

        # Handle operating-system errors, such as a port already in use.
        except OSError as exc:
            self.node = None
            messagebox.showerror("Startup failed", str(exc))

    # Stop the local peer and clear the displayed connection list.
    def stop_peer(self):

        # Check whether a networking node exists.
        if self.node:

            # Stop the networking node and close its connections.
            self.node.stop()

            # Clear the reference to the stopped node.
            self.node = None

        # Remove all entries from the peer ID mapping.
        self.peer_map.clear()

        # Clear all displayed peers from the listbox.
        self.peer_list.delete(0, "end")

        # Allow the user to start the peer again.
        self.start_btn.config(state="normal")

        # Disable Stop because the peer is no longer running.
        self.stop_btn.config(state="disabled")

        # Update the status bar.
        self.status_var.set("Peer not started.")

    # Connect the local peer to another peer.
    def connect_peer(self):

        # The local peer must be started before making a connection.
        if not self.node:
            messagebox.showerror("Error", "Start your peer first.")
            return

        # Read the remote IP address or hostname.
        ip = self.ip_var.get().strip()

        # Validate the remote port.
        try:

            # Convert the port input into an integer.
            port = int(self.remote_port_var.get())

            # Check that the port is within the valid range.
            if not 1 <= port <= 65535:
                raise ValueError

        # Display an error if the port is invalid.
        except ValueError:
            messagebox.showerror("Error", "Enter a valid remote port.")
            return

        # Check whether the IP address or hostname can be resolved.
        try:
            socket.gethostbyname(ip)

        # Handle invalid or unresolvable hostnames.
        except socket.gaierror:
            messagebox.showerror(
                "Error", "Invalid IP address or hostname."
            )
            return

        # Define the connection task that will run in a background thread.
        def worker():

            # Try to connect to the remote peer.
            try:
                self.node.connect_to_peer(ip, port)

            # Handle a connection rejected by the remote computer.
            except ConnectionRefusedError:
                self.log(
                    "[ERROR] Connection failed: Connection refused"
                )

            # Handle a connection attempt that times out.
            except TimeoutError:
                self.log("[ERROR] Connection failed: Timeout")

            # Handle other connection errors.
            except Exception as exc:
                self.log(f"[ERROR] Connection failed: {exc}")

        # Start the connection task in a daemon thread.
        # This keeps the GUI responsive during network operations.
        threading.Thread(target=worker, daemon=True).start()

    # Refresh the connected-peer list using information from P2PNode.
    def refresh_peers(self):

        # Do nothing if the local node is not running.
        if not self.node:
            return

        # Retrieve peer IDs, names, and network addresses.
        choices = self.node.get_peer_choices()

        # Reset the mapping between list positions and peer IDs.
        self.peer_map = {}

        # Remove old entries before displaying the updated list.
        self.peer_list.delete(0, "end")

        # Process every connected peer.
        for index, (peer_id, name, address) in enumerate(choices):

            # Format the information for display in the listbox.
            display = f"{name} [{peer_id}] @ {address[0]}:{address[1]}"

            # Add the peer information to the GUI.
            self.peer_list.insert("end", display)

            # Save the peer ID against its current list position.
            self.peer_map[index] = peer_id

    # Return the ID of the peer selected in the listbox.
    def selected_peer_id(self):

        # Get the selected listbox position.
        selection = self.peer_list.curselection()

        # Check whether the user selected a peer.
        if not selection:
            messagebox.showwarning(
                "No peer selected", "Select a connected peer first."
            )
            return None

        # Convert the selected position into the corresponding peer ID.
        return self.peer_map.get(selection[0])

    # Send a text message to the selected peer.
    def send_text(self):

        # Make sure the local peer is running.
        if not self.node:
            messagebox.showerror("Error", "Start your peer first.")
            return

        # Get the selected destination peer's ID.
        peer_id = self.selected_peer_id()

        # Stop if the user has not selected a peer.
        if not peer_id:
            return

        # Read the message and remove extra spaces.
        text = self.message_var.get().strip()

        # Prevent sending an empty message.
        if not text:
            messagebox.showwarning("Empty message", "Enter a message.")
            return

        # Try to send the message through the networking node.
        try:
            self.node.send_text(peer_id, text)

            # Clear the input field after sending successfully.
            self.message_var.set("")

        # Display an error if sending fails.
        except Exception as exc:
            messagebox.showerror("Send failed", str(exc))

    # Select a file and send it to the selected peer.
    def send_file(self):

        # Ensure the local peer has started.
        if not self.node:
            messagebox.showerror("Error", "Start your peer first.")
            return

        # Get the selected destination peer's ID.
        peer_id = self.selected_peer_id()

        # Stop if no peer was selected.
        if not peer_id:
            return

        # Open a file dialog and let the user choose a file.
        # The returned value is the selected file's path.
        path = filedialog.askopenfilename(title="Select a file")

        # If the user cancels the dialog, do nothing.
        if not path:
            return

        # Define the file-transfer task for a background thread.
        def worker():

            # Try to send the selected file.
            try:
                self.node.send_file(peer_id, path)

            # Handle a file that no longer exists.
            except FileNotFoundError as exc:
                self.log(f"[ERROR] {exc}")

            # Handle other file-transfer errors.
            except Exception as exc:
                self.log(f"[ERROR] File transfer failed: {exc}")

        # Run file transfer in a daemon thread.
        # This prevents large file transfers from freezing the GUI.
        threading.Thread(target=worker, daemon=True).start()

    # Clean up the networking node when the application closes.
    def on_close(self):

        # Stop the peer and close its networking connections.
        self.stop_peer()

        # Destroy the Tkinter window.
        self.root.destroy()


# Check whether this file is being executed directly.
if __name__ == "__main__":

    # Create the main Tkinter application window.
    root = tk.Tk()

    # Create the P2P application and attach it to the window.
    app = P2PApp(root)

    # Start Tkinter's event loop.
    # The loop keeps the window open and responds to user actions.
    root.mainloop()
