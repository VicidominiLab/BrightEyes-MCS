from decimal import Decimal

import h5py
import threading
import numpy as np
from PySide6.QtCore import QByteArray, QBuffer, QIODevice

from ..libs.print_dec import print_dec

try:
    import pyqtgraph as pg
except:
    print("pyqtgraph not found")


class H5Manager:
    def __init__(self, filenameh5, new_file=True, shm_number_of_threads_h5=None):
        if shm_number_of_threads_h5 is not None:
            self.shm_number_of_threads_h5 = shm_number_of_threads_h5
        print(shm_number_of_threads_h5)

        if new_file:
            self.h5file = h5py.File(filenameh5, "w")
            print_dec("w")
        elif not new_file:
            self.h5file = h5py.File(filenameh5, "r+")
            print_dec("r+")

        self.h5dset = {}
        self.threads = []
        self.threads_called = 0
        self.threads_ended = 0

        self.lock = threading.Lock()
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
        # self._add_to_dataset(dataset_name, buffer_for_save, current_rep, current_z)
        #print_dec(dataset_name, buffer_for_save.shape, current_rep, current_z, "get_number_of_threads", self.get_number_of_threads())
        self.threads.append(
            threading.Thread(
                target=lambda: self._add_to_dataset(
                    dataset_name, buffer_for_save, current_rep, current_z
                )
            )
        )
        self.threads[-1].start()
        self.threads_called = self.threads_called + 1
        self.update_threads_number()

    def _add_to_dataset(self, dataset_name, buffer_for_save, current_rep, current_z):
        self.lock.acquire()
        dims = list(self.h5dset[dataset_name].shape)
        dims[0] = current_rep + 1
        # print_dec("_add_to_dataset", dataset_name, dims)
        self.h5dset[dataset_name].resize(dims)
        # print_dec(self.h5dset[dataset_name].shape)
        self.h5dset[dataset_name][current_rep, current_z, :] = buffer_for_save
        # print_dec()
        # print_dec(self.h5dset[dataset_name].shape, buffer_for_save.shape)
        self.threads_ended = self.threads_ended + 1
        self.lock.release()

    def close(self):
        for i in self.threads:
            # print_dec("thread.join()", i)
            i.join()
            self.update_threads_number()
        print_dec("h5 closed")
        self.h5file.close()

    def get_number_of_threads(self):
        return self.threads_called - self.threads_ended
        # l = len(self.threads)
        # print_dec("get_number_of_threads", l)

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
