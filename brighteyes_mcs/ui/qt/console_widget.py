"""Application console: live object access, script execution, and kernel ownership."""

import tokenize

from IPython.utils.capture import capture_output
from PySide6.QtWidgets import QApplication
from qtconsole.inprocess import QtInProcessKernelManager
from qtconsole.rich_jupyter_widget import RichJupyterWidget


class _ConsoleSession:
    """Own the kernel separately from the widget's presentation state."""

    def __init__(self):
        self.closed = False
        self.manager = QtInProcessKernelManager()
        self.client = None
        try:
            self.manager.start_kernel(show_banner=True)
            self.manager.kernel.gui = "qt"
            self.client = self.manager.client()
        except Exception:
            self.close()
            raise

    def close(self):
        if not self.closed:
            self.closed = True
            try:
                if self.client is not None:
                    self.client.stop_channels()
            finally:
                if self.manager.has_kernel:
                    self.manager.shutdown_kernel()

    def publish(self, variables):
        if self.closed:
            raise RuntimeError("The application console has been shut down")
        self.manager.kernel.shell.push(variables)

    def execute_hidden(self, source):
        # In-process client replies can arrive before QtConsole records a
        # request as hidden. Capture at the shell to keep startup/plugin output
        # out of the user's console, including rich display messages.
        with capture_output():
            self.manager.kernel.shell.run_cell(source, store_history=False, silent=True)


class ConsoleWidget(RichJupyterWidget):
    """Keep the main window and script plug-in's console API in one adapter.

    The kernel runs in this process so published objects retain their identity.
    Commands therefore execute on the GUI thread, as in the existing application.
    """

    def __init__(self, namespace=None, customBanner=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.font_size = 16
        if customBanner is not None:
            self.banner = customBanner
        self.set_default_style(colors="linux")
        self._session = _ConsoleSession()
        try:
            self.kernel_manager = self._session.manager
            self.kernel_client = self._session.client
            self.kernel_client.start_channels()
            self.push_vars({} if namespace is None else namespace)
            self.execute_command(
                "%matplotlib inline\n"
                "import matplotlib.pyplot as plt\n"
                "plt.style.use('dark_background')",
                hidden=True,
            )
        except Exception:
            self.shutdown_kernel()
            raise
        self.exit_requested.connect(self._exit_application)

    def _exit_application(self, _console=None):
        self.shutdown_kernel()
        QApplication.quit()

    def shutdown_kernel(self):
        """Release channels and the kernel; repeated shutdown is harmless."""
        self._session.close()

    def closeEvent(self, event):
        self.shutdown_kernel()
        super().closeEvent(event)

    def push_vars(self, variableDict):
        """Make application objects available by name without copying them."""
        self._session.publish(variableDict)

    def print_text(self, text):
        """Insert application output above the editable prompt."""
        self._append_plain_text(str(text), before_prompt=True)

    def execute_command(self, command, hidden=False):
        """Submit complete Python/IPython input through QtConsole's public API."""
        if self._session.closed:
            raise RuntimeError("The application console has been shut down")
        if hidden:
            self._session.execute_hidden(command)
        else:
            self.execute(source=command, hidden=False, interactive=False)

    def run_script(self, script_path):
        """Run a Python file in the shared namespace, respecting its encoding."""
        with tokenize.open(script_path) as script:
            source = script.read()
        self.execute_command(source)
