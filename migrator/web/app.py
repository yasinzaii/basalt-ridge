import asyncio
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from main import run
from migrator.utils.files import read_json
from migrator.web.login import interactive_login

app = FastAPI()
run_lock = asyncio.Lock()


@app.get("/")
async def index():
    return FileResponse(Path(__file__).with_name("index.html"))


@app.websocket("/ws")
async def migration(websocket: WebSocket):
    await websocket.accept()
    task = None
    receiver = None
    try:
        request = await websocket.receive_json()
        source = request.get("source")
        if source not in {"cliniko", "zanda"}:
            await websocket.send_json({"type": "error", "message": "Choose Cliniko or Zanda."})
            return
        if run_lock.locked():
            await websocket.send_json({"type": "error", "message": "A migration is already running."})
            return
        async with run_lock:
            inputs = asyncio.Queue()

            async def receive_inputs():
                while True:
                    await inputs.put(await websocket.receive_json())

            async def ask(event):
                await websocket.send_json({"type": "question", **event})
                answer = await inputs.get()
                value = answer.get("value")
                if not isinstance(value, str):
                    raise ValueError("Invalid input")
                return value

            async def login_handler(backend, browser, selected_source, directory):
                await interactive_login(backend, browser, selected_source, directory, ask)

            async def progress(stage, status, limitations=None):
                await websocket.send_json({"type": "progress", "stage": stage,
                                           "status": status, "limitations": limitations or []})

            receiver = asyncio.create_task(receive_inputs())
            task = asyncio.create_task(run("all", source=source, login_handler=login_handler, progress=progress))
            done, _ = await asyncio.wait({task, receiver}, return_when=asyncio.FIRST_COMPLETED)
            if receiver in done:
                receiver.result()
            output = task.result()
            manifest = read_json(output / "manifest.json")
            await websocket.send_json({"type": "done", "directory": str(output), "status": manifest["status"]})
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await websocket.send_json({"type": "error", "message": f"Extraction failed: {type(exc).__name__}"})
        except (RuntimeError, WebSocketDisconnect):
            pass
    finally:
        for pending in (task, receiver):
            if pending and not pending.done():
                pending.cancel()
        await asyncio.gather(*(p for p in (task, receiver) if p), return_exceptions=True)
        try:
            await websocket.close()
        except RuntimeError:
            pass
