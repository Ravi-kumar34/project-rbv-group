from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import base64
import json
import uuid
from pymongo import MongoClient
import mysql.connector
from mysql.connector import pooling 
from fastapi.middleware.cors import CORSMiddleware
from backend.facial_recognition_module import find_closest_match, build_encodings_cache
from backend.phase4 import router, update_elo_and_record

active_games = {}
sessions = {}
app = FastAPI()

# Restored wildcard for multi-device local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

class LoginRequest(BaseModel):
    image: str

# 1. GLOBAL CONNECTION POOL (Thread-Safe Concurrency)
mysql_pool = mysql.connector.pooling.MySQLConnectionPool(
    pool_name="game_pool",
    pool_size=10,
    host="localhost",
    user="root",
    password="MySQLpassword42",
    database="project"
)

# 2. MONGO & STARTUP CACHE SETUP
mongo_client = MongoClient("mongodb://localhost:27017/")
mongo_db = mongo_client["project_db"]
collection = mongo_db["images"]

db_images = {doc["uid"]: doc["image"] for doc in collection.find()}
#encodings_cache = build_encodings_cache(db_images)


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


# ---------- 1. STANDARD FACE LOGIN API ----------
@app.post("/login")
def login(request: LoginRequest):
    conn = mysql_pool.get_connection()
    cursor = conn.cursor(buffered=True)
    try:
        base64_data = request.image.split(",")[1]
        login_image_bytes = base64.b64decode(base64_data)

        matched_uid = find_closest_match(login_image_bytes, encodings_cache)
        if matched_uid is None:
            return {"message": "Login Failed"}

        cursor.execute("SELECT * FROM users WHERE uid=%s", (matched_uid,))
        user = cursor.fetchone()

        if not user:
            return {"message": "User not found"}

        cursor.execute("UPDATE users SET is_online=TRUE WHERE uid=%s", (matched_uid,))
        conn.commit()

        sessions[matched_uid] = True
        return {"message": "Login Success", "uid": matched_uid}
    except Exception as e:
        return {"message": f"Error: {str(e)}"}
    finally:
        cursor.close()
        conn.close()


# ---------- 2. LOGINROLL (DEV BYPASS) ----------
@app.post("/loginroll")
def loginroll(dev_uid: str):
    conn = mysql_pool.get_connection()
    cursor = conn.cursor(buffered=True)
    try:
        cursor.execute("SELECT uid FROM users WHERE uid=%s", (dev_uid,))
        user = cursor.fetchone()

        if user is None:
            return {"message": "Invalid UID"}

        cursor.execute("UPDATE users SET is_online=TRUE WHERE uid=%s", (dev_uid,))
        conn.commit()

        sessions[dev_uid] = True
        return {"message": "Login Success", "uid": dev_uid}
    except Exception as e:
        return {"message": f"Error: {str(e)}"}
    finally:
        cursor.close()
        conn.close()


# ---------- 3. USER PROFILE API ----------
@app.get("/user/{uid}")
def get_user_profile(uid: str):
    conn = mysql_pool.get_connection()
    cursor = conn.cursor(buffered=True)
    try:
        cursor.execute("SELECT name, elo_rating FROM users WHERE uid=%s", (uid,))
        user = cursor.fetchone()
        
        if user is None:
            return {"error": "User not found"}
            
        return {
            "name": user[0],
            "elo_rating": user[1]
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        cursor.close()
        conn.close()


# ---------- HELPER: GAME WIN LOGIC ----------
def check_winner(board):
    win_combinations = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8],
        [0, 3, 6], [1, 4, 7], [2, 5, 8],
        [0, 4, 8], [2, 4, 6]             
    ]
    for combo in win_combinations:
        a, b, c = combo
        if board[a] is not None and board[a] == board[b] == board[c]:
            return board[a]
            
    if None not in board:
        return "Draw"
    return None


# ---------- 4. REAL-TIME GAME ARENA (WEBSOCKET) ----------
@app.websocket("/ws/{uid}")
async def websocket_endpoint(websocket: WebSocket, uid: str):
    await manager.connect(websocket, uid)

    conn = mysql_pool.get_connection()
    cursor = conn.cursor(buffered=True)

    try:
        cursor.execute("UPDATE users SET is_online=TRUE WHERE uid=%s", (uid,))
        conn.commit()

        cursor.execute("SELECT uid, name, elo_rating FROM users WHERE is_online=TRUE")
        online_users = [{"uid": row[0], "name": row[1], "elo": row[2]} for row in cursor.fetchall()]
        await manager.broadcast({"type": "lobby_update", "users": online_users})

        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
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

                        winner_mark = check_winner(game["board"])
                        if winner_mark:
                            if winner_mark == "Draw":
                                winner_uid = "Draw"
                            else:
                                winner_uid = game["player1"] if winner_mark == "X" else game["player2"]
                                
                            # Calls Phase 4 mathematical formula calculation and logs to matches table
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
            
            # Forfeit trigger: Process victory Elo changes through phase4
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