"""Preview selection independent from Qt widget rendering."""


class PreviewController:
    @staticmethod
    def image(manager, fallback, projection="xy", rgb=False):
        if manager.shared_arrays_ready:
            return manager.getPreviewImage(projection, rgb)
        return fallback

    @staticmethod
    def flat_data(manager, active_file):
        if active_file:
            return None
        return manager.getPreviewFlatData()
