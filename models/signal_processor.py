import numpy as np
from scipy import signal as scipy_signal


class SignalProcessor:
    """
    Signal processing utilities for EMG data.

    Provides bandpass filtering and RMS envelope computation,
    based on the methods from Exercise 02.

    Parameters used (documented in README):
    - Bandpass: 20–450 Hz, 4th order Butterworth, zero-phase (filtfilt)
    - RMS: 100 ms sliding window
    """

    def __init__(self, sampling_rate=2000, low_cut=20.0, high_cut=450.0,
                 filter_order=4, rms_window_ms=100.0):
        self.sampling_rate = sampling_rate
        self.low_cut = low_cut
        self.high_cut = high_cut
        self.filter_order = filter_order
        self.rms_window_ms = rms_window_ms

        # Pre-compute filter coefficients once — they don't change
        nyquist = self.sampling_rate / 2.0
        low = self.low_cut / nyquist
        high = self.high_cut / nyquist
        self.b, self.a = scipy_signal.butter(
            self.filter_order, [low, high], btype="band"
        )

        # RMS window size in samples: 100 ms * 2000 Hz = 200 samples
        self.rms_window_size = int(
            (self.rms_window_ms / 1000.0) * self.sampling_rate
        )

    def apply_bandpass(self, data):
        """
        Apply a 4th order Butterworth bandpass filter (20–450 Hz).

        Uses filtfilt for zero phase distortion — the signal is filtered
        forward and backward, so there is no time delay in the output.

        Parameters
        ----------
        data : np.ndarray
            1D signal array (single channel).

        Returns
        -------
        np.ndarray
            Filtered signal, same length as input.
        """
        if data.shape[0] < 13:
            # filtfilt needs at least 3 * max(len(a), len(b)) samples
            # with a 4th order filter that's 3 * 5 = 15, but 13 is the
            # padlen default. Return zeros if not enough data yet.
            return np.zeros_like(data)

        return scipy_signal.filtfilt(self.b, self.a, data)

    def apply_rms(self, data):
        """
        Compute the RMS envelope using a sliding window.

        RMS = sqrt(mean(x^2)) over a window of 100 ms.
        Uses convolution with a uniform kernel for efficiency,
        which is much faster than the loop-based version from Ex02.

        Parameters
        ----------
        data : np.ndarray
            1D signal array (single channel). Should be filtered first.

        Returns
        -------
        np.ndarray
            RMS envelope, same length as input.
        """
        if data.shape[0] < self.rms_window_size:
            return np.zeros_like(data)

        # Square the signal, smooth with uniform window, take sqrt
        squared = data ** 2
        kernel = np.ones(self.rms_window_size) / self.rms_window_size
        mean_squared = np.convolve(squared, kernel, mode="same")
        return np.sqrt(mean_squared)

    def process_channel(self, data, mode):
        """
        Process a single channel according to the selected signal mode.

        Parameters
        ----------
        data : np.ndarray
            Raw 1D signal for one channel.
        mode : str
            One of "Original", "Filtered", "RMS".

        Returns
        -------
        np.ndarray
            Processed signal.
        """
        if mode == "Original":
            return data
        elif mode == "Filtered":
            return self.apply_bandpass(data)
        elif mode == "RMS":
            # RMS is computed on the filtered signal, not the raw signal
            filtered = self.apply_bandpass(data)
            return self.apply_rms(filtered)
        else:
            return data

    def process_all_channels(self, all_channel_data, mode):
        """
        Process all 32 channels according to the selected signal mode.

        Parameters
        ----------
        all_channel_data : np.ndarray
            2D array of shape (32, n_samples).
        mode : str
            One of "Original", "Filtered", "RMS".

        Returns
        -------
        np.ndarray
            Processed data, same shape as input.
        """
        if mode == "Original":
            return all_channel_data

        result = np.zeros_like(all_channel_data)
        for ch in range(all_channel_data.shape[0]):
            result[ch, :] = self.process_channel(
                all_channel_data[ch, :], mode
            )
        return result
