import socket
import subprocess
import sys
import time
import unittest
from pathlib import Path

import numpy as np
import zmq


ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class TestWorkerIntegration(unittest.TestCase):
    def test_remote_matmul_protocol_and_result(self):
        port = free_port()
        process = subprocess.Popen(
            [sys.executable, str(ROOT / "worker.py"), "--host", "127.0.0.1", "--port", str(port)],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        context = zmq.Context()
        socket_ = context.socket(zmq.REQ)
        socket_.setsockopt(zmq.RCVTIMEO, 3000)
        socket_.setsockopt(zmq.SNDTIMEO, 3000)
        socket_.connect(f"tcp://127.0.0.1:{port}")

        try:
            deadline = time.time() + 3
            while True:
                try:
                    a = np.arange(16, dtype=np.float64).reshape(4, 4)
                    b = np.eye(4, dtype=np.float64)
                    socket_.send_json({"op": "matmul", "n": 4, "dtype": "float64"})
                    ready = socket_.recv_json()
                    break
                except zmq.Again:
                    if time.time() >= deadline:
                        self.fail("worker did not become ready")
                    time.sleep(0.05)

            self.assertTrue(ready["ok"])
            socket_.send(a.tobytes())
            self.assertTrue(socket_.recv_json()["ok"])
            socket_.send(b.tobytes())
            meta = socket_.recv_json()
            self.assertTrue(meta["ok"])
            self.assertGreater(meta["t_compute"], 0)

            socket_.send_string("SEND_RESULT")
            result = socket_.recv()
            c = np.frombuffer(result, dtype=np.float64).reshape(4, 4)
            np.testing.assert_allclose(c, a @ b)
        finally:
            socket_.close(0)
            context.term()
            process.terminate()
            process.wait(timeout=3)


if __name__ == "__main__":
    unittest.main()
