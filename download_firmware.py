from PySide2.QtCore import Qt, QUrl
from PySide2.QtWidgets import QMainWindow, QApplication, QPushButton, QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel, QMessageBox
from PySide2.QtWebEngineWidgets import QWebEngineView

import sys, os

import requests, zipfile
from io import BytesIO

# Define the URL of the ZIP file you want to download
zip_url = "https://github.com/VicidominiLab/BrightEyes-MCSLL/archive/refs/heads/main.zip"
extract_directory = "brighteyes_mcs/bitfiles"

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        # Create a container for the browser and the buttons
        container = QWidget(self)
        container_layout = QVBoxLayout()

        self.browser = QWebEngineView()
        self.browser.setUrl(QUrl("https://github.com/VicidominiLab/BrightEyes-MCSLL"))

        container_layout.addWidget(self.browser)

        # Create a label
        label = QLabel("BrightEyes-MCS is under General Public License version 3 (GPLv3).\n"
                       "The firmwares instead are part of BrightEyes-MCSLL which is NOT under GPLv3.\n"
                       "The firmwares are free of usage under certain usage described by the license above.\n\n"
                       "Please read carefully the License above and then click below your choice.\n")
        label.setAlignment(Qt.AlignCenter)

        container_layout.addWidget(label)

        # Create a frame for the buttons at the bottom
        bottom_frame = QFrame()
        bottom_frame.setFrameShape(QFrame.StyledPanel)

        # Create a horizontal layout for the buttons
        button_layout = QHBoxLayout()

        accept_button = QPushButton("Accept", self)
        accept_button.clicked.connect(self.accept)

        decline_button = QPushButton("Decline", self)
        decline_button.clicked.connect(self.decline)

        button_layout.addWidget(accept_button)
        button_layout.addWidget(decline_button)

        bottom_frame.setLayout(button_layout)
        container_layout.addWidget(bottom_frame)

        container.setLayout(container_layout)
        self.setCentralWidget(container)

    def accept(self):
        print("Accepted")

        # Download the ZIP file and store it in a BytesIO buffer
        response = requests.get(zip_url)

        if response.status_code == 200:
            with BytesIO(response.content) as buffer:
                # Extract the contents from the buffer
                with zipfile.ZipFile(buffer) as zip_ref:
                    root_zip_dir=None
                    for file_info in zip_ref.infolist():
                        if file_info.is_dir():
                            root_zip_dir = file_info.filename

                    for file_info in zip_ref.infolist():
                        if file_info.is_dir():
                            continue
                        print(file_info.filename)
                        # Get the file name without any internal directory structure
                        file_name = os.path.basename(file_info.filename)
                        # Extract the file to the current working directory
                        zip_ref.extract(file_info, path=extract_directory)
                        print(f"Files extracted successfully to {extract_directory}")
                        # Rename the extracted file to remove the directory structure
                        a = os.path.join(extract_directory, file_info.filename)
                        b = os.path.join(extract_directory, file_name)
                        try:
                            os.rename(a,b)
                            print(f"File moved from {a} successfully to {b}")
                        except FileExistsError:
                            os.replace(a,b)
                            print(f"File replaced from {a} successfully to {b}")
            if root_zip_dir is not None:
                print(f"This folder should be deleted {root_zip_dir}")
            msgBox = QMessageBox()
            msgBox.setText("Great! Firmware downloaded correctly. The program will close.")
            msgBox.exec_()
        else:
            print("Failed to download the ZIP file.")
            msgBox = QMessageBox()
            msgBox.setText("Failed to download the firmware. You can download it manually from https://github.com/VicidominiLab/BrightEyes-MCSLL/ and extract in the folder brighteyes_mcs/bitfiles.")
            msgBox.exec_()
        self.close()
    def decline(self):
        print("Declined")
        msgBox = QMessageBox()
        msgBox.setText(
            "License not accepted. The program will close.")
        msgBox.exec_()
        self.close()

app = QApplication(sys.argv)
window = MainWindow()
window.show()
app.exec_()
