import subprocess
import sys


def install_requirements():
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            check=True,
        )
        print("Requirements installed successfully.")
    except subprocess.CalledProcessError as exc:
        print(f"Failed to install requirements: {exc}")
        sys.exit(1)


def check_compiled_extensions():
    from test import check_compiled_extensions

    check_compiled_extensions.test()


if __name__ == "__main__":
    if "--help" in sys.argv or "-h" in sys.argv or "/?" in sys.argv:
        print(
            "This script installs the requirements of BrightEyes-MCS.\r\n\r\n"
            "Compiled extension modules are provided by the "
            "brighteyes-mcs-cylibs wheel from pip; this project no longer "
            "builds them locally.\r\n\r\n"
            "Arguments\r\n"
            "--no--install-requirements  Skip pip install -r requirements.txt\r\n"
            "--no--compile               Accepted for backward compatibility; ignored\r\n"
            "--force-msys2               Accepted for backward compatibility; ignored\r\n"
            "--force-vs                  Accepted for backward compatibility; ignored\r\n"
            "--do-not-upgrade-msys2      Accepted for backward compatibility; ignored\r\n"
        )
        raise SystemExit(0)

    no_install_requirements = "--no--install-requirements" in sys.argv

    if no_install_requirements:
        print("Ignore install requirements.txt")
    else:
        install_requirements()

    print(
        "Compiled extension modules are installed from brighteyes-mcs-cylibs; "
        "no local compilation is performed."
    )
    check_compiled_extensions()
