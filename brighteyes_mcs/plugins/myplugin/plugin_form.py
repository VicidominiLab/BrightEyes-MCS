from .gui.plugin_gui import Ui_Form
from PySide2.QtCore import Slot

class myForm(Ui_Form):
    """
    An example of implementation of the QWidget used by the plugin
    """

    @Slot()
    def prova(self):
        self.pushButton.setText("CIAO")
        self.pushButton_2.setText("CIAO")
        print("prova")

    def setupUi(self, Form):
        super().setupUi(Form)
        self.pushButton.clicked.connect(self.prova)
