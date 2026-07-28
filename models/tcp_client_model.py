import socket
import numpy as np


class TcpClientModel:
    """
    TCP client for receiving EMG data from the course server.

    Extends the Exercise 05 solution with:
    - configurable port (user enters it in the GUI)
    - a full recording buffer for offline inspection after disconnect
    - access to all 32 channels for the "Plot All Channels" view

    Data contract (must match the TCP server):
    - 32 channels, 18 samples per packet, float64
    - one packet = 32 * 18 * 8 = 4608 bytes
    - server sends raw bytes via current_window.tobytes()
    """

    def __init__(self, host="localhost", port=12345, sampling_rate=2000,
                 channels=32, samples_per_packet=18, window_seconds=10):
        self.host = host
        self.port = port
        self.sampling_rate = sampling_rate
        self.channels = channels
        self.samples_per_packet = samples_per_packet
        self.window_seconds = window_seconds

        # Must match server dtype before .tobytes()
        self.dtype = np.float64

        self.socket = None
        self.is_connected = False

        # Packet size calculation: 32 channels * 18 samples = 576 values
        self.packet_size = self.channels * self.samples_per_packet
        self.packet_size_bytes = self.packet_size * np.dtype(self.dtype).itemsize

        # Rolling window size: 10 seconds * 2000 Hz = 20000 samples
        self.window_size = int(self.sampling_rate * self.window_seconds)

        # Byte buffer collects raw TCP bytes before packet extraction
        self.byte_buffer = bytearray()

        # Rolling buffer for live plotting (keeps last 10 seconds)
        self.data_buffer = np.empty((self.channels, 0), dtype=self.dtype)

        # Full recording buffer for offline inspection (keeps everything)
        self.recorded_data = np.empty((self.channels, 0), dtype=self.dtype)

        # Total sample counter for signal time calculation
        self.total_samples_received = 0

    def connect(self):
        """
        Connect to the TCP server using a non-blocking socket.

        Non-blocking mode is critical: it prevents recv() from freezing the
        GUI when no data is available. Without this, the entire application
        would hang waiting for the next packet.
        """
        if self.is_connected:
            return

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))
        self.socket.setblocking(False)

        self.is_connected = True

    def disconnect(self):
        """Close the TCP connection and clean up the socket."""
        self.is_connected = False

        if self.socket is not None:
            self.socket.close()
            self.socket = None

    def reset_buffers(self):
        """
        Clear all buffers for a fresh connection.

        Called before connecting so old data from a previous session
        does not mix with new data.
        """
        self.byte_buffer = bytearray()
        self.data_buffer = np.empty((self.channels, 0), dtype=self.dtype)
        self.recorded_data = np.empty((self.channels, 0), dtype=self.dtype)
        self.total_samples_received = 0

    def receive_data(self):
        """
        Receive all currently available TCP data.

        TCP is a byte stream — one recv() call does not necessarily return
        exactly one packet. We collect bytes into a buffer first, then
        extract complete packets of the expected size.

        BlockingIOError is expected in non-blocking mode when no data
        is available. This is normal and means we just stop reading.
        """
        if not self.is_connected or self.socket is None:
            return

        while True:
            try:
                new_bytes = self.socket.recv(4096)

                if not new_bytes:
                    # Empty bytes means server closed the connection
                    self.disconnect()
                    return

                self.byte_buffer.extend(new_bytes)

            except BlockingIOError:
                # No more data available right now — this is expected
                break

        self._extract_packets_from_buffer()

    def _extract_packets_from_buffer(self):
        """
        Convert complete byte packets into NumPy arrays.

        Each packet is 4608 bytes = 32 channels * 18 samples * 8 bytes.
        Partial packets stay in the byte buffer for the next call.
        """
        packets = []

        while len(self.byte_buffer) >= self.packet_size_bytes:
            packet_bytes = self.byte_buffer[:self.packet_size_bytes]
            del self.byte_buffer[:self.packet_size_bytes]

            packet = np.frombuffer(packet_bytes, dtype=self.dtype)
            packet = packet.reshape(self.channels, self.samples_per_packet)

            packets.append(packet)

        if len(packets) == 0:
            return

        new_data = np.concatenate(packets, axis=1)

        # Append to rolling buffer (for live plotting)
        self.data_buffer = np.concatenate(
            (self.data_buffer, new_data), axis=1
        )

        # Append to full recording buffer (for offline inspection)
        self.recorded_data = np.concatenate(
            (self.recorded_data, new_data), axis=1
        )

        # Count total received samples for signal time
        self.total_samples_received += new_data.shape[1]

        # Trim rolling buffer to keep only the last 10 seconds
        if self.data_buffer.shape[1] > self.window_size:
            self.data_buffer = self.data_buffer[:, -self.window_size:]

    def has_data(self):
        """Return True if enough data is available for plotting."""
        return self.data_buffer.shape[1] >= 2

    def has_recorded_data(self):
        """Return True if there is recorded data for offline inspection."""
        return self.recorded_data.shape[1] >= 2

    def get_channel_data(self, channel):
        """
        Return x and y data for a single channel from the rolling buffer.

        Parameters
        ----------
        channel : int
            Channel index (0–31).

        Returns
        -------
        tuple[np.ndarray, np.ndarray]
            Time axis and signal values for the selected channel.
        """
        y = self.data_buffer[channel, :]
        n_samples = y.shape[0]
        x = np.arange(n_samples) / self.sampling_rate
        return x, y

    def get_all_channels_data(self):
        """
        Return x and all 32 channels from the rolling buffer.

        Used by the "Plot All Channels" view.

        Returns
        -------
        tuple[np.ndarray, np.ndarray]
            Time axis (1D) and all channel data (32 × n_samples).
        """
        n_samples = self.data_buffer.shape[1]
        x = np.arange(n_samples) / self.sampling_rate
        return x, self.data_buffer

    def get_recorded_channel(self, channel):
        """
        Return x and y data for one channel from the full recording.

        Used for offline Matplotlib inspection after disconnect.
        """
        y = self.recorded_data[channel, :]
        n_samples = y.shape[0]
        x = np.arange(n_samples) / self.sampling_rate
        return x, y

    def get_recorded_all_channels(self):
        """Return the full recorded data array (32 × total_samples)."""
        return self.recorded_data

    def get_signal_time_seconds(self):
        """
        Return total signal time in seconds.

        Formula: total_samples_received / sampling_rate
        """
        return self.total_samples_received / self.sampling_rate
