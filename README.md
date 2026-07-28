# TCP EMG Viewer — Final Project

**Applied Programming 2026** — N² Lab, FAU Erlangen-Nürnberg

A PySide6 desktop application for live visualization and offline inspection of streamed EMG data via TCP.

---

## Team

| Name | Responsibility |
|------|----------------|
| TODO | TCP client / backend |
| TODO | Visualization / frontend |
| TODO | Documentation / integration |

---

## Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd final_project

# Install dependencies
pip install -r requirements.txt
```

### Dependencies

- `numpy` — array operations and data buffering
- `scipy` — bandpass filter and signal processing
- `matplotlib` — offline signal inspection plots
- `pyside6` — GUI framework (Qt for Python)
- `vispy` — high-performance live signal plotting

---

## How to Run

### 1. Start the TCP Server

The server is provided by the course. It streams EMG data from `recording.pkl`.

```bash
python TCP_Server/main.py
```

The server runs on `localhost:12345` by default.

### 2. Start the Application

```bash
python main.py
```

---

## How to Use

### Connecting to the Server

1. Enter the TCP port in the **Port** field (default: `12345`).
2. Click **Connect**. The status label shows the connection state.
3. Live streaming starts automatically after a successful connection.
4. Click **Disconnect** to stop streaming.

### Live Plot (VisPy)

- The live plot shows a rolling 10-second window of the incoming signal.
- The x-axis displays time labels that move from right to left.
- The y-axis scale can be adjusted with the **Y Scale** input.

### Selecting a Channel

- Use the **Channel** dropdown to switch between channels 1–32.
- The plot updates immediately to show the selected channel.

### Signal Modes

Use the **Signal Mode** dropdown to switch between:

- **Original** — raw signal as received from the server
- **Filtered** — 4th order Butterworth bandpass filter (20–450 Hz)
- **RMS** — root mean square envelope (100 ms window), computed on the filtered signal

Signal modes work in both live and offline views.

### Plot All Channels

Click the **Plot All Channels** button to display all 32 channels simultaneously with vertical offset. Each channel is normalized and color-coded. Click again to return to single-channel view.

### Offline Inspection (Matplotlib)

After disconnecting, click **Offline Inspection** to open a Matplotlib dialog:

- Select any channel from the dropdown
- Switch between Original / Filtered / RMS signal modes
- The plot shows the full recorded signal (not just the last 10 seconds)

---

## Signal Processing Parameters

| Parameter | Value |
|-----------|-------|
| Bandpass filter type | Butterworth |
| Filter order | 4th order |
| Low cutoff frequency | 20 Hz |
| High cutoff frequency | 450 Hz |
| Filter method | `scipy.signal.filtfilt` (zero-phase) |
| RMS window duration | 100 ms |
| RMS window size | 200 samples (at 2000 Hz) |
| RMS method | Convolution with uniform kernel |

The RMS envelope is computed on the filtered signal, not on the raw signal.

---

## Project Structure (MVVM)

```
final_project/
├── main.py                          # Entry point
├── README.md                        # This file
├── requirements.txt                 # Dependencies
├── models/
│   ├── __init__.py
│   ├── tcp_client_model.py          # TCP client + data buffering (Model)
│   └── signal_processor.py          # Bandpass filter + RMS (Model)
├── viewmodels/
│   ├── __init__.py
│   └── main_viewmodel.py            # Application state + signals (ViewModel)
└── views/
    ├── __init__.py
    ├── main_view.py                 # Main window + offline dialog (View)
    └── plot_view.py                 # VisPy live plot widget (View)
```

### MVVM Responsibilities

**Model** (`models/`):
- `TcpClientModel`: handles TCP socket connection, byte buffering, packet extraction, and rolling/recording data buffers. No GUI code.
- `SignalProcessor`: applies bandpass filtering and RMS envelope computation. Stateless utility — filter coefficients are pre-computed once.

**ViewModel** (`viewmodels/main_viewmodel.py`):
- Owns the Model instances and manages application state (connection, selected channel, signal mode).
- Uses a `QTimer` (10 ms interval) to poll the TCP model for new data.
- Processes data through the `SignalProcessor` and emits results via Qt signals.
- Does not contain any GUI widgets or layout code.

**View** (`views/`):
- `MainView`: creates all GUI widgets (buttons, dropdowns, labels) and connects ViewModel signals to UI updates. Does not access TCP data directly.
- `VisPyPlotWidget`: renders live EMG data using VisPy scene visuals. Supports single-channel and all-channels display modes.
- `OfflineInspectionDialog`: embeds a Matplotlib canvas for post-recording inspection.

### Data Flow

```
TCP Server → TcpClientModel.receive_data()
           → ViewModel._update() [called by QTimer]
           → SignalProcessor.process_channel()
           → ViewModel emits plot_updated signal
           → View.plot_widget.update_plot()
```

---

## Error Handling

The application handles common errors without crashing:

- **Server not running**: displays "Connection failed: [Errno ...]" in the status label
- **Wrong port**: same connection error handling via try/except
- **Connection lost**: detected when `recv()` returns empty bytes; triggers automatic disconnect
- **No data for offline plot**: shows a "No recorded data available" message in the Matplotlib dialog
- **Reconnection**: buffers are reset before each new connection so old data does not mix with new data
