from __future__ import annotations

import json
import logging
from typing import Dict, List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Signaling"],
)


class ConnectionManager:
    def __init__(self):
        # meeting_id -> list of {"peer_id": str, "user_name": str, "websocket": WebSocket}
        self.rooms: Dict[int, List[dict]] = {}

    async def connect(
        self,
        meeting_id: int,
        peer_id: str,
        user_name: str,
        websocket: WebSocket,
    ):
        if meeting_id not in self.rooms:
            self.rooms[meeting_id] = []

        # List existing peers in this room
        existing_users = [
            {"peerId": p["peer_id"], "userName": p["user_name"]}
            for p in self.rooms[meeting_id]
        ]

        # Send existing users list to the new peer
        await websocket.send_text(
            json.dumps({
                "type": "room_users",
                "users": existing_users,
            })
        )

        # Notify existing participants about the new user
        for p in self.rooms[meeting_id]:
            try:
                await p["websocket"].send_text(
                    json.dumps({
                        "type": "user_joined",
                        "peerId": peer_id,
                        "userName": user_name,
                    })
                )
            except Exception:
                pass

        self.rooms[meeting_id].append({
            "peer_id": peer_id,
            "user_name": user_name,
            "websocket": websocket,
        })
        logger.info(f"Peer {peer_id} ({user_name}) joined room {meeting_id}. Total: {len(self.rooms[meeting_id])}")

    def disconnect(self, meeting_id: int, peer_id: str):
        if meeting_id in self.rooms:
            self.rooms[meeting_id] = [
                p for p in self.rooms[meeting_id] if p["peer_id"] != peer_id
            ]
            if not self.rooms[meeting_id]:
                del self.rooms[meeting_id]

    async def broadcast_to_room(
        self,
        meeting_id: int,
        sender_peer_id: str,
        message: dict,
    ):
        if meeting_id not in self.rooms:
            return

        target_peer = message.get("target")
        text_data = json.dumps(message)

        for p in self.rooms[meeting_id]:
            if target_peer:
                # Direct signal to specific peer (offer, answer, candidate)
                if p["peer_id"] == target_peer:
                    try:
                        await p["websocket"].send_text(text_data)
                    except Exception:
                        pass
            else:
                # Broadcast to all other peers in the room
                if p["peer_id"] != sender_peer_id:
                    try:
                        await p["websocket"].send_text(text_data)
                    except Exception:
                        pass


manager = ConnectionManager()


@router.websocket("/ws/meetings/{meeting_id}")
async def websocket_signaling(websocket: WebSocket, meeting_id: int):
    await websocket.accept()
    peer_id = None
    user_name = "Guest"
    try:
        # First message expected: join announcement
        init_data = await websocket.receive_text()
        init_msg = json.loads(init_data)
        peer_id = init_msg.get("peerId") or f"peer_{id(websocket)}"
        user_name = init_msg.get("userName") or "Guest"

        await manager.connect(meeting_id, peer_id, user_name, websocket)

        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            message["sender"] = peer_id
            await manager.broadcast_to_room(meeting_id, peer_id, message)

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for peer {peer_id} in room {meeting_id}")
    except Exception as exc:
        logger.warning(f"WebSocket error for peer {peer_id}: {exc}")
    finally:
        if peer_id:
            manager.disconnect(meeting_id, peer_id)
            await manager.broadcast_to_room(
                meeting_id,
                peer_id,
                {
                    "type": "user_left",
                    "peerId": peer_id,
                },
            )
