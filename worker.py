"""PROJECT-NEURO-K remote worker.

Binary NumPy buffers are transported through ZeroMQ. No root privileges
or HTTP/JSON payloads are required for matrix data.
"""

from __future__ import annotations

import argparse
import time

import numpy as np
import zmq


def start_worker(host: str = "*", port: int = 5555) -> None:
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.setsockopt(zmq.LINGER, 0)
    socket.bind(f"tcp://{host}:{port}")
    print(f"[NEURO-K] worker listening on tcp://{host}:{port}")

    try:
        while True:
            request = socket.recv_json()
            if request.get("op") != "matmul":
                socket.send_json({"ok": False, "error": "unsupported operation"})
                continue

            n = int(request["n"])
            dtype = np.dtype(request["dtype"])

            if n <= 0 or n > 8192:
                socket.send_json({"ok": False, "error": "invalid matrix size"})
                continue

            # ACK is kept explicit so the benchmark can separate protocol
            # round-trip time from raw payload transfer.
            socket.send_json({"ok": True, "stage": "READY"})

            bytes_a = socket.recv()
            socket.send_json({"ok": True, "stage": "A_RECEIVED"})

            bytes_b = socket.recv()
            socket.send_json({"ok": True, "stage": "B_RECEIVED"})

            expected = n * n * dtype.itemsize
            if len(bytes_a) != expected or len(bytes_b) != expected:
                socket.send_json({"ok": False, "error": "invalid payload size"})
                continue

            t0 = time.perf_counter()
            a = np.frombuffer(bytes_a, dtype=dtype).reshape(n, n)
            b = np.frombuffer(bytes_b, dtype=dtype).reshape(n, n)
            t_deserialize = time.perf_counter() - t0

            t0 = time.perf_counter()
            c = np.matmul(a, b)
            t_compute = time.perf_counter() - t0

            t0 = time.perf_counter()
            bytes_c = np.ascontiguousarray(c).tobytes()
            t_serialize = time.perf_counter() - t0

            socket.send_json(
                {
                    "ok": True,
                    "stage": "RESULT_READY",
                    "t_deserialize": t_deserialize,
                    "t_compute": t_compute,
                    "t_serialize": t_serialize,
                    "result_bytes": len(bytes_c),
                }
            )

            # Client explicitly acknowledges before the binary result.
            ack = socket.recv_string()
            if ack != "SEND_RESULT":
                socket.send(b"")
                continue

            socket.send(bytes_c)
    finally:
        socket.close()
        context.term()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="*")
    parser.add_argument("--port", type=int, default=5555)
    args = parser.parse_args()
    start_worker(args.host, args.port)
