from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..services.monitor_hub import monitor_hub

router = APIRouter(tags=["monitor"])


@router.websocket("/ws/monitor")
async def monitor_websocket(websocket: WebSocket):
    await monitor_hub.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        monitor_hub.disconnect(websocket)
