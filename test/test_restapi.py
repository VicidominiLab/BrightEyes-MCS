import os
import sys
import asyncio
import unittest
from unittest.mock import MagicMock
from fastapi import HTTPException

sys.path.insert(1, os.getcwd())

from brighteyes_mcs.libs.restapi import FastAPIServerThread


class TestFastApiStatusEndpoint(unittest.TestCase):
    def test_state_endpoint_returns_program_state_only(self):
        main_window = MagicMock()
        main_window.get_state_payload.return_value = {
            "program_state": "preview",
        }

        server = FastAPIServerThread(main_window)
        state_route = next(
            route for route in server.app.routes if getattr(route, "path", None) == "/state/"
        )

        payload = asyncio.run(state_route.endpoint())

        self.assertEqual(payload["program_state"], "preview")
        self.assertEqual(list(payload.keys()), ["program_state"])
        main_window.get_state_payload.assert_called_once_with()

    def test_full_state_endpoint_returns_main_window_payload(self):
        main_window = MagicMock()
        main_window.get_full_status_payload.return_value = {
            "program_state": "preview",
            "acquisition_running": True,
            "started_normal": False,
            "started_preview": True,
            "completed_acquisition_count": 1,
        }

        server = FastAPIServerThread(main_window)
        full_state_route = next(
            route for route in server.app.routes if getattr(route, "path", None) == "/full_state"
        )

        payload = asyncio.run(full_state_route.endpoint())

        self.assertEqual(payload["program_state"], "preview")
        self.assertTrue(payload["acquisition_running"])
        main_window.get_full_status_payload.assert_called_once_with()

    def test_cmd_catalog_endpoint_lists_supported_commands(self):
        main_window = MagicMock()
        server = FastAPIServerThread(main_window)
        cmd_catalog_route = next(
            route for route in server.app.routes if getattr(route, "path", None) == "/cmd/"
        )

        payload = asyncio.run(cmd_catalog_route.endpoint())

        self.assertIn("supported_commands", payload)
        self.assertIn("preview", payload["supported_commands"])
        self.assertIn("acquisition", payload["supported_commands"])
        self.assertIn("stop", payload["supported_commands"])
        self.assertEqual(payload["state_endpoint"], "/state/")
        self.assertEqual(payload["full_state_endpoint"], "/full_state")

    def test_cmd_endpoint_rejects_unsupported_command(self):
        main_window = MagicMock()
        server = FastAPIServerThread(main_window)
        cmd_route = next(
            route for route in server.app.routes if getattr(route, "path", None) == "/cmd/{item}"
        )

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(cmd_route.endpoint("invalid"))

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Unsupported command", ctx.exception.detail)

    def test_openapi_documents_cmd_endpoint(self):
        main_window = MagicMock()
        main_window.get_state_payload.return_value = {"program_state": "idle"}
        main_window.get_full_status_payload.return_value = {"program_state": "idle"}
        main_window.getGUI_data.return_value = {}

        server = FastAPIServerThread(main_window)
        schema = server.app.openapi()
        cmd_catalog_operation = schema["paths"]["/cmd/"]["get"]
        cmd_operation = schema["paths"]["/cmd/{item}"]["get"]
        state_operation = schema["paths"]["/state/"]["get"]
        full_state_operation = schema["paths"]["/full_state"]["get"]

        self.assertEqual(cmd_catalog_operation["summary"], "List supported GUI commands")
        self.assertIn("supported command names", cmd_catalog_operation["description"])
        self.assertEqual(cmd_operation["summary"], "Dispatch a GUI command")
        self.assertIn("Supported commands", cmd_operation["description"])
        self.assertIn("preview", cmd_operation["description"])
        self.assertIn("acquisition", cmd_operation["description"])
        self.assertIn("stop", cmd_operation["description"])
        self.assertIn("/state/", cmd_operation["description"])
        self.assertIn("/full_state", cmd_operation["description"])
        self.assertEqual(state_operation["summary"], "Get the current program state")
        self.assertEqual(full_state_operation["summary"], "Get the full acquisition state")
        parameter_schema_description = cmd_operation["parameters"][0]["schema"]["description"]
        self.assertIn("Supported values", parameter_schema_description)


if __name__ == "__main__":
    unittest.main()
