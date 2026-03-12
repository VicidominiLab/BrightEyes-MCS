from decimal import Decimal

import h5py
import multiprocessing as mp
import numpy as np
from PySide6.QtCore import QByteArray, QBuffer, QIODevice

from ..libs.print_dec import print_dec



try:
    import pyqtgraph as pg
except:
    print("pyqtgraph not found")


class H5Manager:
    def __init__(self, filenameh5, new_file=True, shm_number_of_threads_h5=None):
        self.shm_number_of_threads_h5 = shm_number_of_threads_h5
        print(shm_number_of_threads_h5)

        if new_file:
            self.h5file = h5py.File(filenameh5, "w")
            print_dec("w")
        elif not new_file:
            self.h5file = h5py.File(filenameh5, "r+")
            print_dec("r+")

        self.h5dset = {}
        print_dec("Filename:", filenameh5)

    def init_dataset(self, dataset_name, shape, timebinsPerPixel, channels, dtype):
        print_dec("init_dataset")
        self.h5dset[dataset_name] = self.h5file.create_dataset(
            dataset_name,
            shape=(
                1,
                shape[2],
                shape[1],
                shape[0],
                timebinsPerPixel,
                channels,
            ),
            maxshape=(
                None,
                shape[2],
                shape[1],
                shape[0],
                timebinsPerPixel,
                channels,
            ),
            dtype=dtype,
        )
        print_dec(dataset_name, self.h5dset[dataset_name].shape)

    def add_to_dataset(self, dataset_name, buffer_for_save, current_rep, current_z):
        # Writes are already asynchronous at process level (H5ManagerProcess).
        # Avoid per-frame Python thread creation overhead here.
        self._add_to_dataset(dataset_name, buffer_for_save, current_rep, current_z)
        self.update_threads_number()

    def _add_to_dataset(self, dataset_name, buffer_for_save, current_rep, current_z):
        dims = list(self.h5dset[dataset_name].shape)
        dims[0] = current_rep + 1
        # print_dec("_add_to_dataset", dataset_name, dims)
        self.h5dset[dataset_name].resize(dims)
        # print_dec(self.h5dset[dataset_name].shape)
        self.h5dset[dataset_name][current_rep, current_z, :] = buffer_for_save
        # print_dec()
        # print_dec(self.h5dset[dataset_name].shape, buffer_for_save.shape)

    def close(self):
        self.update_threads_number()
        print_dec("h5 closed")
        self.h5file.close()

    def get_number_of_threads(self):
        # Thread pool removed: this manager executes writes synchronously
        # inside the dedicated H5 process.
        return 0

    def update_threads_number(self):
        if self.shm_number_of_threads_h5 is not None:
            self.shm_number_of_threads_h5.value = self.get_number_of_threads()

    def metadata_add_dict(self, group_name, mydict={}):
        print_dec("metadata_add_dict")
        if not (group_name in self.h5file.keys()):
            group_conf = self.h5file.create_group(group_name)
        else:
            group_conf = self.h5file[group_name]

        meta_data_h5_debug=""
        for i in mydict.keys():
            value_i = mydict[i]
            if value_i is not None:
                meta_data_h5_debug+="%s (%s): %s     "  %(i, type(value_i), value_i)
                if isinstance(value_i, list):
                    fff = np.asarray(mydict[i], dtype=np.float64)
                    print_dec(fff, type(fff))
                    group_conf.attrs[i] = fff
                elif isinstance(value_i, Decimal):
                    group_conf.attrs[i] = float(mydict[i])
                elif isinstance(value_i, dict):
                    group_conf.attrs[i] = str(mydict[i])
                else:
                    group_conf.attrs[i] = mydict[i]
        print_dec("Metadata h5 added at %s: " % group_name, meta_data_h5_debug )
    def metadata_add_initial(self, comment):
        print_dec("metadata_add_initial")
        self.h5file.attrs["default"] = "data"
        self.h5file.attrs["data_format_version"] = "0.0.1"
        self.h5file.attrs["comment"] = comment

    def metadata_add_thumbnail(self, image):
        print_dec("metadata_add_thumbnail")
        try:
            # get the current projection save in JPEG inside the HDF5
            exporter = pg.exporters.ImageExporter(image)
            exporter.parameters()["width"] = 200
            image_bitmap = exporter.export(toBytes=True)

            file_ba = QByteArray()
            file_buff = QBuffer(file_ba)
            file_buff.open(QIODevice.WriteOnly)
            image_bitmap.save(file_buff, "JPEG")
            binary_data = bytes(file_buff.data())

            dt = h5py.special_dtype(vlen=np.dtype("uint8"))
            thumbnail = self.h5file.create_dataset("thumbnail", (1,), dtype=dt)
            thumbnail[0] = np.fromstring(binary_data, dtype="uint8")

        except Exception as ex:
            print_dec("Thumbnail creation ERROR")
            print_dec(ex)

    def print_keys(self):
        print(self.h5file.keys())


class H5ManagerProcess(mp.Process):
    def __init__(self, command_queue, response_queue, shm_number_of_threads_h5=None):
        super().__init__()
        self.command_queue = command_queue
        self.response_queue = response_queue
        self.shm_number_of_threads_h5 = shm_number_of_threads_h5

    def _send_response(self, request_id, ok=True, result=None, error=None):
        self.response_queue.put(
            {
                "request_id": request_id,
                "ok": ok,
                "result": result,
                "error": error,
            }
        )

    def _update_pending_counter(self, in_flight=0):
        if self.shm_number_of_threads_h5 is None:
            return
        pending = in_flight
        try:
            pending += int(self.command_queue.qsize())
        except Exception:
            # qsize() can be unavailable on some platforms.
            pass
        self.shm_number_of_threads_h5.value = pending

    def run(self):
        h5mgr = None
        keep_running = True

        while keep_running:
            self._update_pending_counter(in_flight=0)
            msg = self.command_queue.get()
            cmd = msg.get("cmd")
            wait = msg.get("wait", False)
            request_id = msg.get("request_id")
            kwargs = msg.get("kwargs", {})

            try:
                if cmd == "init":
                    h5mgr = H5Manager(
                        kwargs["filenameh5"],
                        new_file=kwargs.get("new_file", True),
                        shm_number_of_threads_h5=self.shm_number_of_threads_h5,
                    )
                    result = True

                elif cmd == "init_dataset":
                    h5mgr.init_dataset(
                        kwargs["dataset_name"],
                        kwargs["shape"],
                        kwargs["timebinsPerPixel"],
                        kwargs["channels"],
                        kwargs["dtype"],
                    )
                    result = True

                elif cmd == "add_to_dataset":
                    self._update_pending_counter(in_flight=1)
                    h5mgr.add_to_dataset(
                        kwargs["dataset_name"],
                        kwargs["buffer_for_save"],
                        kwargs["current_rep"],
                        kwargs["current_z"],
                    )
                    result = True

                elif cmd == "get_number_of_threads":
                    result = h5mgr.get_number_of_threads()

                elif cmd == "close":
                    if h5mgr is not None:
                        h5mgr.close()
                        h5mgr = None
                    result = True

                elif cmd == "shutdown":
                    if h5mgr is not None:
                        h5mgr.close()
                        h5mgr = None
                    keep_running = False
                    result = True

                else:
                    raise RuntimeError("Unknown H5ManagerProcess command: %s" % cmd)

                if wait:
                    self._send_response(request_id, ok=True, result=result)
                self._update_pending_counter(in_flight=0)

            except Exception as ex:
                print_dec("H5ManagerProcess error", repr(ex))
                if wait:
                    self._send_response(request_id, ok=False, error=repr(ex))
                self._update_pending_counter(in_flight=0)

        if h5mgr is not None:
            try:
                h5mgr.close()
            except Exception as ex:
                print_dec("H5ManagerProcess close error", repr(ex))


class H5ManagerProcessClient:
    def __init__(self, command_queue, response_queue, timeout=120):
        self.command_queue = command_queue
        self.response_queue = response_queue
        self.timeout = timeout
        self.request_id = 0

    def _next_request_id(self):
        self.request_id += 1
        return self.request_id

    def _send(self, cmd, wait=False, timeout=None, **kwargs):
        msg = {"cmd": cmd, "kwargs": kwargs, "wait": wait}
        req_id = None
        if wait:
            req_id = self._next_request_id()
            msg["request_id"] = req_id
            self.command_queue.put(msg)
        else:
            # Non-blocking enqueue for fire-and-forget writes.
            self.command_queue.put_nowait(msg)

        if not wait:
            return None

        timeout_s = self.timeout if timeout is None else timeout
        response = self.response_queue.get(timeout=timeout_s)
        if response.get("request_id") != req_id:
            raise RuntimeError("Unexpected H5ManagerProcess response id")
        if not response.get("ok", False):
            raise RuntimeError(response.get("error", "Unknown H5ManagerProcess error"))
        return response.get("result")

    def init(self, filenameh5, new_file=True):
        self._send("init", wait=True, filenameh5=filenameh5, new_file=new_file)

    def init_dataset(self, dataset_name, shape, timebinsPerPixel, channels, dtype):
        self._send(
            "init_dataset",
            wait=True,
            dataset_name=dataset_name,
            shape=shape,
            timebinsPerPixel=timebinsPerPixel,
            channels=channels,
            dtype=dtype,
        )

    def add_to_dataset(self, dataset_name, buffer_for_save, current_rep, current_z):
        self._send(
            "add_to_dataset",
            wait=False,
            dataset_name=dataset_name,
            buffer_for_save=buffer_for_save,
            current_rep=current_rep,
            current_z=current_z,
        )

    def get_number_of_threads(self):
        return self._send("get_number_of_threads", wait=True)

    def close(self):
        self._send("close", wait=True)

    def shutdown(self):
        self._send("shutdown", wait=True)
