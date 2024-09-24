
import uvicorn
import threading
from fastapi import FastAPI, HTTPException, UploadFile, File, Request

from fastapi.responses import StreamingResponse, Response
import io
from pyqtgraph import exporters
import json
import numpy as np

from PySide2.QtCore import (
    Signal,
    QIODevice,
    QBuffer,
    QObject)


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return json.JSONEncoder.default(self, obj)


class FastAPIServerThread(threading.Thread):
    def __init__(self, main_window, host="127.0.0.1", port=8000):
        super().__init__()
        self.host = host
        self.port = port
        self.app = FastAPI()
        self.main_window = main_window
        self.server = None

        class MySignal(QObject):
            start = Signal()
            stop = Signal()
            preview = Signal()

        self.signal = MySignal()
        self.signal.start.connect(self.main_window.startButtonClicked)
        self.signal.stop.connect(self.main_window.stopButtonClicked)
        self.signal.preview.connect(self.main_window.previewButtonClicked)

        @self.app.get("/")
        async def read_root():
            return {"message": "Hello, World!"}

        @self.app.get("/gui/")
        async def read_item():
            mydict = self.main_window.getGUI_data()

            return json.dumps(mydict, cls=NumpyEncoder)

        @self.app.get("/gui/{item}")
        async def read_item(item: str = None):
            mydict = self.main_window.getGUI_data()

            if item == 'all':
                return json.dumps(mydict, cls=NumpyEncoder)
            else:
                return json.dumps(mydict[item], cls=NumpyEncoder)

        @self.app.get("/cmd/{item}")
        async def read_item(item: str = None):
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
        uvicorn_config = uvicorn.Config(app=self.app, host=self.host, port=self.port, log_level="info")
        self.server = uvicorn.Server(config=uvicorn_config)
        self.server.run()

    def stop(self):
        if self.server:
            self.server.should_exit = True