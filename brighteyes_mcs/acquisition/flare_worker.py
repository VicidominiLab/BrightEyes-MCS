"""Picklable Flare tasks. Device I/O and decoding never run in Qt's process."""

from dataclasses import dataclass, field
import queue
import logging

from .detectors.flare.config import configuration_from_gui


class WorkerLogHandler(logging.Handler):
    def __init__(self, mailbox):
        super().__init__(logging.INFO)
        self.mailbox = mailbox

    def emit(self, record):
        try:
            self.mailbox.put_nowait(record.getMessage())
        except (queue.Full, EOFError, BrokenPipeError, OSError):
            pass  # The session file retains diagnostics when the GUI falls behind.


def initialize_worker(log_mailbox=None):
    from ..logging_setup import configure_logging

    configure_logging()
    if log_mailbox is not None:
        logging.getLogger("brighteyes_mcs").addHandler(WorkerLogHandler(log_mailbox))


def publish_latest(mailbox, value):
    """Drop an obsolete display update, never acquisition data."""
    try:
        mailbox.put_nowait(value)
    except queue.Full:
        try:
            mailbox.get_nowait()
        except queue.Empty:
            pass
        mailbox.put_nowait(value)


@dataclass
class FlareTask:
    action: str
    settings: object = None
    controls: object = None
    arguments: dict = field(default_factory=dict)

    def __call__(self):
        from ..hardware.flare import FlareClient

        args = self.arguments
        if self.action == "convert":
            from ..storage.raw import convert_raw_acquisition

            return convert_raw_acquisition(args["metadata"], args["output"])
        if self.action == "acquire":
            return self.acquire()
        client = FlareClient(self.settings)
        try:
            if self.action == "live":
                return self.controls.apply(client)
            if self.action == "reference_factor":
                from .detectors.flare.dfd import REFERENCE_FACTOR

                discovery = client.discover()
                if not discovery["firmware"].get("board_capabilities", 0) & 0x400:
                    return {"action": self.action, "discovery": discovery, "result": None}
                # Share the configure/START lock: the toggle cannot insert a
                # raw write between an accepted configuration and START.
                result = self.controls.write(client, REFERENCE_FACTOR, args["value"])
                if result["value"] != args["value"]:
                    raise RuntimeError("Reference decimation readback differs from the requested factor")
                return {"action": "write", "discovery": discovery, "result": result}
            cached = args.get("discovery")
            if cached and self.action in ("read", "write", "read_all", "status"):
                discovery = dict(cached)
                client.catalog = {row["name"]: row for row in discovery["registers"]}
                if self.action == "status":
                    discovery["status"] = client.status()
            else:
                discovery = client.discover()
            result = discovery
            if self.action == "read":
                result = client.read_register(args["name"])
            elif self.action == "write":
                result = self.controls.write(client, args["name"], args["value"])
            elif self.action == "read_all":
                result = client.read_all()
            elif self.action in ("reset", "stop"):
                with self.controls.io_lock:
                    result = {"before_command": client.status(), "command": client.command(self.action)}
            return {"action": self.action, "discovery": discovery, "result": result}
        finally:
            client.close()

    def acquire(self):
        from ..hardware.flare import FlareClient
        from .flare import FlareAcquisition

        args = self.arguments
        values = args["values"]
        client = FlareClient(self.settings)
        try:
            client.discover()
            client.check_acquisition_support(**({"dfd": True} if values["dfd_enable"] else {}))
            configuration = configuration_from_gui(
                values, client.firmware["clock_hz"], self.settings,
                preview=args["preview"], dummy=args["dummy"],
                firmware=client.firmware,
            )
        finally:
            client.close()

        def snapshot(value):
            publish_latest(args["snapshots"], dict(
                value, geometry=self.controls.geometry() or values,
            ))

        runner = FlareAcquisition(
            self.settings, configuration, filename=args["filename"], raw_only=args["raw_only"],
            on_snapshot=snapshot, initial_image=args["initial_image"], live_controls=self.controls,
        )
        runner.cancel = args["cancel"]
        runner.gui_metadata = values
        runner.display_state = args["display"]
        return runner.run()
