from PySide2.QtWidgets import QApplication
from PySide2.QtCore import Qt
import sys
import ttm_widget

app = QApplication(sys.argv)
app.setAttribute(Qt.AA_EnableHighDpiScaling)

window = ttm_widget.TtmWidget(sys.argv)
window.show()

sys.exit(app.exec_())
