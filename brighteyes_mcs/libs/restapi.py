
import uvicorn
import threading
from fastapi import FastAPI, HTTPException, UploadFile, File, Request, Path

from fastapi.responses import StreamingResponse, Response
import io
from pyqtgraph import exporters
import json
import numpy as np

from PySide6.QtCore import (
    Signal,
    QIODevice,
    QBuffer,
    QObject)


class NumpyEncoder(json.JSONEncoder):
    """
    Custom JSON encoder for NumPy arrays
    """
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return json.JSONEncoder.default(self, obj)


class FastAPIServerThread(threading.Thread):
    """
    Thread class for running the FastAPI server
    """
    def __init__(self, main_window, host="127.0.0.1", port=8000):
        """
        Constructor for the FastAPIServerThread class that initializes the FastAPI app and the server configuration parameters (host and port)
        """
        super().__init__()
        self.host = host
        self.port = port
        self.app = FastAPI(
            title="BrightEyes-MCS HTTP API",
            description=(
                "Remote control and status API for BrightEyes-MCS.\n\n"
                "Use `/cmd/` to discover supported commands, `/cmd/{item}` to "
                "dispatch one, `/state/` to inspect the current runtime "
                "state, and `/full_state` to inspect filenames, counters, "
                "and other acquisition metadata."
            ),
            version="1.0.0",
        )
        self.main_window = main_window
        self.server = None
        command_catalog = {
            "preview": {
                "description": "Start preview mode without saving an acquisition file.",
                "resulting_program_state": "preview",
            },
            "acquisition": {
                "description": "Start a normal acquisition with saving enabled.",
                "resulting_program_state": "acquisition",
            },
            "stop": {
                "description": "Stop the current preview or acquisition.",
                "resulting_program_state": "idle or acquisition_done",
            },
        }
        supported_commands_description = ", ".join(
            "`%s`" % command for command in command_catalog
        )
        full_status_example = {
            "program_state": "idle",
            "allowed_program_states": [
                "idle",
                "acquisition",
                "preview",
                "acquisition_done",
            ],
            "program_state_reason": "startup",
            "program_state_changed_at": "2026-04-01T12:00:00+02:00",
            "acquisition_running": False,
            "started_normal": False,
            "started_preview": False,
            "do_not_save": False,
            "last_requested_filename": "C:/data/example.h5",
            "last_saved_filename": "C:/data/example.h5",
            "last_completed_filename": "C:/data/example.h5",
            "acquisition_run_id": 4,
            "preview_run_id": 7,
            "completed_acquisition_count": 3,
            "last_acquisition_started_at": "2026-04-01T11:58:00+02:00",
            "last_preview_started_at": "2026-04-01T11:55:00+02:00",
            "last_acquisition_completed_at": "2026-04-01T11:59:30+02:00",
            "http_server_running": True,
        }

        class MySignal(QObject):
            """
            Custom signal class for emitting signals to the main window
            """
            start = Signal()
            stop = Signal()
            preview = Signal()

        self.signal = MySignal()
        self.signal.start.connect(self.main_window.startButtonClicked)
        self.signal.stop.connect(self.main_window.stopButtonClicked)
        self.signal.preview.connect(self.main_window.previewButtonClicked)

        @self.app.get("/")
        async def read_root():
            """
            route that returns a simple JSON message
            """
            return {"message": "Hello, World!"}

        @self.app.get(
            "/state/",
            tags=["Status"],
            summary="Get the current program state",
            description=(
                "Return only the current BrightEyes-MCS program state."
            ),
            responses={
                200: {
                    "description": "Current application state payload.",
                    "content": {
                        "application/json": {
                            "example": {"program_state": "idle"}
                        }
                    },
                },
            },
        )
        async def read_state():
            """
            route that returns only the current main window program state
            """
            return self.main_window.get_state_payload()

        @self.app.get(
            "/full_state",
            tags=["Status"],
            summary="Get the full acquisition state",
            description=(
                "Return the current BrightEyes-MCS runtime state together with "
                "useful metadata such as filenames, counters, timestamps, and "
                "whether a preview or acquisition is currently running."
            ),
            responses={
                200: {
                    "description": "Current full application status payload.",
                    "content": {
                        "application/json": {
                            "example": full_status_example
                        }
                    },
                },
            },
        )
        async def read_full_state():
            """
            route that returns the full main window status payload
            """
            return self.main_window.get_full_status_payload()

        @self.app.get("/gui/")
        async def read_gui():
            """
            route that returns the GUI data as a JSON string
            """
            mydict = self.main_window.getGUI_data()

            return json.dumps(mydict, cls=NumpyEncoder)

        @self.app.get("/gui/{item}")
        async def read_gui_item(item: str = None):
            """
            route that returns a specific item from the GUI data as a JSON string
            if the item is 'all', the entire GUI data is returned
            otherwise, the specific item is returned
            """
            mydict = self.main_window.getGUI_data()

            if item == 'all':
                return json.dumps(mydict, cls=NumpyEncoder)
            else:
                return json.dumps(mydict[item], cls=NumpyEncoder)

        @self.app.get(
            "/cmd/",
            tags=["Commands"],
            summary="List supported GUI commands",
            description=(
                "Return the supported command names for `/cmd/{item}` together "
                "with a short description and the expected program state."
            ),
            responses={
                200: {
                    "description": "Supported command catalog.",
                    "content": {
                        "application/json": {
                            "example": {
                                "supported_commands": command_catalog,
                                "state_endpoint": "/state/",
                                "full_state_endpoint": "/full_state",
                                "notes": [
                                    "Use `/cmd/{item}` to dispatch a command.",
                                    "Use `/state/` after dispatching a command to inspect the resulting state.",
                                    "Use `/full_state` for filenames, counters, and timestamps.",
                                ],
                            }
                        }
                    },
                },
            },
        )
        async def list_commands():
            """
            route that returns the supported commands for the command dispatcher
            """
            return {
                "supported_commands": command_catalog,
                "state_endpoint": "/state/",
                "full_state_endpoint": "/full_state",
                "notes": [
                    "Use `/cmd/{item}` to dispatch a command.",
                    "Use `/state/` after dispatching a command to inspect the resulting state.",
                    "Use `/full_state` for filenames, counters, and timestamps.",
                ],
            }

        @self.app.get(
            "/cmd/{item}",
            tags=["Commands"],
            summary="Dispatch a GUI command",
            description=(
                "Supported commands:\n"
                "- `preview`: start preview mode without saving a file.\n"
                "- `acquisition`: start a normal acquisition with saving enabled.\n"
                "- `stop`: stop the current preview or acquisition.\n\n"
                "Call `/state/` after dispatching a command to inspect the current "
                "program state. Call `/full_state` when you also need the last "
                "filename, counters, and acquisition timestamps."
            ),
            responses={
                200: {
                    "description": "Command accepted by the GUI dispatcher.",
                    "content": {
                        "application/json": {
                            "example": "Done"
                        }
                    },
                },
                400: {
                    "description": "Unsupported command name.",
                },
            },
        )
        async def dispatch_command(
            item: str = Path(
                ...,
                description="Supported values: %s." % supported_commands_description,
            )
        ):
            """
             route that receives a command and emits a signal to the main window based on the command
             preview: emits the preview signal
             acquisition: emits the start signal
             stop: emits the stop signal
            """
            if item not in command_catalog:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Unsupported command '%s'. Supported commands: %s"
                        % (item, ", ".join(command_catalog.keys()))
                    ),
                )

            if item == "preview":
                print("preview")
                self.signal.preview.emit()
            if item == "acquisition":
                print("acquisition")
                self.signal.start.emit()
            if item == "stop":
                print("stop")
                self.signal.stop.emit()

            return "Done"

        @self.app.put("/set")
        async def update_item(request: Request):
            """
            route that receives a JSON object and updates the GUI data with the received object
            sets a particular GUI data to the received object and returns a JSON response with the status
            """
            try:
                mydict = await request.json()
                mydict_processed = {}
                for i in mydict.keys():
                    d = mydict[i]
                    if d != '':
                        mydict_processed.update({i:d})
                    print(mydict)
                if len(mydict_processed.keys()) > 0:
                    print(mydict_processed)
                    self.main_window.setGUI_data(mydict_processed)
                    return {"status": "OK"}
                else:
                    return {"status": "BAD"}
            except Exception as e:
                print(f"Error: {e}")
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.post("/array/")
        async def receive_array(file: UploadFile = File(...), shape: str = "", dtype: str = "float64"):
            """
            DUMMY FOR TESTING PURPOSES
            route that receives a NumPy array as a binary file and converts it to a NumPy array
            """
            try:
                # Read the file contents into bytes
                data = await file.read()

                # Log the received data length
                print(f"Received data length: {len(data)} bytes")

                # Convert the shape from string to tuple
                shape_tuple = tuple(map(int, shape.split(',')))

                # Log the received shape and dtype
                print(f"Received shape: {shape_tuple}, dtype: {dtype}")

                # Create the NumPy array from the binary data
                np_array = np.frombuffer(data, dtype=dtype).reshape(shape_tuple)

                return {"message": "Array received", "shape": np_array.shape}
            except Exception as e:
                # Log the exception message
                print(f"Error: {e}")
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.get("/preview.png")
        async def send_array():
            """
            route that returns the preview image as a PNG image
            """
            try:
                # Create a sample NumPy array

                exporter = exporters.ImageExporter(main_window.im_widget.imageItem)

                # Save the image to a buffer
                buffer = io.BytesIO()
                image = exporter.export(toBytes=True)
                buffer = QBuffer()
                buffer.open(QIODevice.WriteOnly)
                image.save(buffer, "PNG")

                buffer.seek(0)
                data = buffer.data().data()
                return Response(data, media_type="image/png")

            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/fingerprint.png")
        async def send_array():
            """
            route that returns the fingerprint image as a PNG image
            """
            try:

                exporter = exporters.ImageExporter(main_window.fingerprint_widget.imageItem)

                # Save the image to a buffer
                buffer = io.BytesIO()
                image = exporter.export(toBytes=True)
                buffer = QBuffer()
                buffer.open(QIODevice.WriteOnly)
                image.save(buffer, "PNG")

                buffer.seek(0)
                data = buffer.data().data()
                return Response(data, media_type="image/png")
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/preview.np")
        async def send_array():
            """
            route that returns the preview image as a NumPy array
            """
            try:
                # Create a sample NumPy array
                np_array = main_window.im_widget.getImageItem().image

                # Convert the array to bytes
                array_bytes = np_array.tobytes()
                shape_str = ','.join(map(str, np_array.shape))
                dtype_str = str(np_array.dtype)
                headers = {
                    "X-Shape": shape_str,
                    "X-Dtype": dtype_str
                }
                buffer = io.BytesIO(array_bytes)
                return StreamingResponse(buffer, media_type="application/octet-stream", headers=headers)
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/fingerprint.np")
        async def send_array():
            """
            route that returns the fingerprint image as a NumPy array
            """
            try:
                # Create a sample NumPy array
                np_array = main_window.fingerprint_widget.getImageItem().image
                # Convert the array to bytes
                array_bytes = np_array.tobytes()
                shape_str = ','.join(map(str, np_array.shape))
                dtype_str = str(np_array.dtype)
                headers = {
                    "X-Shape": shape_str,
                    "X-Dtype": dtype_str
                }
                buffer = io.BytesIO(array_bytes)
                return StreamingResponse(buffer, media_type="application/octet-stream", headers=headers)
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))



    def run(self):
        """
        Method to run the FastAPI server
        """
        uvicorn_config = uvicorn.Config(app=self.app, host=self.host, port=self.port, log_level="info")
        self.server = uvicorn.Server(config=uvicorn_config)
        self.server.run()

    def stop(self):
        """
        Method to stop the FastAPI server
        """
        if self.server:
            self.server.should_exit = True
