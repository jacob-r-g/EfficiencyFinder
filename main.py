"""App entry point."""

import sys
from pathlib import Path

# Allow `python main.py` from any cwd.
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from PySide6.QtWidgets import QApplication

from gui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("CRISPR Amplicon Editing Efficiency")
    app.setOrganizationName("CENH3")
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
