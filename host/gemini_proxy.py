#!/usr/bin/env python3
"""
Modernized Host-side HTTP proxy for Gemini CLI.
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
    format="[gemini-proxy] %(asctime)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Constants
HOST = os.getenv("GEMINI_PROXY_HOST", "0.0.0.0")
PORT = int(os.getenv("GEMINI_PROXY_PORT", "8765"))
TIMEOUT = int(os.getenv("GEMINI_PROXY_TIMEOUT", "120"))

class GenerateRequest(BaseModel):
    prompt: str

class SmartPathFinder:
    @staticmethod
    def find_gemini() -> Optional[str]:
        # 1. Explicit env var
        explicit = os.getenv("GEMINI_BIN")
        if explicit and (os.path.isfile(explicit) or shutil.which(explicit)):
            return explicit

        # 2. Search NVM paths
        home = os.path.expanduser("~")
        nvm_dir = os.getenv("NVM_DIR", os.path.join(home, ".nvm"))
        if os.path.isdir(nvm_dir):
            # Find the latest node version bin
            versions_dir = os.path.join(nvm_dir, "versions/node")
            if os.path.isdir(versions_dir):
                for v in sorted(os.listdir(versions_dir), reverse=True):
                    candidate = os.path.join(versions_dir, v, "bin/gemini")
                    if os.path.isfile(candidate):
                        return candidate

        # 3. Search NPM global prefix
        try:
            npm_prefix = subprocess.check_output(["npm", "config", "get", "prefix"], text=True).strip()
            candidate = os.path.join(npm_prefix, "bin/gemini")
            if os.path.isfile(candidate):
                return candidate
        except:
            pass

        # 4. Standard system paths
        return shutil.which("gemini")

    @staticmethod
    def get_gemini_home() -> Optional[str]:
        """Try to find where .gemini config resides."""
        home = os.path.expanduser("~")
        if os.path.isdir(os.path.join(home, ".gemini")):
            return home
        # Fallback to common root/service homes
        for p in ["/root", "/home/moon"]:
            if os.path.isdir(os.path.join(p, ".gemini")):
                return p
        return None

GEMINI_BIN = SmartPathFinder.find_gemini()
GEMINI_HOME = SmartPathFinder.get_gemini_home()

def get_subprocess_env() -> dict:
    env = os.environ.copy()
    env["LANG"] = "en_US.UTF-8"
    env["LC_ALL"] = "en_US.UTF-8"
    env["PYTHONUTF8"] = "1"
    env["GEMINI_CLI_TRUST_WORKSPACE"] = "true"
    
    if GEMINI_HOME:
        env["GEMINI_CLI_HOME"] = GEMINI_HOME
        env["HOME"] = GEMINI_HOME

    # Crucial: Ensure the PATH includes the directory of gemini (and its node)
    paths = ["/usr/local/bin", "/usr/bin", "/bin"]
    if GEMINI_BIN:
        bin_dir = os.path.dirname(os.path.realpath(GEMINI_BIN))
        if bin_dir not in paths:
            paths.insert(0, bin_dir)
    
    env["PATH"] = ":".join(paths) + ":" + env.get("PATH", "")
    return env

@asynccontextmanager
async def lifespan(app: FastAPI):
    if GEMINI_BIN:
        logger.info("Smart-Path: Found gemini at %s", GEMINI_BIN)
        if GEMINI_HOME:
            logger.info("Smart-Path: Using config from %s/.gemini", GEMINI_HOME)
    else:
        logger.error("Smart-Path: gemini CLI NOT FOUND! Please install it.")
    yield

app = FastAPI(title="Gemini Proxy", version="0.2.0", lifespan=lifespan)

@app.get("/health")
async def health():
    if not GEMINI_BIN:
        return {"ok": False, "reason": "gemini not found"}
    try:
        proc = await asyncio.create_subprocess_exec(
            GEMINI_BIN, "--version",
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
    if not GEMINI_BIN:
        raise HTTPException(status_code=503, detail="Gemini CLI not configured")

    try:
        # Run gemini with prompt on stdin
        proc = await asyncio.create_subprocess_exec(
            GEMINI_BIN, "-p", ".",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=get_subprocess_env()
        )

        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=req.prompt.encode("utf-8")),
            timeout=TIMEOUT
        )

        if proc.returncode != 0:
            err_msg = stderr.decode("utf-8", errors="replace")
            logger.error("Gemini failed (exit %d): %s", proc.returncode, err_msg[:500])
            raise HTTPException(status_code=500, detail={"error": "Gemini failed", "stderr": err_msg})

        return Response(content=stdout, media_type="text/plain")

    except asyncio.TimeoutExpired:
        logger.error("Gemini timed out after %ds", TIMEOUT)
        raise HTTPException(status_code=504, detail="Gemini processing timed out")
    except Exception as e:
        logger.error("Unexpected error: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
