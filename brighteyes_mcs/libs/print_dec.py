import sys, os
from datetime import datetime
import inspect

project_folder = os.getcwd() + os.sep
project_folder = os.sep.join(project_folder.split(os.sep)[:-2])

internal_debug = False


def set_debug(debug=False):
    global internal_debug
    internal_debug = debug


def print_dec(*objects, sep=" ", end="\n", file=sys.stdout, flush=False):
    global internal_debug

    if internal_debug:
        return

    try:
        filename = inspect.stack()[1].filename.replace(
            project_folder, ""
        )  # .split("\\")[-1]
        filename = filename[1:]
        lineno = inspect.stack()[1].lineno
    except:
        filename = "../.."
        lineno = "."
    print(
        "{0:70}".format(filename + ":%d" % lineno),
        "\t",
        datetime.now().strftime("%H:%M:%S.%f"),
        "\t",
        *objects,
        sep=" ",
        end="\n",
        file=sys.stdout,
        flush=False
    )
