"""Narrow adapter used by HTTP and other non-Qt application surfaces."""

from __future__ import annotations


class GuiApplicationGateway:
    """Expose application operations without coupling consumers to MainWindow fields."""

    def __init__(self, window):
        self.window = window

    def start_acquisition(self):
        return self.window.startButtonClicked()

    def start_preview(self):
        return self.window.previewButtonClicked()

    def stop(self):
        return self.window.stopButtonClicked()

    def state(self):
        return self.window.get_state_payload()

    def full_state(self):
        return self.window.get_full_status_payload()

    def configuration(self):
        return self.window.getGUI_data()

    def update_configuration(self, payload):
        return self.window.setGUI_data(payload)

    def preview_image_item(self):
        return self.window.im_widget.imageItem

    def fingerprint_image_item(self):
        return self.window.fingerprint_widget.imageItem

    def preview_array(self):
        return self.window.im_widget.getImageItem().image

    def fingerprint_array(self):
        return self.window.fingerprint_widget.getImageItem().image
