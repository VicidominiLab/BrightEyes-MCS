#!/usr/bin/env python3
"""
TCP emulator for Pi Imaging pSPAD scanning-binary measurements.

Listens on TCP port 9997, accepts a CS command, and streams back detector
image planes followed by the 4-byte sentinel b"DONE".

Protocol recap:
  -> client connects
  <- server sends greeting string
  -> client sends: CS,<dwell_us>,<frames>,<pix_x>,<pix_y>,<ext_frame>\n
  <- server streams: frames * 23 * pix_x * pix_y bytes
  <- server appends: b"DONE"
"""

import argparse
import os
import socket
import threading
import time

import numpy as np


def debug_enabled(default=False):
    value = os.environ.get("PI23_DEBUG", os.environ.get("DEBUG"))
    if value is None:
        return bool(default)
    return value.strip().lower() in ("1", "true", "yes", "on", "debug")


def make_scene(pix_x: int, pix_y: int, n_planes: int = 23, seed: int | None = None) -> np.ndarray:
    """Return a uint8 array of shape (n_planes, pix_y, pix_x)."""
    rng = np.random.default_rng(seed)

    y = np.linspace(-1, 1, pix_y)
    x = np.linspace(-1, 1, pix_x)
    xx, yy = np.meshgrid(x, y)

    mean_rate = (
        8.0 * np.exp(-((xx - 0.0) ** 2 + (yy - 0.0) ** 2) / (2 * 0.18**2))
        + 3.5 * np.exp(-((xx + 0.4) ** 2 + (yy - 0.3) ** 2) / (2 * 0.10**2))
        + 2.0 * np.exp(-((xx - 0.5) ** 2 + (yy + 0.5) ** 2) / (2 * 0.08**2))
        + 0.3
    )
    mean_rate = np.clip(mean_rate, 0, 255.0 / n_planes)
    return rng.poisson(
        lam=mean_rate[np.newaxis, :, :],
        size=(n_planes, pix_y, pix_x),
    ).astype(np.uint8)


def parse_cs(line: str):
    """Parse a CS command line."""
    parts = line.strip().split(",")
    if len(parts) != 6 or parts[0].upper() != "CS":
        raise ValueError(f"Unknown or malformed command: {line!r}")
    _, dwell, nf, px, py, ext = parts
    return float(dwell), int(nf), int(px), int(py), int(ext)


def handle_client(
    conn: socket.socket,
    addr,
    chunk_size: int,
    simulated_delay: bool,
    verbose: bool,
):
    peer = f"{addr[0]}:{addr[1]}"
    print(f"[+] Connection from {peer}")

    try:
        greeting = (
            "BrightEyes-MCS PI23 Emulator v1.0\r\n"
            "Ready. Send CS,<dwell_us>,<frames>,<pix_x>,<pix_y>,<ext_frame>\r\n"
        )
        conn.sendall(greeting.encode("utf-8"))

        buf = b""
        while b"\n" not in buf:
            chunk = conn.recv(256)
            if not chunk:
                print(f"[-] {peer} disconnected before sending command")
                return
            buf += chunk

        cmd_line = buf.split(b"\n")[0].decode("utf-8")
        if verbose:
            print(f"[>] {peer} command: {cmd_line!r}")

        try:
            dwell_us, nr_frames, pix_x, pix_y, ext_frame = parse_cs(cmd_line)
        except ValueError as exc:
            conn.sendall(f"ERROR: {exc}\n".encode("utf-8"))
            return

        n_pixels = pix_x * pix_y
        n_chan = 23
        scan_frames = max(1, nr_frames)

        print(
            f"[*] {peer} -> dwell={dwell_us} us  frames={scan_frames}  "
            f"size={pix_x}x{pix_y}  ext={ext_frame}"
        )

        if simulated_delay:
            acq_time = dwell_us * 1e-6 * n_pixels * scan_frames / 100.0
            if acq_time > 0.05:
                print(f"[*] Simulating ~{acq_time:.2f}s acquisition ...")
                time.sleep(acq_time)

        frames = np.stack(
            [make_scene(pix_x, pix_y, n_chan, seed=frame_idx) for frame_idx in range(scan_frames)],
            axis=0,
        )
        payload = frames.tobytes(order="C")
        expected = scan_frames * n_chan * n_pixels
        assert len(payload) == expected, f"{len(payload)} != {expected}"

        t0 = time.perf_counter()
        sent = 0
        while sent < len(payload):
            end = min(sent + chunk_size, len(payload))
            conn.sendall(payload[sent:end])
            sent = end

        conn.sendall(b"DONE")
        elapsed = time.perf_counter() - t0
        mb = len(payload) / 1e6
        rate = mb / elapsed if elapsed > 0 else 0.0
        print(f"[*] {peer} <- {mb:.2f} MB in {elapsed:.3f}s  ({rate:.1f} MB/s)  +DONE")

    except (BrokenPipeError, ConnectionResetError):
        print(f"[-] {peer} connection dropped")
    except Exception as exc:
        print(f"[!] {peer} error: {exc}")
        try:
            conn.sendall(b"ERROR\n")
        except Exception:
            pass
    finally:
        conn.close()
        print(f"[-] {peer} closed")


def run_server(
    host: str = "127.0.0.1",
    port: int = 9997,
    chunk_size: int = 32768,
    simulated_delay: bool = False,
    verbose: bool = False,
):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen(5)
    print(f"[*] Emulator listening on {host}:{port}  (chunk={chunk_size}B)")
    print("[*] Press Ctrl-C to stop\n")

    try:
        while True:
            conn, addr = srv.accept()
            thread = threading.Thread(
                target=handle_client,
                args=(conn, addr, chunk_size, simulated_delay, verbose),
                daemon=True,
            )
            thread.start()
    except KeyboardInterrupt:
        print("\n[*] Shutting down emulator")
    finally:
        srv.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TCP emulator for PI23 scanning binary data")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9997)
    parser.add_argument("--chunk", type=int, default=32768)
    parser.add_argument("--delay", action="store_true")
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=debug_enabled(False),
        help="Print raw command strings. Also enabled by DEBUG=1 or PI23_DEBUG=1",
    )
    args = parser.parse_args()

    run_server(
        host=args.host,
        port=args.port,
        chunk_size=args.chunk,
        simulated_delay=args.delay,
        verbose=args.verbose,
    )
