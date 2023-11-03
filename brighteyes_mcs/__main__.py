print(__name__)

if __name__ == "__main__":
    import sys
    import os

    print("args", sys.argv)
    from pathlib import Path

    print("Current Working Directory", os.getcwd())
    path = Path(__file__).parent.absolute()
    os.chdir(path)
    print("Current Working Directory moved to ", os.getcwd())

    from PySide2.QtWidgets import QApplication
    from PySide2.QtCore import Qt

    # import qdarkstyle # fancy dark style

    import qdarktheme

    # import gui.MainWindow as MainWindow
    from .gui import MainWindow

    import platform

    import ctypes

    if any(platform.win32_ver()):
        myappid = "iit.mms.brighteyesmcs.1"  # arbitrary string
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    qdarktheme.enable_hi_dpi()

    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_EnableHighDpiScaling)
    # app.setStyleSheet(qdarkstyle.load_stylesheet())

    qdarktheme.setup_theme()

    window = MainWindow(sys.argv)
    window.show()

    sys.exit(app.exec_())
