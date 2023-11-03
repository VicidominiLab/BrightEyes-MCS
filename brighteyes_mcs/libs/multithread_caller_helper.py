from PySide2.QtCore import Slot, QRunnable


class Worker(QRunnable):
    """
    Worker thread

    Inherits from QRunnable to handler worker thread setup, signals and wrap-up.

    :param callback: The function callback to run on this worker thread. Supplied args and
                     kwargs will be passed through to the runner.
    :type callback: function
    :param args: Arguments to pass to the callback function
    :param kwargs: Keywords to pass to the callback function

    """

    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    @Slot()  # QtCore.Slot
    def run(self):
        """
        Initialise the runner function with passed args, kwargs.
        """
        self.fn(*self.args, **self.kwargs)


def pushButton_multithread_call(status_dict, threadpool, button, func, *args, **kwargs):
    if func.__name__ in status_dict:
        print("already run")
        return

    print("pushButton_multithread_call", func.__name__)

    def call_the_function():
        ttt = button.text()
        en = button.isEnabled()
        button.setText("Wait...")
        button.setEnabled(False)

        print("pushButton_meas_load_clicked")
        try:
            func(*args, **kwargs)
        except Exception as e:
            print("ERROR ", func.__name__)
            raise (e)

        status_dict.pop(func.__name__)

        button.setEnabled(en)
        button.setText(ttt)

    worker = Worker(
        call_the_function
    )  # Any other args, kwargs are passed to the run function
    threadpool.start(worker)
    print(func.__name__, "Max: ", threadpool.maxThreadCount())
    print(func.__name__, "thread.start()")
    status_dict.update({func.__name__: worker})
