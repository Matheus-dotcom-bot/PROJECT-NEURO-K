import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from orchestrator import Calibration, NeuroKOrchestrator, append_result


class TestOrchestratorMath(unittest.TestCase):
    def test_matrix_memory_estimates(self):
        dtype = np.dtype(np.float64)
        self.assertEqual(NeuroKOrchestrator.matrix_bytes(10, dtype), 800)
        self.assertEqual(NeuroKOrchestrator.required_bytes(10, dtype), 2400)

    def test_predict_requires_calibration(self):
        orchestrator = NeuroKOrchestrator("tcp://127.0.0.1:1")
        try:
            with self.assertRaises(RuntimeError):
                orchestrator.predict(128)
        finally:
            orchestrator.close()

    def test_predict_rejects_non_positive_size(self):
        orchestrator = NeuroKOrchestrator("tcp://127.0.0.1:1")
        orchestrator.calibration = Calibration(0.1, 0.1, 1e9, 0.001)
        try:
            with self.assertRaises(ValueError):
                orchestrator.predict(0)
            with self.assertRaises(ValueError):
                orchestrator.predict(-1)
        finally:
            orchestrator.close()

    def test_predict_offload_when_remote_is_faster(self):
        orchestrator = NeuroKOrchestrator("tcp://127.0.0.1:1")
        orchestrator.calibration = Calibration(
            local_seconds=0.10,
            worker_compute_seconds=0.01,
            bandwidth_bytes_per_second=1e12,
            rtt_seconds=0.0001,
        )
        try:
            with patch.object(orchestrator, "available_memory", return_value=10**12):
                decision, reason = orchestrator.predict(128)
            self.assertTrue(decision)
            self.assertEqual(reason, "PREDICTED_FASTER")
        finally:
            orchestrator.close()

    def test_predict_local_when_communication_dominates(self):
        orchestrator = NeuroKOrchestrator("tcp://127.0.0.1:1")
        orchestrator.calibration = Calibration(
            local_seconds=0.01,
            worker_compute_seconds=0.009,
            bandwidth_bytes_per_second=1e3,
            rtt_seconds=0.1,
        )
        try:
            with patch.object(orchestrator, "available_memory", return_value=10**12):
                decision, reason = orchestrator.predict(128)
            self.assertFalse(decision)
            self.assertEqual(reason, "PREDICTED_LOCAL_FASTER")
        finally:
            orchestrator.close()

    def test_ram_pressure_forces_offload(self):
        orchestrator = NeuroKOrchestrator("tcp://127.0.0.1:1")
        orchestrator.calibration = Calibration(0.1, 0.1, 1e9, 0.001)
        try:
            with patch.object(orchestrator, "available_memory", return_value=1):
                decision, reason = orchestrator.predict(128)
            self.assertTrue(decision)
            self.assertEqual(reason, "RAM_PRESSURE")
        finally:
            orchestrator.close()


class TestCsvPersistence(unittest.TestCase):
    def test_append_result_writes_measured_schema(self):
        result = {
            "n": 64,
            "dtype": "float64",
            "decision": "OFFLOAD",
            "reason": "PREDICTED_FASTER",
            "t_local": 0.01,
            "t_offload_total": 0.02,
            "gain_percent": -100.0,
            "metrics": {
                "t_serialization": 0.0002,
                "t_send_a": 0.001,
                "t_send_b": 0.001,
                "t_receive_c": 0.001,
                "t_remote_deserialize": 0.0001,
                "t_remote_compute": 0.005,
                "t_remote_serialize": 0.0001,
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "results.csv"
            append_result(path, result)
            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["status"], "MEASURED")
            self.assertEqual(rows[0]["n"], "64")
            self.assertEqual(rows[0]["decision"], "OFFLOAD")
            self.assertEqual(rows[0]["t_serialization_s"], "0.0002")


if __name__ == "__main__":
    unittest.main()
