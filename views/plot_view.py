import math
import numpy as np
from PySide6.QtWidgets import QVBoxLayout, QWidget
from vispy import scene


class VisPyPlotWidget(QWidget):
    """
    VisPy-based plot widget for live EMG signal visualization.

    Extends the Exercise 05 solution with:
    - All-channels mode: shows 32 channels with vertical offset
    - Signal mode awareness: adjusts y-scale for RMS vs raw signal
    - Smooth switching between single and all-channel views

    Two display modes:
    1. Single channel: one signal line, same as Ex05
    2. All channels: 32 signal lines stacked vertically with offset

    The visible window is always 10 seconds wide. Time labels move
    from right to left, and the range is allowed to start below 0
    during the first seconds (same behavior as Ex05).
    """

    NUM_CHANNELS = 32

    def __init__(self, visible_duration_seconds=10.0, y_scale=300.0):
        super().__init__()

        self.visible_duration_seconds = visible_duration_seconds
        self.y_scale = y_scale
        self.current_signal_time = 0.0
        self.time_tick_step = 5.0
        self.showing_all_channels = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # VisPy canvas setup — same as Ex05
        self.canvas = scene.SceneCanvas(
            keys="interactive",
            show=False,
            bgcolor="white",
            size=(1000, 600),
        )

        self.view = self.canvas.central_widget.add_view()
        self.view.camera = "panzoom"

        # Single-channel signal line (blue, same color as Ex05)
        self.signal_line = scene.Line(
            pos=np.array([[0.0, 0.0], [0.0, 0.0]], dtype=float),
            color=(0.1, 0.3, 0.8, 1.0),
            parent=self.view.scene,
            width=2,
        )

        # 32 lines for all-channels mode, each with a unique color
        self.channel_lines = []
        colors = self._generate_channel_colors(self.NUM_CHANNELS)
        for i in range(self.NUM_CHANNELS):
            line = scene.Line(
                pos=np.array([[0.0, 0.0], [0.0, 0.0]], dtype=float),
                color=colors[i],
                parent=self.view.scene,
                width=1.5,
            )
            line.visible = False
            self.channel_lines.append(line)

        # Channel labels for all-channels mode
        self.channel_labels = []
        for i in range(self.NUM_CHANNELS):
            label = scene.Text(
                text=f"Ch {i + 1}",
                color="black",
                font_size=8,
                anchor_x="right",
                anchor_y="center",
                parent=self.view.scene,
            )
            label.visible = False
            self.channel_labels.append(label)

        # X-axis line at the bottom
        self.x_axis_line = scene.Line(
            pos=np.array(
                [[0.0, -self.y_scale],
                 [self.visible_duration_seconds, -self.y_scale]],
                dtype=float,
            ),
            color=(0.0, 0.0, 0.0, 1.0),
            parent=self.view.scene,
            width=1,
        )

        # Y-axis line on the left
        self.y_axis_line = scene.Line(
            pos=np.array(
                [[0.0, -self.y_scale], [0.0, self.y_scale]],
                dtype=float,
            ),
            color=(0.0, 0.0, 0.0, 1.0),
            parent=self.view.scene,
            width=1,
        )

        # Tick marks on the x-axis (connect="segments" draws pairs)
        self.tick_line = scene.Line(
            pos=np.empty((0, 2), dtype=float),
            color=(0.0, 0.0, 0.0, 1.0),
            parent=self.view.scene,
            width=1,
            connect="segments",
        )

        # Time labels below the x-axis (pool of 8 reusable texts)
        self.time_texts = []
        for _ in range(8):
            text = scene.Text(
                text="",
                color="black",
                font_size=10,
                anchor_x="center",
                anchor_y="top",
                parent=self.view.scene,
            )
            self.time_texts.append(text)

        layout.addWidget(self.canvas.native)

        self._update_axes()
        self._update_time_ticks()
        self._update_camera()

    def _generate_channel_colors(self, n):
        """Generate n distinct colors using HSV color space."""
        colors = []
        for i in range(n):
            hue = i / n
            # Convert HSV to RGB (saturation=0.8, value=0.85)
            import colorsys
            r, g, b = colorsys.hsv_to_rgb(hue, 0.8, 0.85)
            colors.append((r, g, b, 1.0))
        return colors

    def set_y_scale(self, y_scale):
        """Update the y-axis range and redraw axes."""
        self.y_scale = float(y_scale)
        self._update_axes()
        self._update_time_ticks()
        self._update_camera()

    def set_signal_time(self, signal_time_seconds):
        """Receive current signal time from the ViewModel."""
        self.current_signal_time = float(signal_time_seconds)
        self._update_time_ticks()

    def set_mode_all_channels(self, show_all):
        """
        Switch between single-channel and all-channels display.

        Hides/shows the appropriate line visuals.
        """
        self.showing_all_channels = show_all

        # Toggle visibility: single line vs 32 channel lines
        self.signal_line.visible = not show_all
        for line in self.channel_lines:
            line.visible = show_all
        for label in self.channel_labels:
            label.visible = show_all

    def update_plot(self, x, y):
        """
        Update the single-channel VisPy plot with new data.

        Called by the ViewModel via the plot_updated signal.
        Uses the same display_x offset logic as Ex05 so the signal
        enters from the right during the first seconds.
        """
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)

        if x.size < 2 or y.size < 2:
            return

        newest_time = x[-1]

        # Offset so newest sample is at the right edge of the window
        display_x = x - newest_time + self.visible_duration_seconds

        # Clip to visible range
        keep = (display_x >= 0.0) & (display_x <= self.visible_duration_seconds)
        display_x = display_x[keep]
        y = y[keep]

        if display_x.size < 2:
            return

        pos = np.column_stack((display_x, y))
        self.signal_line.set_data(pos=pos)

        self._update_camera()

    def update_all_channels(self, x, all_channel_data):
        """
        Update the all-channels VisPy plot.

        Each channel is offset vertically so they don't overlap.
        Channel 0 is at the top, channel 31 at the bottom.

        Parameters
        ----------
        x : np.ndarray
            Time axis (1D).
        all_channel_data : np.ndarray
            2D array of shape (32, n_samples).
        """
        x = np.asarray(x, dtype=float)
        all_channel_data = np.asarray(all_channel_data, dtype=float)

        if x.size < 2:
            return

        newest_time = x[-1]
        display_x = x - newest_time + self.visible_duration_seconds

        keep = (display_x >= 0.0) & (display_x <= self.visible_duration_seconds)
        display_x = display_x[keep]

        if display_x.size < 2:
            return

        n_channels = all_channel_data.shape[0]

        # Vertical spacing between channels
        spacing = self.y_scale * 2 / (n_channels + 1)

        for ch in range(n_channels):
            y = all_channel_data[ch, keep]

            # Normalize each channel to fit within the spacing
            y_range = np.ptp(y) if np.ptp(y) > 0 else 1.0
            y_normalized = (y - np.mean(y)) / y_range * spacing * 0.4

            # Offset: channel 0 at top, channel 31 at bottom
            offset = self.y_scale - spacing * (ch + 1)
            y_display = y_normalized + offset

            pos = np.column_stack((display_x, y_display))
            self.channel_lines[ch].set_data(pos=pos)

            # Position the channel label at the left edge
            self.channel_labels[ch].pos = (-0.3, offset)

        self._update_camera()

    def _update_axes(self):
        """Redraw the x and y axis lines for the current y_scale."""
        y_min = -self.y_scale
        y_max = self.y_scale

        self.x_axis_line.set_data(
            pos=np.array(
                [[0.0, y_min], [self.visible_duration_seconds, y_min]],
                dtype=float,
            )
        )

        self.y_axis_line.set_data(
            pos=np.array(
                [[0.0, y_min], [0.0, y_max]],
                dtype=float,
            )
        )

    def _update_time_ticks(self):
        """
        Update moving time tick labels on the x-axis.

        Same logic as Ex05: the visible time range runs from
        (current_signal_time - visible_duration) to current_signal_time,
        and is NOT clamped to zero. This means during the first seconds,
        labels appear to enter from the right side.
        """
        y_min = -self.y_scale

        tick_height = 0.04 * (2 * self.y_scale)
        label_y = y_min - 0.06 * (2 * self.y_scale)

        visible_start_time = self.current_signal_time - self.visible_duration_seconds
        visible_end_time = self.current_signal_time

        first_tick = (
            math.floor(visible_start_time / self.time_tick_step)
            * self.time_tick_step
        )

        tick_values = []
        tick_time = first_tick

        while tick_time <= visible_end_time + self.time_tick_step:
            display_x = tick_time - visible_start_time

            if tick_time >= 0.0 and 0.0 <= display_x <= self.visible_duration_seconds:
                tick_values.append((tick_time, display_x))

            tick_time += self.time_tick_step

        tick_positions = []
        for _, display_x in tick_values:
            tick_positions.append([display_x, y_min])
            tick_positions.append([display_x, y_min + tick_height])

        if tick_positions:
            self.tick_line.set_data(
                pos=np.asarray(tick_positions, dtype=float)
            )
        else:
            self.tick_line.set_data(pos=np.empty((0, 2), dtype=float))

        for index, text in enumerate(self.time_texts):
            if index < len(tick_values):
                tick_time, display_x = tick_values[index]
                text.text = f"{tick_time:.0f}"
                text.pos = (display_x, label_y)
                text.visible = True
            else:
                text.visible = False

    def _update_camera(self):
        """Set the camera range to fit the current y_scale with label space."""
        label_space = 0.16 * (2 * self.y_scale)

        self.view.camera.set_range(
            x=(0.0, self.visible_duration_seconds),
            y=(-self.y_scale - label_space, self.y_scale),
            margin=0.02,
        )
