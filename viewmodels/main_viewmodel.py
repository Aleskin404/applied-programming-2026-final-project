from PySide6.QtCore import QObject, QTimer, Signal

from models.tcp_client_model import TcpClientModel
from models.signal_processor import SignalProcessor


class MainViewModel(QObject):
    """
    ViewModel for the TCP EMG Visualization application.

    Responsibilities (MVVM pattern):
    - Owns the TcpClientModel and SignalProcessor (models)
    - Manages application state (connection, channel, signal mode)
    - Uses QTimer to poll for new TCP data every 10 ms
    - Emits processed data to the View via Qt signals
    - Does NOT contain any GUI code (no widgets, no layouts)

    Signals emitted to the View:
    - plot_updated(x, y): new data for single-channel VisPy plot
    - all_channels_updated(x, all_y): data for all-channels VisPy plot
    - status_updated(str): connection status text
    - signal_time_updated(float): current signal time in seconds
    - connection_changed(bool): True when connected, False when disconnected
    """

    # Signals for the View to connect to
    plot_updated = Signal(object, object)
    all_channels_updated = Signal(object, object)
    status_updated = Signal(str)
    signal_time_updated = Signal(float)
    connection_changed = Signal(bool)

    def __init__(self):
        super().__init__()

        # Create the TCP client model with default settings
        self.tcp_model = TcpClientModel(
            host="localhost",
            port=12345,
            sampling_rate=2000,
            channels=32,
            samples_per_packet=18,
            window_seconds=10,
        )

        # Create the signal processor with Ex02 parameters
        self.signal_processor = SignalProcessor(
            sampling_rate=2000,
            low_cut=20.0,
            high_cut=450.0,
            filter_order=4,
            rms_window_ms=100.0,
        )

        # Application state
        self.is_plotting = False
        self.selected_channel = 0
        self.signal_mode = "Original"  # "Original", "Filtered", or "RMS"
        self.show_all_channels = False

        # QTimer polls for new TCP data every 10 ms
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update)

    def connect_to_server(self, port):
        """
        Connect to the TCP server on the given port.

        Resets buffers first so old data from a previous session
        does not contaminate the new connection.
        """
        if self.is_plotting:
            return

        # Update port from GUI input
        self.tcp_model.port = port

        # Clear old data before reconnecting
        self.tcp_model.reset_buffers()

        try:
            self.tcp_model.connect()
        except OSError as error:
            self.status_updated.emit(f"Connection failed: {error}")
            return

        self.is_plotting = True
        self.status_updated.emit(f"Connected to localhost:{port}")
        self.connection_changed.emit(True)

        # Start polling for data every 10 ms
        self.timer.start(10)

    def disconnect_from_server(self):
        """Stop plotting and close the TCP connection."""
        if not self.is_plotting:
            return

        self.timer.stop()
        self.tcp_model.disconnect()

        self.is_plotting = False
        self.status_updated.emit("Disconnected. Offline inspection available.")
        self.connection_changed.emit(False)

    def set_channel(self, channel):
        """Change the displayed channel (0–31)."""
        self.selected_channel = channel

    def set_signal_mode(self, mode):
        """
        Change the signal processing mode.

        Parameters
        ----------
        mode : str
            One of "Original", "Filtered", "RMS".
        """
        self.signal_mode = mode

    def set_show_all_channels(self, show_all):
        """Toggle between single-channel and all-channels view."""
        self.show_all_channels = show_all

    def _update(self):
        """
        Called by QTimer every 10 ms.

        Pulls new data from the TCP model, applies signal processing,
        and emits the result to the View.
        """
        self.tcp_model.receive_data()

        if not self.tcp_model.has_data():
            return

        # Check if server closed the connection during receive
        if not self.tcp_model.is_connected:
            self.disconnect_from_server()
            return

        if self.show_all_channels:
            self._emit_all_channels()
        else:
            self._emit_single_channel()

        # Update signal time display
        signal_time = self.tcp_model.get_signal_time_seconds()
        self.signal_time_updated.emit(signal_time)

    def _emit_single_channel(self):
        """Process and emit data for one selected channel."""
        x, y = self.tcp_model.get_channel_data(self.selected_channel)
        y_processed = self.signal_processor.process_channel(y, self.signal_mode)
        self.plot_updated.emit(x, y_processed)

    def _emit_all_channels(self):
        """Process and emit data for all 32 channels."""
        x, all_data = self.tcp_model.get_all_channels_data()
        all_processed = self.signal_processor.process_all_channels(
            all_data, self.signal_mode
        )
        self.all_channels_updated.emit(x, all_processed)

    def get_offline_data(self, channel, mode):
        """
        Return processed recorded data for offline Matplotlib inspection.

        Parameters
        ----------
        channel : int
            Channel index (0–31).
        mode : str
            Signal processing mode.

        Returns
        -------
        tuple[np.ndarray, np.ndarray] or None
            (x, y) arrays, or None if no recorded data exists.
        """
        if not self.tcp_model.has_recorded_data():
            return None

        x, y = self.tcp_model.get_recorded_channel(channel)
        y_processed = self.signal_processor.process_channel(y, mode)
        return x, y_processed

    def get_offline_all_channels(self, mode):
        """
        Return processed recorded data for all channels (offline).

        Returns
        -------
        tuple[np.ndarray, np.ndarray] or None
        """
        if not self.tcp_model.has_recorded_data():
            return None

        recorded = self.tcp_model.get_recorded_all_channels()
        n_samples = recorded.shape[1]
        import numpy as np
        x = np.arange(n_samples) / self.tcp_model.sampling_rate
        processed = self.signal_processor.process_all_channels(recorded, mode)
        return x, processed
