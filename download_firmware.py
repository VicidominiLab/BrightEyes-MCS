import sys, os
import requests, zipfile
from io import BytesIO
import markdown
from PySide2.QtCore import Qt, QThread, Signal
from PySide2.QtWidgets import QMainWindow, QApplication, QPushButton, QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel, QMessageBox, QTextBrowser, QProgressDialog, QDialog, QProgressBar, QVBoxLayout

# Define the URL of the Markdown file you want to download
md_url = "https://raw.githubusercontent.com/VicidominiLab/BrightEyes-MCSLL/refs/heads/main/LICENSE.md"

zip_url = "https://github.com/VicidominiLab/BrightEyes-MCSLL/archive/refs/heads/main.zip"

extract_directory = "brighteyes_mcs/bitfiles"

class DownloadThread(QThread):
    download_progress = Signal(int)

    def __init__(self, url):
        super().__init__()
        self.url = url
        self.response = None
        self.total_size = 0

    def run(self):
        try:
            # Start streaming the download
            self.response = requests.get(self.url, stream=True)
            self.response.raise_for_status()  # Check for HTTP errors
            self.total_size = int(self.response.headers.get('content-length', 0))
            print(self.url)
            print(self.response)
            print(self.response.headers.get('content-length', 0))
            if self.total_size==0:
                msgBox = QMessageBox()
                msgBox.setText(f"The length of the 'content-length'=0 of \n{self.url}\n"
                                "Probabily too many downloads attempts.     \n "
                                "Try later or download it manually from {self.url}\n"
                                "and extract in the folder brighteyes_mcs/bitfiles.\n"
)
                msgBox.exec_()
                error_message = (
                    "====================================================\n"
                    "ERROR: Firmware Downloading Failed\n"
                    f"Please download it manually from {self.url}\n"
                    "and extract in the folder brighteyes_mcs/bitfiles.\n"
                    "====================================================\n"
                )
                print(error_message)


            downloaded_size = 0
            chunk_size = 1024  # 1KB
            content = BytesIO()

            # Download in chunks and update progress
            for chunk in self.response.iter_content(chunk_size=chunk_size):
                if chunk:  # Filter out keep-alive chunks
                    content.write(chunk)
                    downloaded_size += len(chunk)
                    progress_percent = int(downloaded_size / self.total_size * 100)
                    self.download_progress.emit(progress_percent)

            content.seek(0)
            self.content = content  # Store the content for extraction later

        except requests.exceptions.RequestException as e:
            print(f"Error fetching the ZIP file: {e}")
            error_message = (
                "=============================================\n"
                "ERROR: Firmware Downloading Failed\n"
                f"Please download it manually from {self.url}\n"
                "and extract in the folder brighteyes_mcs/bitfiles."
                "============================================="
            )
            print(error_message)
            msgBox = QMessageBox()
            msgBox.setText("Firmware Downloading Failed. Check details on console.")
            msgBox.exec_()

class ProgressDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Downloading Firmware")
        self.setGeometry(300, 300, 400, 100)

        layout = QVBoxLayout(self)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setMaximum(100)
        layout.addWidget(self.progress_bar)

    def set_progress(self, value):
        self.progress_bar.setValue(value)

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        # Create a container for the browser and the buttons
        container = QWidget(self)
        container_layout = QVBoxLayout()

        # Create a QTextBrowser to display the downloaded Markdown content
        self.text_browser = QTextBrowser(self)
        container_layout.addWidget(self.text_browser)

        # Download and display the markdown content
        self.download_markdown(md_url)

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

        # Accept button starts as disabled
        self.accept_button = QPushButton("Accept", self)
        self.accept_button.setEnabled(False)  # Disable it initially
        self.accept_button.clicked.connect(self.accept)

        # Decline button
        self.decline_button = QPushButton("Decline", self)
        self.decline_button.clicked.connect(self.decline)

        button_layout.addWidget(self.accept_button)
        button_layout.addWidget(self.decline_button)

        bottom_frame.setLayout(button_layout)
        container_layout.addWidget(bottom_frame)

        container.setLayout(container_layout)
        self.setCentralWidget(container)

        # Connect the vertical scrollbar to track scrolling
        self.text_browser.verticalScrollBar().valueChanged.connect(self.check_scroll_position)

    def download_markdown(self, url):
        try:
            # Download the Markdown content from the URL
            response = requests.get(url)
            response.raise_for_status()  # Check for HTTP errors

            md_text = response.text

            # Convert the markdown to HTML
            html_text = markdown.markdown(md_text)

            # Display the HTML content in the QTextBrowser
            self.text_browser.setHtml(html_text)

        except requests.exceptions.RequestException as e:
            # Handle any network-related errors
            self.text_browser.setText(f"Error fetching the markdown file: {e}")

    def check_scroll_position(self):
        """ Enable the 'Accept' button when the user scrolls to the bottom of the QTextBrowser. """
        scrollbar = self.text_browser.verticalScrollBar()
        # Check if the scrollbar is at the bottom
        if scrollbar.value() == scrollbar.maximum():
            self.accept_button.setEnabled(True)  # Enable the button when scrolled to the bottom

    def accept(self):
        print("Accepted")

        # Show a progress dialog during the download
        self.accept_button.setEnabled(False)
        self.decline_button.setEnabled(False)
        self.progress_dialog = ProgressDialog()
        self.progress_dialog.show()

        # Start the download in a separate thread
        self.download_thread = DownloadThread(zip_url)
        self.download_thread.download_progress.connect(self.progress_dialog.set_progress)
        self.download_thread.finished.connect(self.on_download_complete)
        self.download_thread.start()

    def on_download_complete(self):
        print("Download Complete")

        # Close the progress dialog
        self.progress_dialog.close()

        # Extract the ZIP file from the downloaded content
        with zipfile.ZipFile(self.download_thread.content) as zip_ref:
            root_zip_dir = None
            for file_info in zip_ref.infolist():
                if file_info.is_dir():
                    root_zip_dir = file_info.filename

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
                    os.rename(a, b)
                    print(f"File moved from {a} successfully to {b}")
                except FileExistsError:
                    os.replace(a, b)
                    print(f"File replaced from {a} successfully to {b}")
        if root_zip_dir is not None:
            print(f"This folder should be deleted {root_zip_dir}")

        success_message = (
            "=============================================\n"
            "Great! Firmware downloaded correctly.\n"
            "============================================="
        )
        print(success_message)

        msgBox = QMessageBox()
        msgBox.setText("Great! Firmware downloaded correctly. The program will close.")
        msgBox.exec_()

        self.close()

    def decline(self):
        print("Declined")

        msgBox = QMessageBox()
        msgBox.setText("License not accepted. The program will close.")
        msgBox.exec_()

        self.close()

app = QApplication(sys.argv)
window = MainWindow()
window.show()
app.exec_()
