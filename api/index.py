"""HTTP API for the Vercel-hosted PROJECT-NEURO-K service.

This endpoint provides a cloud/serverless execution baseline. It is deliberately
separate from the ZeroMQ worker benchmark because Vercel Functions are ephemeral
and do not provide a persistent TCP worker endpoint.
"""

from __future__ import annotations

from pathlib import Path
import platform
import time

import numpy as np
import psutil
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field


SUPPORTED_DTYPES = {"float32": np.float32, "float64": np.float64}
MAX_N = 2048
DASHBOARD_PATH = Path(__file__).resolve().parent.parent / "dashboard.html"

app = FastAPI(
    title="PROJECT-NEURO-K",
    description="Adaptive computational offloading proof of concept.",
    version="2.6.0",
)


class BenchmarkRequest(BaseModel):
    n: int = Field(gt=0, le=MAX_N)
    dtype: str = Field(default="float64")
    seed: int = Field(default=0, ge=0, le=2**32 - 1)


@app.get("/")
def root():
    return {
        "project": "PROJECT-NEURO-K",
        "status": "online",
        "service": "Vercel API",
        "architecture": "FastAPI serverless baseline",
        "benchmark_endpoint": "/benchmark",
        "dashboard_endpoint": "/dashboard.html",
        "zeromq_worker": "separate persistent process required",
    }


@app.get("/dashboard.html", include_in_schema=False)
@app.get("/dashboard", include_in_schema=False)
def dashboard():
    """Serve the static simulation dashboard through the FastAPI function."""
    if not DASHBOARD_PATH.is_file():
        raise HTTPException(status_code=404, detail="dashboard.html not found")
    return FileResponse(DASHBOARD_PATH, media_type="text/html")


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "neuro-k-api",
        "python": platform.python_version(),
        "numpy": np.__version__,
    }


@app.get("/runtime")
def runtime():
    """Return runtime information for provenance of a cloud baseline."""
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "numpy": np.__version__,
        "cpu_count": psutil.cpu_count(logical=True),
        "available_memory_bytes": int(psutil.virtual_memory().available),
    }


@app.post("/benchmark")
def benchmark(request: BenchmarkRequest):
    """Measure one NumPy matrix multiplication inside the Vercel function.

    This is a cloud execution baseline, not a ZeroMQ network-offload result.
    """
    dtype_name = request.dtype.lower()
    if dtype_name not in SUPPORTED_DTYPES:
        raise HTTPException(status_code=400, detail="dtype must be float32 or float64")

    dtype = np.dtype(SUPPORTED_DTYPES[dtype_name])
    rng = np.random.default_rng(request.seed)
    a = rng.random((request.n, request.n)).astype(dtype, copy=False)
    b = rng.random((request.n, request.n)).astype(dtype, copy=False)

    # Warm-up is intentionally excluded from the reported measurement.
    np.matmul(a, b)

    started = time.perf_counter()
    c = np.matmul(a, b)
    elapsed = time.perf_counter() - started

    return {
        "status": "MEASURED",
        "execution": "VERCEL_FUNCTION",
        "n": request.n,
        "dtype": dtype_name,
        "seed": request.seed,
        "t_compute_s": elapsed,
        "result_checksum": float(np.sum(c, dtype=np.float64)),
        "matrix_bytes": request.n * request.n * dtype.itemsize,
    }
