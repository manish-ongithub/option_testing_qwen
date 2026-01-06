"""
Screener UI module.

Provides a PyQt6 graphical interface for the options screener.

Run the GUI with:
    python -m screener.ui.screener_gui
"""

# Lazy import to avoid PyQt6 dependency for non-GUI usage
def get_main_window():
    """Get the ScreenerMainWindow class (lazy import)."""
    from screener.ui.screener_gui import ScreenerMainWindow
    return ScreenerMainWindow


def run_gui():
    """Launch the screener GUI application."""
    from screener.ui.screener_gui import main
    main()


__all__ = ['get_main_window', 'run_gui']

