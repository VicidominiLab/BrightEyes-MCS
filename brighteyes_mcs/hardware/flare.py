"""HTTP control for the Kria Flare service. No connections occur on import."""

import logging
import os
from urllib.parse import quote

import requests


log = logging.getLogger(__name__)


class FlareError(RuntimeError):
    pass


def resolve_register_name(name, catalog):
    """Resolve the same discovered names and addresses in the client and UI."""
    if name in catalog:
        return name
    constant = name.lower().removeprefix("reg_")
    if constant in catalog:
        return constant
    try:
        address = int(name, 0)
    except ValueError:
        address = None
    for canonical, entry in catalog.items():
        if address is not None and entry.get("address") == address:
            return canonical
    # Named registers absent from an older catalog still go to the server.
    return constant


class FlareClient:
    def __init__(self, settings, *, session=None, token=None):
        self.settings = settings.validate()
        host = settings.host
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        self.base_url = f"http://{host}:{settings.port}/api/v1/devices/flare0"
        self.session = session or requests.Session()
        self.session.trust_env = False
        token = os.environ.get("FLARE_API_TOKEN", "") if token is None else token
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"
        self.catalog = {}
        self.firmware = {}

    def close(self):
        self.session.close()

    def request(self, method, path, body=None):
        log.info("Flare %s %s", method, path)
        try:
            response = self.session.request(
                method, self.base_url + path, json=body, timeout=self.settings.http_timeout_seconds
            )
        except requests.RequestException as error:
            # Never retry mutations: a timeout does not prove the command failed.
            raise FlareError(
                f"{method} {path}: {type(error).__name__}; inspect status before retrying a command"
            ) from error
        try:
            result = response.json()
        except ValueError as error:
            raise FlareError(
                f"{method} {path}: HTTP {response.status_code}, invalid JSON response"
            ) from error
        if response.status_code != 200:
            message = (
                result.get("error", "Request failed")
                if isinstance(result, dict)
                else "Request failed"
            )
            errno = result.get("errno") if isinstance(result, dict) else None
            raise FlareError(
                f"{method} {path}: HTTP {response.status_code}, errno={errno}: {message}"
            )
        return result

    def discover(self):
        firmware = self.request("GET", "/firmware")
        catalog = self.request("GET", "/registers")
        commands = self.request("GET", "/commands")
        system = self.request("GET", "/system")
        if (
            not isinstance(firmware, dict)
            or not isinstance(catalog, list)
            or not isinstance(commands, list)
        ):
            raise FlareError("Malformed Flare discovery response")
        self.firmware = firmware
        self.catalog = {entry["name"]: entry for entry in catalog}
        return {
            "firmware": firmware,
            "system": system,
            "registers": catalog,
            "commands": commands,
            "status": self.status(),
        }

    def check_acquisition_support(self, *, dfd=False):
        if self.settings.mode != "master":
            raise FlareError(
                "Flare slave acquisition awaits firmware support for external NI scan timing"
            )
        if (
            self.firmware.get("board_id") != 0x464C5234
            or self.firmware.get("schema_version") not in (0x00030000, 0x00040000)
        ):
            raise FlareError(
                "Acquisition requires supported FLR4 board identity and register schema 3 or 4"
            )
        if dfd and (self.firmware.get("schema_version") != 0x40000 or
                    "dfd" not in self.firmware.get("supported_acquisition_modes", [])):
            raise FlareError("DFD requires schema-4 firmware advertising DFD acquisition support")
        clock = self.firmware.get("clock_hz")
        if isinstance(clock, bool) or not isinstance(clock, int) or clock <= 0:
            raise FlareError("Flare did not advertise a valid fabric clock")

    def status(self):
        status = self.request("GET", "/status")
        if not isinstance(status, dict) or not isinstance(status.get("dma"), dict):
            raise FlareError("Malformed Flare status response")
        return status

    def require_idle(self):
        status = self.status()
        dma = status["dma"]
        stream = status.get("stream")
        if dma.get("state") in (1, 2, 3) or (
            stream and not (stream.get("sender_done") and stream.get("acquisition_done"))
        ):
            raise FlareError(
                "Flare is busy; connecting does not take over or reset an existing acquisition"
            )
        return status

    def resolve_register(self, name):
        return resolve_register_name(name, self.catalog)

    def read_register(self, name):
        name = self.resolve_register(name)
        return self.request("GET", "/registers/" + quote(name, safe=""))

    def read_all(self):
        values = self.request("GET", "/registers_read_all")
        if not isinstance(values, dict):
            raise FlareError("Malformed Flare register readback")
        return values

    def write_register(self, name, value):
        name = self.resolve_register(name)
        # The server owns register access, value and acquisition-state policy.
        self.request("PUT", "/registers/" + quote(name, safe=""), {"value": value})
        return self.read_register(name)

    def configure(self, configuration):
        return self.request("PUT", "/configuration", configuration)

    def stream_settings(self, settings, *, stream=None):
        path = "/streams" if stream is None else "/streams/" + stream
        return self.request("POST", path, settings)

    def command(self, command):
        if command not in ("start", "stop", "reset"):
            raise ValueError("Unknown Flare command")
        return self.request("POST", "/commands/" + command, {})
