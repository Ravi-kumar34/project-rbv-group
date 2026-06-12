import json
import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.config.database import get_mysql_connection

# Importing modularized services
from backend.services.game_logic import check_winner
from backend.services.elo_engine import update_elo_and_record

router = APIRouter(tags=["Game Arena"])

# In-memory tracking for active match states
active_games = {}


# ---------- WEBSOCKET CONNECTION MANAGER ----------
class ConnectionManager:
    def __init__(self):
        self.active_connections = {}

    async def connect(self, websocket: WebSocket, uid: str):
        await websocket.accept()
        self.active_connections[uid] = websocket

    def disconnect(self, websocket: WebSocket, uid: str):
        if uid in self.active_connections and self.active_connections[uid] == websocket:
            del self.active_connections[uid]

    async def broadcast(self, message: dict):
        json_message = json.dumps(message)
        # Safe broadcasting: prevents one bad connection from crashing the loop
        for connection in list(self.active_connections.values()):
            try:
                await connection.send_text(json_message)
            except Exception:
                pass

    async def send_personal_message(self, message: dict, uid: str):
        if uid in self.active_connections:
            await self.active_connections[uid].send_text(json.dumps(message))


manager = ConnectionManager()


# ---------- REAL-TIME GAME ARENA (WEBSOCKET) ----------
@router.websocket("/ws/{uid}")
async def websocket_endpoint(websocket: WebSocket, uid: str):
    await manager.connect(websocket, uid)

    conn = get_mysql_connection()
    cursor = conn.cursor(buffered=True)

    try:
        # Mark user online upon connection and update lobby
        cursor.execute("UPDATE users SET is_online=TRUE WHERE uid=%s", (uid,))
        conn.commit()

        cursor.execute("SELECT uid, name, elo_rating FROM users WHERE is_online=TRUE")
        online_users = [{"uid": row[0], "name": row[1], "elo": row[2]} for row in cursor.fetchall()]
        await manager.broadcast({"type": "lobby_update", "users": online_users})

        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # 1. CHALLENGE HANDSHAKE
            if message["type"] == "challenge":
                target_uid = message["target_uid"]
                from_uid = message["from_uid"]
                
                cursor.execute("SELECT name FROM users WHERE uid=%s", (from_uid,))
                challenger_name = cursor.fetchone()[0]
                
                forward_msg = {
                    "type": "incoming_challenge",
                    "from_uid": from_uid,
                    "from_name": challenger_name
                }
                await manager.send_personal_message(forward_msg, target_uid)

            # 2. CHALLENGE RESPONSE (MATCH CREATION)
            elif message["type"] == "challenge_response":
                target_uid = message["target_uid"]
                from_uid = message["from_uid"]
                accepted = message["accepted"]

                if accepted:
                    game_id = str(uuid.uuid4())
                    
                    # Arena flags added for forfeit protection
                    active_games[game_id] = {
                        "player1": target_uid, 
                        "player2": from_uid,   
                        "turn": target_uid,    
                        "board": [None] * 9,
                        "p1_in_arena": False,
                        "p2_in_arena": False
                    }
                    start_msg = {"type": "match_start", "game_id": game_id}
                    await manager.send_personal_message(start_msg, target_uid)
                    await manager.send_personal_message(start_msg, from_uid)
                else:
                    reject_msg = {"type": "challenge_rejected", "message": "Your challenge was declined."}
                    await manager.send_personal_message(reject_msg, target_uid)
                    
            # 3. COMPONENT MOUNT / STATE SYNC
            elif message["type"] == "fetch_state":
                game_id = message["game_id"]
                if game_id in active_games:
                    game = active_games[game_id]

                    # Track when players successfully mount the game UI component
                    if uid == game["player1"]:
                        game["p1_in_arena"] = True
                    elif uid == game["player2"]:
                        game["p2_in_arena"] = True

                    state_msg = {"type": "game_state", "board": game["board"], "turn": game["turn"]}
                    await manager.send_personal_message(state_msg, uid)

            # 4. GAME MOVE EVALUATION
            elif message["type"] == "move":
                game_id = message["game_id"]
                cell_index = message["cell_index"]

                if game_id in active_games:
                    game = active_games[game_id]

                    if game["turn"] == uid and game["board"][cell_index] is None:
                        mark = "X" if game["player1"] == uid else "O"
                        game["board"][cell_index] = mark
                        
                        next_turn = game["player2"] if game["player1"] == uid else game["player1"]
                        game["turn"] = next_turn

                        # Evaluates board layout using the logic service
                        winner_mark = check_winner(game["board"])
                        if winner_mark:
                            if winner_mark == "Draw":
                                winner_uid = "Draw"
                            else:
                                winner_uid = game["player1"] if winner_mark == "X" else game["player2"]
                                
                            # Process victory Elo changes through pure backend service
                            update_elo_and_record(winner_uid, game["player1"], game["player2"])

                            cursor.execute("SELECT uid, name, elo_rating FROM users WHERE is_online=TRUE")
                            updated_users = [{"uid": row[0], "name": row[1], "elo": row[2]} for row in cursor.fetchall()]
                            await manager.broadcast({"type": "lobby_update", "users": updated_users})
                            
                            game_over_msg = {"type": "game_over", "board": game["board"], "winner": winner_uid}
                            await manager.send_personal_message(game_over_msg, game["player1"])
                            await manager.send_personal_message(game_over_msg, game["player2"])
                            
                            del active_games[game_id]
                        else:
                            state_msg = {"type": "game_state", "board": game["board"], "turn": game["turn"]}
                            await manager.send_personal_message(state_msg, game["player1"])
                            await manager.send_personal_message(state_msg, game["player2"])
                            
    except WebSocketDisconnect:
        manager.disconnect(websocket, uid)
        
        # --- IN-ARENA FORFEIT PROTECTION ---
        game_id_to_close = None
        for g_id, game in active_games.items():
            if game["player1"] == uid or game["player2"] == uid:
                if game.get("p1_in_arena") and game.get("p2_in_arena"):
                    game_id_to_close = g_id
                break

        if game_id_to_close:
            game = active_games[game_id_to_close]
            winner_uid = game["player2"] if game["player1"] == uid else game["player1"]
            
            # Forfeit trigger: Process automatic victory award
            update_elo_and_record(winner_uid, game["player1"], game["player2"])
            
            forfeit_msg = {"type": "game_over", "board": game["board"], "winner": winner_uid}
            await manager.send_personal_message(forfeit_msg, winner_uid)
            del active_games[game_id_to_close]

        # Ghost disconnect protection
        if uid not in manager.active_connections:
            cursor.execute("UPDATE users SET is_online=FALSE WHERE uid=%s", (uid,))
            conn.commit()

            cursor.execute("SELECT uid, name, elo_rating FROM users WHERE is_online=TRUE")
            online_users = [{"uid": row[0], "name": row[1], "elo": row[2]} for row in cursor.fetchall()]
            await manager.broadcast({"type": "lobby_update", "users": online_users})

    finally:
        # Ensures no connection pool starvation ever happens
        cursor.close()
        conn.close()