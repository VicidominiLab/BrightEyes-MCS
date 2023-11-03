from ..libs.print_dec import print_dec
import socket
import time
import threading
import subprocess


class Parameter(object):
    def __init__(self):
        self.last_filename = None
        self.external_app = None
        self.is_ready_flag = None
        self.read_list = None
        self.write_list = None
        self.sock = None
        self.PORT = None

    pass


class TtmRemoteManager(object):
    def __init__(self, ip, port, local_executable):
        print_dec("TtmRemoteManager.__init__")
        self.parameter = Parameter()

        self.parameter.is_ready_flag = False
        self.parameter.external_app = None

        self.parameter.HOST = ip  # Standard loopback interface address (localhost)
        self.parameter.PORT = port  # with 0 the OS give a free non-privileged port (non-privileged ports are > 1023)

        self.local_executable = local_executable

        if self.local_executable == "":  # data receiver (remote)
            self.parameter.external_app = None
        else:  # data receiver (local)
            print_dec(
                "popen",
                (
                    [
                        self.local_executable,
                        "tcp",
                        self.parameter.HOST,
                        str(self.parameter.PORT),
                    ]
                ),
            )
            self.parameter.external_app = subprocess.Popen(
                [
                    self.local_executable,
                    "tcp",
                    self.parameter.HOST,
                    str(self.parameter.PORT),
                ]
            )

        self.connect()

        self.parameter.read_list = []
        self.parameter.write_list = []
        self.parameter.last_filename = ""

        self.parameter.thread_tcp = threading.Thread(target=self.rw_loop, args=())
        self.parameter.thread_tcp.start()

    def connect(self):
        print_dec("Try to connect")
        self.parameter.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.parameter.sock.bind((self.parameter.HOST, self.parameter.PORT))
        (
            self.parameter.HOST,
            self.PORT,
        ) = self.parameter.sock.getsockname()  # get the actual port
        print_dec(self.parameter.HOST, self.parameter.PORT)

    def rw_loop(self):
        print_dec("start thread")
        self.parameter.sock.listen()
        # self.sock.timeout(-1)
        self.parameter.conn, self.parameter.addr = self.parameter.sock.accept()
        print_dec("Connected!")
        self.parameter.conn.settimeout(0.01)

        while self.parameter.conn:
            try:
                data = self.parameter.conn.recv(1024)
            except socket.timeout:
                data = None
            except socket.error as error:
                print_dec("Disconnected")
                self.parameter.is_ready_flag = False
                break

            if data is not None:
                if not (data == b""):
                    print_dec("TCP Recv:", data)
                    self.parse(data)

            if len(self.parameter.write_list) != 0:
                data_to_write = self.parameter.write_list.pop()
                print_dec("TCP Send:", data_to_write)
                try:
                    self.parameter.conn.sendall(str.encode(data_to_write))
                except ConnectionAbortedError:
                    print_dec("Reconnect")
                    self.connect()
                    self.parameter.conn.sendall(str.encode(data_to_write))

    def parse(self, data):
        data = data.decode("utf-8")
        if "READY!" in data:
            self.parameter.is_ready_flag = True
        elif "FILE:" in data:
            print_dec("self.parameter.last_filename = ", data[5:-1])
            self.parameter.last_filename = data[5:-1]
        else:
            self.parameter.read_list.append(data)

    def is_ready(self):
        return self.parameter.is_ready_flag

    def get_remote_filename(self):
        r = self.read()
        if "FILE:" in r:
            self.parameter.last_filename = r
        return self.parameter.last_filename[5:-1]

    def read(self):
        try:
            return self.parameter.read_list.pop()
        except IndexError:
            return None

    def write(self, data):
        return self.parameter.write_list.append(data)

    def start_ttm_recv(self):
        self.parameter.last_filename = ""
        if self.is_ready():
            self.write("START!")

    def stop_ttm_recv(self):
        if self.is_ready():
            self.write("STOP!")
        else:
            print_dec("NOT is_ready()")

    def stop_and_quit_remote(self):
        if self.is_ready():
            self.write("STOPQUIT!")
        else:
            print_dec("NOT is_ready()")

    def set_file_name_remote(self, filename):
        if self.is_ready():
            self.write("SETNAME!%s" % filename)
        else:
            print_dec("NOT is_ready()")

    def set_folder_name_remote(self, folder):
        if self.is_ready():
            self.write("SETFOLDER!%s" % folder)
        else:
            print_dec("NOT is_ready()")

    def close(self):
        print_dec("self.parameter.sock.close()")
        if self.parameter.external_app is not None:
            self.parameter.external_app.kill()
        self.parameter.sock.close()

    def wait_end_of_file_loop(self, handle, timeout=3):
        print_dec("wait_end_of_file_loop")
        t = time.time()
        while (time.time() - t) < timeout:
            if self.parameter.last_filename != "":
                print_dec("wait_end_of_file_thread", self.parameter.last_filename, t)
                handle("TTM: " + self.parameter.last_filename)
                return self.parameter.last_filename
        return None

    def wait_ttm_filename(self, handle):
        self.parameter.thread_wait_end_of_file_thread = threading.Thread(
            target=self.wait_end_of_file_loop,
            args=(
                handle,
                10,
            ),
        )
        self.parameter.thread_wait_end_of_file_thread.start()
