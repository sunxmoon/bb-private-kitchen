#!/usr/bin/env python3
"""
Host-side HTTP proxy for AGY CLI (Antigravity CLI).
Uses FastAPI for asynchronous concurrency and Smart-Path for zero-config discovery.
"""
import asyncio
import json
import logging
import os
import shutil
import sys
import subprocess
from typing import Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Body, Response
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="[agy-proxy] %(asctime)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Constants
HOST = os.getenv("AGY_PROXY_HOST", "0.0.0.0")
PORT = int(os.getenv("AGY_PROXY_PORT", "8765"))
TIMEOUT = int(os.getenv("AGY_PROXY_TIMEOUT", "120"))

class GenerateRequest(BaseModel):
    prompt: str

class SmartPathFinder:
    @staticmethod
    def find_agy() -> Optional[str]:
        # 1. Explicit env var
        explicit = os.getenv("AGY_BIN")
        if explicit and (os.path.isfile(explicit) or shutil.which(explicit)):
            return explicit

        # 2. Search common install paths
        home = os.path.expanduser("~")
        for candidate in [
            os.path.join(home, ".local/bin/agy"),
            os.path.join(home, ".antigravity/bin/agy"),
            "/usr/local/bin/agy",
        ]:
            if os.path.isfile(candidate):
                return candidate

        # 3. Standard system paths
        return shutil.which("agy")

    @staticmethod
    def get_agy_home() -> Optional[str]:
        """Try to find where agy config resides."""
        home = os.path.expanduser("~")
        # AGY shares config with gemini
        if os.path.isdir(os.path.join(home, ".gemini")):
            return home
        for p in ["/root", "/home/moon"]:
            if os.path.isdir(os.path.join(p, ".gemini")):
                return p
        return None

AGY_BIN = SmartPathFinder.find_agy()
AGY_HOME = SmartPathFinder.get_agy_home()

def get_subprocess_env() -> dict:
    env = os.environ.copy()
    env["LANG"] = "en_US.UTF-8"
    env["LC_ALL"] = "en_US.UTF-8"
    env["PYTHONUTF8"] = "1"

    if AGY_HOME:
        env["HOME"] = AGY_HOME

    # Ensure PATH includes the directory of agy
    paths = ["/usr/local/bin", "/usr/bin", "/bin"]
    if AGY_BIN:
        bin_dir = os.path.dirname(os.path.realpath(AGY_BIN))
        if bin_dir not in paths:
            paths.insert(0, bin_dir)

    env["PATH"] = ":".join(paths) + ":" + env.get("PATH", "")
    return env

@asynccontextmanager
async def lifespan(app: FastAPI):
    if AGY_BIN:
        logger.info("Smart-Path: Found agy at %s", AGY_BIN)
        if AGY_HOME:
            logger.info("Smart-Path: Using config from %s/.gemini", AGY_HOME)
    else:
        logger.error("Smart-Path: agy CLI NOT FOUND! Please install it.")
    yield

app = FastAPI(title="AGY Proxy", version="1.0.0", lifespan=lifespan)

@app.get("/health")
async def health():
    if not AGY_BIN:
        return {"ok": False, "reason": "agy not found"}
    try:
        proc = await asyncio.create_subprocess_exec(
            AGY_BIN, "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=get_subprocess_env()
        )
        await asyncio.wait_for(proc.wait(), timeout=5)
        return {"ok": proc.returncode == 0}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post("/generate")
async def generate(req: GenerateRequest):
    if not AGY_BIN:
        raise HTTPException(status_code=503, detail="AGY CLI not configured")

    try:
        proc = await asyncio.create_subprocess_exec(
            AGY_BIN, "--print", req.prompt,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=get_subprocess_env()
        )

        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=TIMEOUT
        )

        if proc.returncode != 0:
            err_msg = stderr.decode("utf-8", errors="replace")
            logger.error("AGY failed (exit %d): %s", proc.returncode, err_msg[:500])
            raise HTTPException(status_code=500, detail={"error": "AGY failed", "stderr": err_msg})

        return Response(content=stdout, media_type="text/plain")

    except asyncio.TimeoutError:
        logger.error("AGY timed out after %ds", TIMEOUT)
        raise HTTPException(status_code=504, detail="AGY processing timed out")
    except Exception as e:
        logger.error("Unexpected error: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
