from fastapi import FastAPI
import os

app = FastAPI()

@app.get("/health")
async def health() -> dict[str, str]:
    """Healthcheck endpoint for Railway."""
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port) 