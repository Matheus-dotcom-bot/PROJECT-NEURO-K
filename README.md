PROJECT NEURO-K

Systems Engineering Research Prototype: Hybrid Local Memory Control & High-Level Orchestration

Abstract

PROJECT NEURO-K is an experimental systems engineering prototype investigating cross-layer integration between low-level memory control mechanisms and high-level orchestration logic.

The system explores privilege-aware cache operations, telemetry-based benchmarking, and structured output generation under simulated memory pressure conditions.

This document includes implementation exemplifications for research transparency.

Architectural Overview

NEURO-K follows a three-layer conceptual model:

Low-Level Control Layer (Native interaction)

Orchestration Layer (Execution & telemetry)

Analytical Layer (Benchmark persistence & visualization)

Implementation Exemplifications

The following listings illustrate the experimental architecture design.

Listing 1 — Native Extension (Conceptual Example)
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdio.h>
#include <unistd.h>

static PyObject* nicho_clean(PyObject* self, PyObject* args) {
    // Safety gate: only execute if running as root
    if (geteuid() != 0) {
        Py_RETURN_FALSE;
    }

    FILE* f = fopen("/proc/sys/vm/drop_caches", "w");
    if (!f) {
        Py_RETURN_FALSE;
    }

    // Linux: 3 = pagecache + dentries + inodes
    fprintf(f, "3\n");
    fclose(f);

    Py_RETURN_TRUE;
}

static PyMethodDef Methods[] = {
    {"nicho_clean", nicho_clean, METH_NOARGS, "Drop caches safely (root-only)."},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef Module = {
    PyModuleDef_HEAD_INIT,
    "neuro_k_core",
    NULL,
    -1,
    Methods
};

PyMODINIT_FUNC PyInit_neuro_k_core(void) {
    return PyModule_Create(&Module);
}

Listing 2 — Orchestration Pipeline (Experimental Skeleton)
import time
import numpy as np

try:
    import neuro_k_core
except Exception:
    neuro_k_core = None


def simulate_memory_pressure(size_mb: int = 300) -> np.ndarray:
    arr = np.ones((size_mb * 250_000,), dtype=np.float32)
    time.sleep(1.0)
    return arr


def read_memavailable_kb() -> int:
    with open("/proc/meminfo", "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("MemAvailable:"):
                return int(line.split()[1])
    return 0


def safe_cleanup() -> bool:
    if neuro_k_core is None:
        return False
    try:
        return bool(neuro_k_core.nicho_clean())
    except Exception:
        return False


def run_experiment():
    arr = simulate_memory_pressure(300)

    before = read_memavailable_kb()
    cleaned = safe_cleanup()
    after = read_memavailable_kb()

    del arr

    return {
        "clean_executed": cleaned,
        "before_kb": before,
        "after_kb": after
    }

Listing 3 — Reproducible Output & Visualization
import os
import csv
import matplotlib.pyplot as plt


def save_csv(result: dict, out_dir="results"):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "benchmark.csv")

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=result.keys())
        writer.writeheader()
        writer.writerow(result)

    return path


def save_plot(before_kb: int, after_kb: int, out_dir="results"):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "benchmark.png")

    plt.figure()
    plt.bar(["Before", "After"], [before_kb, after_kb])
    plt.xlabel("Stage")
    plt.ylabel("MemAvailable (kB)")
    plt.title("NEURO-K Memory Benchmark")
    plt.savefig(path)
    plt.close()

    return path

Algorithm 1 — NEURO-K Experimental Workflow
Input: pressure_mb
Output: (before_kb, after_kb, clean_executed)

1. Allocate pressure_mb to simulate memory load
2. Capture MemAvailable (before)
3. If running as root:
       execute controlled cache drop
   Else:
       skip safely
4. Capture MemAvailable (after)
5. Persist results (CSV)
6. Generate benchmark graph

Experimental Characteristics

Linux-based telemetry model

Privilege-aware execution design

Hybrid C/Python integration concept

Reproducible benchmark artifacts

Safe fallback logic under non-root execution

Limitations

Linux-specific implementation

Cache drop is intrusive and experimental

Memory load is synthetic

No container-awareness

Cloud offloading remains conceptual

Future Directions

Adaptive threshold policies

Predictive memory modeling

Container telemetry integration

Distributed system coordination

ML-based pressure classification

Status

Experimental
Research Prototype
Architecture Study

Author

Matheus Boeira Pedroso
Engineering Systems | Cloud • Security • Applied AI
