PROJECT NEURO-K

Systems Engineering Experiment: Hybrid Local Memory Control + Cloud Offloading Strategy

Overview

PROJECT NEURO-K is an experimental systems engineering project that explores:

Local memory pressure handling using a C extension

Python-based orchestration layer

Optional cloud offloading strategy (conceptual layer)

Controlled memory cleanup and telemetry collection

The goal is to investigate how low-level memory operations can integrate with high-level orchestration in hybrid architectures.

This is not a production system.
It is a research-oriented engineering experiment.

Architecture
/core
    neuro_k_core.c        → Low-level memory management extension (C11)
    setup.py              → C extension build script

/nicho
    main_engine.py        → Python orchestration engine

/results
    benchmark.csv         → Benchmark results (generated)

/requirements.txt
/README.md

Core Concept

Detect memory pressure

Trigger controlled cleanup (optional root-level cache drop)

Collect telemetry

Enable decision logic for offloading computation

Installation
Requirements

Linux (recommended)

Python 3.9+

GCC

NumPy

Step 1 — Create Virtual Environment
python -m venv venv
source venv/bin/activate

Step 2 — Install Dependencies
pip install -r requirements.txt

requirements.txt
numpy

Step 3 — Build C Extension
cd core
python setup.py build_ext --inplace
cd ..

C Extension (core/neuro_k_core.c)
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

static PyObject* nicho_clean(PyObject* self, PyObject* args) {
    if (geteuid() != 0) {
        Py_RETURN_FALSE;
    }

    FILE* f = fopen("/proc/sys/vm/drop_caches", "w");
    if (!f) {
        Py_RETURN_FALSE;
    }

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
import os
import time
import numpy as np
import neuro_k_core
import csv


def simulate_memory_load(size_mb=500):
    print(f"[INFO] Allocating {size_mb}MB of memory...")
    arr = np.ones((size_mb * 250_000,), dtype=np.float32)
    time.sleep(2)
    return arr


def collect_telemetry():
    print("[INFO] Collecting memory telemetry...")
    with open("/proc/meminfo") as f:
        lines = f.readlines()

    meminfo = {}
    for line in lines:
        key, value = line.split(":")
        meminfo[key.strip()] = value.strip()

    return meminfo


def run_benchmark():
    results = []

    arr = simulate_memory_load(300)
    mem_before = collect_telemetry()

    cleaned = neuro_k_core.nicho_clean()
    mem_after = collect_telemetry()

    results.append({
        "clean_executed": cleaned,
        "mem_available_before": mem_before.get("MemAvailable", "N/A"),
        "mem_available_after": mem_after.get("MemAvailable", "N/A"),
    })

    del arr

    os.makedirs("results", exist_ok=True)
    with open("results/benchmark.csv", "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    print("[INFO] Benchmark saved to results/benchmark.csv")


if __name__ == "__main__":
    run_benchmark()

Running the Project
python nicho/main_engine.py


If executed as root, OS cache cleanup will run.
If not, the system will continue safely without dropping caches.

Benchmark Output

Results are saved in:

/results/benchmark.csv


Example output:

clean_executed	mem_available_before	mem_available_after
False	1850000 kB	1862000 kB
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
