# Inspired by https://stackoverflow.com/questions/59731016/non-blocking-ipython-qt-console-in-a-pyqt-application

from qtconsole.rich_jupyter_widget import RichJupyterWidget
from qtconsole.inprocess import QtInProcessKernelManager

class ConsoleWidget(RichJupyterWidget):
    """ """

    def __init__(self, namespace={}, customBanner=None, *args, **kwargs):
        super(ConsoleWidget, self).__init__(*args, **kwargs)

        if customBanner is not None:
            self.banner = customBanner

        self.font_size = 16
        self.kernel_manager = QtInProcessKernelManager()
        self.kernel_manager.start_kernel(show_banner=True)
        self.kernel_manager.kernel.gui = "qt"

        self.kernel_client = self.kernel_manager.client()
        self.kernel_client.start_channels()

        self.push_vars(namespace)

        self.set_default_style(colors="linux")
        self.execute_command("%matplotlib inline", True)
        self.execute_command(
            "import matplotlib.pyplot as plt\nplt.style.use('dark_background')\n", True
        )

        def stop():
            self.kernel_client.stop_channels()
            self.kernel_manager.shutdown_kernel()
            self.guisupport.get_app_qt().exit()

        self.exit_requested.connect(stop)

    def _banner_default(self):
        return super()._banner_default()

    def push_vars(self, variableDict):
        """
        Given a dictionary containing name / value pairs, push those variables
        to the Jupyter console widget
        """
        self.kernel_manager.kernel.shell.push(variableDict)

    def clear(self):
        """
        Clears the terminal
        """
        self._control.clear()

        # self.kernel_manager

    def print_text(self, text):
        """
        Prints some plain text to the console
        """
        self._append_plain_text(text)

    def execute_command(self, command, hidden=False):
        """
        Execute a command in the frame of the console widget
        """
        self._execute(command, hidden)

    def run_script(self, script_path):
        f = open(script_path)
        self.execute(f.read(), False, interactive=True)
