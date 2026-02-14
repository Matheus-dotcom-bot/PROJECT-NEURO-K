# PROJECT NEURO-K

**Systems Engineering Experiment: Hybrid Local Memory Control + Cloud Offloading Strategy**


---

## Overview

PROJECT NEURO-K is an experimental systems engineering project that explores:

- Local memory pressure handling using a **C extension**
- A **Python orchestration layer**
- Optional **cloud offloading strategy** (conceptual layer)
- Controlled cleanup and **telemetry collection**

**Goal:** investigate how low-level memory operations can integrate with high-level orchestration in hybrid architectures.

> This is **not** a production system. It is a **research-oriented engineering experiment**.

---

## Architecture

/core
neuro_k_core.c → Low-level memory management extension (C11)
setup.py → C extension build script

/nicho
main_engine.py → Python orchestration engine (benchmark + graph)

/results
benchmark.csv → Benchmark results (generated)
benchmark.png → Benchmark graph (generated)

requirements.txt
README.md


---

## Core Concept

1. Detect memory pressure (simulated)
2. Trigger controlled cleanup (**optional root-level cache drop**)
3. Collect telemetry
4. Enable decision logic for offloading computation (future work)

---

## Installation

### Requirements

- Linux (recommended)
- Python 3.9+
- GCC / build-essential
- NumPy
- Matplotlib (for auto graph)

---

### Step 1 — Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate

Step 2 — Install Dependencies

pip install -r requirements.txt

requirements.txt:

numpy
matplotlib

Step 3 — Build C Extension

cd core
python setup.py build_ext --inplace
cd ..

Running the Project

python nicho/main_engine.py

    If executed as root, OS cache cleanup will run.

    If not root, the system will continue safely without dropping caches.

Outputs:

    results/benchmark.csv

    results/benchmark.png

Benchmark Output

Results are saved in:

results/benchmark.csv
results/benchmark.png

CSV example:
clean_executed	mem_available_before_kb	mem_available_after_kb
False	1850000	1862000
C Extension (core/neuro_k_core.c)

    ⚠️ Note: drop_caches is Linux-specific and requires root.
    The function returns False when not executed with privileges.

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdio.h>
#include <unistd.h>

static PyObject* nicho_clean(PyObject* self, PyObject* args) {
    // Safety: do nothing if not root
    if (geteuid() != 0) {
        Py_RETURN_FALSE;
    }

    FILE* f = fopen("/proc/sys/vm/drop_caches", "w");
    if (!f) {
        Py_RETURN_FALSE;
    }

    // 3 = drop pagecache + dentries + inodes
    fprintf(f, "3\n");
    fclose(f);

    Py_RETURN_TRUE;
}

static PyMethodDef NeuroKMethods[] = {
    {"nicho_clean", nicho_clean, METH_NOARGS, "Safely drop OS cache (requires root)."},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef neurokmodule = {
    PyModuleDef_HEAD_INIT,
    "neuro_k_core",
    NULL,
    -1,
    NeuroKMethods
};

PyMODINIT_FUNC PyInit_neuro_k_core(void) {
    return PyModule_Create(&neurokmodule);
}

Build Script (core/setup.py)

from setuptools import setup, Extension

module = Extension(
    "neuro_k_core",
    sources=["neuro_k_core.c"],
)

setup(
    name="neuro_k_core",
    version="0.1",
    description="Low-level memory control extension",
    ext_modules=[module],
)

Python Orchestration Engine (nicho/main_engine.py)

This file:

    simulates memory load

    collects /proc/meminfo telemetry

    attempts nicho_clean() (safe non-root behavior)

    writes benchmark.csv

    generates benchmark.png

import os
import time
import csv
import numpy as np
import matplotlib.pyplot as plt
import neuro_k_core


def simulate_memory_load(size_mb: int = 300) -> np.ndarray:
    # float32 ~ 4 bytes; allocation size is approximate
    print(f"[INFO] Allocating ~{size_mb}MB of memory...")
    arr = np.ones((size_mb * 250_000,), dtype=np.float32)
    time.sleep(1.5)
    return arr


def collect_telemetry() -> dict:
    with open("/proc/meminfo", "r", encoding="utf-8") as f:
        lines = f.readlines()

    meminfo = {}
    for line in lines:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meminfo[key.strip()] = value.strip()

    return meminfo


def parse_kb(value: str) -> int:
    # Example: "1850000 kB"
    try:
        return int(value.split()[0])
    except Exception:
        return 0


def save_csv(result: dict) -> None:
    os.makedirs("results", exist_ok=True)
    path = "results/benchmark.csv"

    with open(path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=result.keys())
        writer.writeheader()
        writer.writerow(result)

    print(f"[INFO] Benchmark saved to {path}")


def generate_graph(before_kb: int, after_kb: int) -> None:
    os.makedirs("results", exist_ok=True)
    path = "results/benchmark.png"

    labels = ["Before", "After"]
    values = [before_kb, after_kb]

    plt.figure()
    plt.bar(labels, values)
    plt.xlabel("Stage")
    plt.ylabel("MemAvailable (kB)")
    plt.title("NEURO-K Memory Benchmark")
    plt.savefig(path)
    plt.close()

    print(f"[INFO] Graph saved to {path}")


def run_benchmark() -> None:
    arr = simulate_memory_load(300)

    mem_before = collect_telemetry()
    cleaned = bool(neuro_k_core.nicho_clean())
    mem_after = collect_telemetry()

    before_kb = parse_kb(mem_before.get("MemAvailable", "0 kB"))
    after_kb = parse_kb(mem_after.get("MemAvailable", "0 kB"))

    result = {
        "clean_executed": cleaned,
        "mem_available_before_kb": before_kb,
        "mem_available_after_kb": after_kb,
    }

    save_csv(result)
    generate_graph(before_kb, after_kb)

    # free memory
    del arr
    print("[INFO] Benchmark completed.")


if __name__ == "__main__":
    run_benchmark()

Research Notes

This project explores:

    Memory pressure simulation

    Hybrid low-level/high-level orchestration

    System telemetry integration

    Safe privilege-aware execution

Future iterations may include:

    Cloud-based offload triggers

    Adaptive thresholds

    ML-based decision layer

    Distributed memory monitoring

Status

Experimental
Research Prototype
Actively evolving
Author

Matheus Boeira Pedroso
Engineering Systems | Cloud • Security • Applied AI
