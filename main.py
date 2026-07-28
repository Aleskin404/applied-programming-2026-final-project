"""
TCP EMG Viewer — Final Project
Applied Programming 2026 (N² Lab, FAU)

Entry point for the PySide6 desktop application.
Creates the ViewModel and View following the MVVM pattern,
then starts the Qt event loop.

Usage:
    1. Start the TCP server:  python TCP_Server/main.py
    2. Start this application: python main.py
    3. Click "Connect" to begin live streaming
"""

import sys
from PySide6.QtWidgets import QApplication

from viewmodels.main_viewmodel import MainViewModel
from views.main_view import MainView


def main():
    app = QApplication(sys.argv)

    # ViewModel is created first — it owns the models
    view_model = MainViewModel()

    # View receives the ViewModel and connects signals to widgets
    view = MainView(view_model)
    view.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
