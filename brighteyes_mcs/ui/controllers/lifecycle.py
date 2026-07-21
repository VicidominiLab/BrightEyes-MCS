"""Runtime status projection shared by the Qt UI and HTTP adapter."""

from __future__ import annotations

from datetime import datetime


class LifecycleController:
    @staticmethod
    def timestamp():
        return datetime.now().astimezone().isoformat(timespec="seconds")

    def transition(self, window, state, reason=""):
        window.program_state = state
        window.program_state_reason = reason
        window.program_state_changed_at = self.timestamp()

    @staticmethod
    def state_payload(window):
        return {"program_state": window.program_state}

    @staticmethod
    def full_status_payload(window):
        return {
            "program_state": window.program_state,
            "allowed_program_states": list(window.PROGRAM_STATES),
            "program_state_reason": window.program_state_reason,
            "program_state_changed_at": window.program_state_changed_at,
            "acquisition_running": window.started_normal or window.started_preview,
            "started_normal": window.started_normal,
            "started_preview": window.started_preview,
            "do_not_save": getattr(window, "do_not_save", False),
            "last_requested_filename": window.last_requested_filename,
            "last_saved_filename": window.last_saved_filename,
            "last_completed_filename": window.last_completed_filename,
            "acquisition_run_id": window.acquisition_run_id,
            "preview_run_id": window.preview_run_id,
            "completed_acquisition_count": window.completed_acquisition_count,
            "last_acquisition_started_at": window.last_acquisition_started_at,
            "last_preview_started_at": window.last_preview_started_at,
            "last_acquisition_completed_at": window.last_acquisition_completed_at,
            "http_server_running": window.http_server_thread is not None,
        }
