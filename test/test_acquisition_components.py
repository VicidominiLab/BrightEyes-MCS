import unittest
from types import SimpleNamespace

from brighteyes_mcs.acquisition.coordinator import AcquisitionCoordinator
from brighteyes_mcs.acquisition.process_supervisor import ProcessSupervisor
from brighteyes_mcs.acquisition.state import AcquisitionState


class FakeProcess:
    def __init__(self):
        self.started = False
        self.stopped = False
        self.alive = False
        self.terminated = False

    def start(self):
        self.started = self.alive = True

    def stop(self):
        self.stopped = True
        self.alive = False

    def join(self, timeout=None):
        pass

    def is_alive(self):
        return self.alive

    def terminate(self):
        self.terminated = True
        self.alive = False


class TestProcessSupervisor(unittest.TestCase):
    def test_registered_process_has_consistent_start_and_stop(self):
        process = FakeProcess()
        supervisor = ProcessSupervisor()
        supervisor.register("worker", process)
        supervisor.start("worker")
        self.assertTrue(supervisor.is_alive("worker"))
        supervisor.stop("worker")
        self.assertTrue(process.stopped)
        self.assertFalse(supervisor.is_alive("worker"))


class TestAcquisitionCoordinator(unittest.TestCase):
    def test_state_follows_backend_lifecycle(self):
        backend = SimpleNamespace(
            do_not_save_event=SimpleNamespace(is_set=lambda: True),
            _run_pipeline=lambda: None,
            _stop_pipeline=lambda: None,
        )
        coordinator = AcquisitionCoordinator(backend)
        coordinator.run()
        self.assertEqual(coordinator.state, AcquisitionState.PREVIEWING)
        coordinator.stop()
        self.assertEqual(coordinator.state, AcquisitionState.IDLE)


if __name__ == "__main__":
    unittest.main()
