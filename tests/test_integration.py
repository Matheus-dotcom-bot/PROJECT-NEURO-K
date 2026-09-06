import socket
import subprocess
import sys
import time
import unittest
from pathlib import Path

import numpy as np
import zmq

from worker import DEFAULT_MAX_MEMORY_BYTES, start_worker


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
        a = np.arange(16, dtype=np.float64).reshape(4, 4)
        b = np.eye(4, dtype=np.float64)
        socket_ = None
        context = zmq.Context()

        try:
            deadline = time.time() + 3
            while time.time() < deadline:
                candidate = context.socket(zmq.REQ)
                candidate.setsockopt(zmq.RCVTIMEO, 250)
                candidate.setsockopt(zmq.SNDTIMEO, 250)
                candidate.setsockopt(zmq.LINGER, 0)
                candidate.connect(f"tcp://127.0.0.1:{port}")
                try:
                    candidate.send_json({"op": "matmul", "n": 4, "dtype": "float64"})
                    ready = candidate.recv_json()
                    socket_ = candidate
                    break
                except zmq.Again:
                    candidate.close(0)
                    time.sleep(0.05)

            if socket_ is None:
                self.fail("worker did not become ready")

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
            if socket_ is not None:
                socket_.close(0)
            context.term()
            process.terminate()
            process.wait(timeout=3)

    def test_worker_rejects_oversized_working_set(self):
        port = free_port()
        process = subprocess.Popen(
            [
                sys.executable,
                str(ROOT / "worker.py"),
                "--host", "127.0.0.1",
                "--port", str(port),
                "--max-memory-mb", "1",
            ],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        context = zmq.Context()
        socket_ = context.socket(zmq.REQ)
        socket_.setsockopt(zmq.RCVTIMEO, 1000)
        socket_.setsockopt(zmq.SNDTIMEO, 1000)
        socket_.setsockopt(zmq.LINGER, 0)
        socket_.connect(f"tcp://127.0.0.1:{port}")

        try:
            deadline = time.time() + 3
            while time.time() < deadline:
                try:
                    socket_.send_json({"op": "matmul", "n": 1024, "dtype": "float64"})
                    response = socket_.recv_json()
                    break
                except zmq.Again:
                    time.sleep(0.05)
            else:
                self.fail("worker did not respond")

            self.assertFalse(response["ok"])
            self.assertEqual(response["error"], "matrix exceeds worker memory limit")
        finally:
            socket_.close(0)
            context.term()
            process.terminate()
            process.wait(timeout=3)


class TestWorkerValidation(unittest.TestCase):
    def test_default_memory_limit_is_reasonable_for_poC(self):
        self.assertEqual(DEFAULT_MAX_MEMORY_BYTES, 512 * 1024 * 1024)

    def test_start_worker_rejects_invalid_configuration(self):
        with self.assertRaises(ValueError):
            start_worker(port=0)
        with self.assertRaises(ValueError):
            start_worker(max_memory_bytes=0)
        with self.assertRaises(ValueError):
            start_worker(max_n=0)


if __name__ == "__main__":
    unittest.main()
