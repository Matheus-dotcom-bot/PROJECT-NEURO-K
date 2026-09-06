from fastapi import FastAPI

app = FastAPI(
    title="PROJECT-NEURO-K",
    description="Adaptive computational offloading proof of concept.",
    version="2.5.0",
)


@app.get("/")
def root():
    return {
        "project": "PROJECT-NEURO-K",
        "status": "online",
        "service": "Vercel API",
        "architecture": "FastAPI + ZeroMQ worker",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "neuro-k-api",
    }
