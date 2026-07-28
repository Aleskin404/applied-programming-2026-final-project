import numpy as np
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QGroupBox,
    QDialog,
)

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from views.plot_view import VisPyPlotWidget


class MainView(QMainWindow):
    """
    Main application window.

    The View owns all visible widgets and connects ViewModel signals
    to UI updates. It does NOT receive TCP data directly or perform
    any data processing — that is the ViewModel's job.

    Layout:
    - Top row: signal time label
    - Left panel: connection controls, channel selection, signal mode,
      plot all button, y-scale, offline inspection button
    - Right panel: VisPy live plot
    - Bottom: status bar
    """

    def __init__(self, view_model):
        super().__init__()

        self.view_model = view_model

        self.setWindowTitle("TCP EMG Viewer — Final Project")
        self.resize(1200, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # --- Signal time display ---
        self.time_label = QLabel("Signal time: 0.00 s")
        self.time_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        main_layout.addWidget(self.time_label)

        # --- Main content: controls on the left, plot on the right ---
        content_layout = QHBoxLayout()
        content_layout.setSpacing(8)

        control_layout = QVBoxLayout()
        control_layout.setSpacing(8)

        # --- Connection controls group ---
        connection_group = QGroupBox("Connection")
        connection_layout = QVBoxLayout()

        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("Port:"))
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(12345)
        port_layout.addWidget(self.port_input)
        connection_layout.addLayout(port_layout)

        self.connect_button = QPushButton("Connect")
        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.setEnabled(False)
        connection_layout.addWidget(self.connect_button)
        connection_layout.addWidget(self.disconnect_button)

        self.status_label = QLabel("Not connected")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #666; font-size: 12px;")
        connection_layout.addWidget(self.status_label)

        connection_group.setLayout(connection_layout)
        control_layout.addWidget(connection_group)

        # --- Channel selection group ---
        channel_group = QGroupBox("Channel")
        channel_layout = QVBoxLayout()

        self.channel_combo = QComboBox()
        for i in range(32):
            self.channel_combo.addItem(f"Channel {i + 1}", i)
        channel_layout.addWidget(self.channel_combo)

        self.plot_all_button = QPushButton("Plot All Channels")
        self.plot_all_button.setCheckable(True)
        channel_layout.addWidget(self.plot_all_button)

        channel_group.setLayout(channel_layout)
        control_layout.addWidget(channel_group)

        # --- Signal mode group ---
        mode_group = QGroupBox("Signal Mode")
        mode_layout = QVBoxLayout()

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Original", "Filtered", "RMS"])
        mode_layout.addWidget(self.mode_combo)

        mode_group.setLayout(mode_layout)
        control_layout.addWidget(mode_group)

        # --- Y scale group ---
        scale_group = QGroupBox("Y Scale")
        scale_layout = QVBoxLayout()

        self.y_scale_input = QDoubleSpinBox()
        self.y_scale_input.setRange(0.01, 100000.0)
        self.y_scale_input.setValue(300.0)
        self.y_scale_input.setSingleStep(50.0)
        self.y_scale_input.setDecimals(2)
        scale_layout.addWidget(self.y_scale_input)

        scale_group.setLayout(scale_layout)
        control_layout.addWidget(scale_group)

        # --- Offline inspection button ---
        self.offline_button = QPushButton("Offline Inspection")
        self.offline_button.setEnabled(False)
        control_layout.addWidget(self.offline_button)

        control_layout.addStretch()

        # --- VisPy plot widget ---
        self.plot_widget = VisPyPlotWidget(
            visible_duration_seconds=10.0,
            y_scale=self.y_scale_input.value(),
        )

        content_layout.addLayout(control_layout, stretch=0)
        content_layout.addWidget(self.plot_widget, stretch=1)
        main_layout.addLayout(content_layout)

        # ---- Connect GUI widgets to actions ----

        # Connection buttons
        self.connect_button.clicked.connect(self._on_connect)
        self.disconnect_button.clicked.connect(self._on_disconnect)

        # Channel selection
        self.channel_combo.currentIndexChanged.connect(self._on_channel_changed)

        # Signal mode
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)

        # Plot all channels toggle
        self.plot_all_button.toggled.connect(self._on_plot_all_toggled)

        # Y scale
        self.y_scale_input.valueChanged.connect(self.plot_widget.set_y_scale)

        # Offline inspection
        self.offline_button.clicked.connect(self._open_offline_dialog)

        # ---- Connect ViewModel signals to View updates ----

        self.view_model.plot_updated.connect(self.plot_widget.update_plot)
        self.view_model.all_channels_updated.connect(
            self.plot_widget.update_all_channels
        )
        self.view_model.status_updated.connect(self._update_status)
        self.view_model.signal_time_updated.connect(self._update_signal_time)
        self.view_model.signal_time_updated.connect(
            self.plot_widget.set_signal_time
        )
        self.view_model.connection_changed.connect(
            self._on_connection_changed
        )

    # ---- Slot methods (respond to GUI interactions) ----

    def _on_connect(self):
        """Read port from input and tell the ViewModel to connect."""
        port = self.port_input.value()
        self.view_model.connect_to_server(port)

    def _on_disconnect(self):
        """Tell the ViewModel to disconnect."""
        self.view_model.disconnect_from_server()

    def _on_channel_changed(self, index):
        """Pass the selected channel index to the ViewModel."""
        channel = self.channel_combo.currentData()
        if channel is not None:
            self.view_model.set_channel(channel)

    def _on_mode_changed(self, mode_text):
        """Pass the selected signal mode to the ViewModel."""
        self.view_model.set_signal_mode(mode_text)

    def _on_plot_all_toggled(self, checked):
        """Toggle between single-channel and all-channels view."""
        self.view_model.set_show_all_channels(checked)
        self.plot_widget.set_mode_all_channels(checked)

        # Disable single-channel selection when showing all
        self.channel_combo.setEnabled(not checked)

        if checked:
            self.plot_all_button.setText("Show Single Channel")
        else:
            self.plot_all_button.setText("Plot All Channels")

    # ---- Slot methods (respond to ViewModel signals) ----

    def _update_status(self, text):
        """Update the status label with connection info."""
        self.status_label.setText(text)

    def _update_signal_time(self, signal_time_seconds):
        """Update the signal time display."""
        self.time_label.setText(
            f"Signal time: {signal_time_seconds:.2f} s"
        )

    def _on_connection_changed(self, connected):
        """
        Enable/disable buttons based on connection state.

        When connected: disable connect, enable disconnect
        When disconnected: enable connect, disable disconnect,
                           enable offline inspection if data exists
        """
        self.connect_button.setEnabled(not connected)
        self.disconnect_button.setEnabled(connected)
        self.port_input.setEnabled(not connected)

        # Enable offline inspection only after disconnecting with data
        has_data = self.view_model.tcp_model.has_recorded_data()
        self.offline_button.setEnabled(not connected and has_data)

    # ---- Offline Matplotlib inspection ----

    def _open_offline_dialog(self):
        """
        Open a dialog for offline signal inspection using Matplotlib.

        Allows the user to select a channel and signal mode, then
        displays the full recorded signal in a Matplotlib plot.
        """
        if not self.view_model.tcp_model.has_recorded_data():
            self.status_label.setText("No recorded data for offline inspection.")
            return

        dialog = OfflineInspectionDialog(self.view_model, parent=self)
        dialog.exec()


class OfflineInspectionDialog(QDialog):
    """
    Dialog for offline Matplotlib inspection of recorded EMG data.

    Provides channel selection and signal mode switching for the
    full recorded signal, displayed as a Matplotlib plot.
    """

    def __init__(self, view_model, parent=None):
        super().__init__(parent)

        self.view_model = view_model

        self.setWindowTitle("Offline Signal Inspection")
        self.resize(900, 600)

        layout = QVBoxLayout(self)

        # --- Controls row ---
        controls_layout = QHBoxLayout()

        controls_layout.addWidget(QLabel("Channel:"))
        self.channel_combo = QComboBox()
        for i in range(32):
            self.channel_combo.addItem(f"Channel {i + 1}", i)
        controls_layout.addWidget(self.channel_combo)

        controls_layout.addWidget(QLabel("Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Original", "Filtered", "RMS"])
        controls_layout.addWidget(self.mode_combo)

        self.refresh_button = QPushButton("Update Plot")
        controls_layout.addWidget(self.refresh_button)

        controls_layout.addStretch()
        layout.addLayout(controls_layout)

        # --- Matplotlib canvas ---
        self.figure = Figure(figsize=(10, 5))
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)

        # --- Connect signals ---
        self.channel_combo.currentIndexChanged.connect(self._update_plot)
        self.mode_combo.currentTextChanged.connect(self._update_plot)
        self.refresh_button.clicked.connect(self._update_plot)

        # Draw the initial plot
        self._update_plot()

    def _update_plot(self):
        """
        Redraw the Matplotlib plot with the selected channel and mode.

        Uses the ViewModel to get processed recorded data, keeping
        the View free of data logic.
        """
        channel = self.channel_combo.currentData()
        if channel is None:
            channel = 0

        mode = self.mode_combo.currentText()

        result = self.view_model.get_offline_data(channel, mode)

        self.figure.clear()
        ax = self.figure.add_subplot(111)

        if result is None:
            ax.text(
                0.5, 0.5,
                "No recorded data available.\nConnect and stream data first.",
                ha="center", va="center",
                fontsize=14, color="gray",
                transform=ax.transAxes,
            )
        else:
            x, y = result
            ax.plot(x, y, linewidth=0.5, color="#1a4d8f")
            ax.set_title(
                f"Channel {channel + 1} — {mode}",
                fontsize=14,
            )
            ax.set_xlabel("Time (s)")
            ax.set_ylabel("Amplitude")
            ax.grid(True, alpha=0.3)

        self.figure.tight_layout()
        self.canvas.draw()
