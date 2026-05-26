from fastapi import FastAPI
from pydantic import BaseModel
import base64
from pymongo import MongoClient
import mysql.connector
from fastapi.middleware.cors import CORSMiddleware
from backend.facial_recognition_module import find_closest_match
from fastapi import WebSocket, WebSocketDisconnect
import json
import uuid

# Add this right below your sessions dictionary
active_games = {}

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    # Explicitly allow the Live Server addresses
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions = {}

# ---------- Request Model ----------
class LoginRequest(BaseModel):
    image: str   # base64 image

# ---------- MySQL ----------
mysql_conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="MySQLpassword42",
    database="project"
)
mysql_cursor = mysql_conn.cursor()

# ---------- MongoDB ----------
mongo_client = MongoClient("mongodb://localhost:27017/")
mongo_db = mongo_client["project_db"]
collection = mongo_db["images"]

from backend.facial_recognition_module import build_encodings_cache

# Convert MongoDB data → dictionary
db_images = {}

for doc in collection.find():
    uid = doc["uid"]
    image_data = doc["image"]
    db_images[uid] = image_data

# Build cache once at startup
encodings_cache = build_encodings_cache(db_images)

# ---------- WEBSOCKET CONNECTION MANAGER ----------
class ConnectionManager:
    def __init__(self):
        # Maps uid -> WebSocket object for O(1) routing
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, uid: str):
        await websocket.accept()
        self.active_connections[uid] = websocket

# Replace your old disconnect function with this one:
    def disconnect(self, websocket: WebSocket, uid: str):
        # Only delete the connection if the socket trying to disconnect is the CURRENT active one
        if uid in self.active_connections and self.active_connections[uid] == websocket:
            del self.active_connections[uid]
    async def broadcast(self, message: dict):
        """Send a message to ALL connected clients (e.g., lobby updates)."""
        json_message = json.dumps(message)
        
        # --- THE FIX: Wrap .values() in list() ---
        for connection in list(self.active_connections.values()):
            try:
                await connection.send_text(json_message)
            except Exception:
                # If a specific connection is dead, ignore it and keep broadcasting to the others
                pass
    async def send_personal_message(self, message: dict, uid: str):
        """Send a message to ONE specific client (e.g., matchmaking challenge)."""
        if uid in self.active_connections:
            await self.active_connections[uid].send_text(json.dumps(message))

manager = ConnectionManager()

#---------- LOGIN API ----------
@app.post("/login")
def login(request: LoginRequest):

    try:
        # Decode Base64 image
        base64_data = request.image.split(",")[1]
        login_image_bytes = base64.b64decode(base64_data)

        # Fetch images from MongoDB
        # Face match
        matched_uid = find_closest_match(login_image_bytes, encodings_cache)

        # Check result
        if matched_uid is None:
            return {"message": "Login Failed"}

        # Verify in MySQL
        mysql_cursor.execute(
            "SELECT * FROM users WHERE uid=%s",(matched_uid,)
        )

        user = mysql_cursor.fetchone()

        if not user:
            return {"message": "User not found"}

        # Update is_online
        mysql_cursor.execute(
            "UPDATE users SET is_online=TRUE WHERE uid=%s",(matched_uid,)
        )
        mysql_conn.commit()

        # Success
        sessions[matched_uid] = True

        return {
            "message": "Login Success",
            "uid": matched_uid
        }

    except Exception as e:
        return {"message": f"Error: {str(e)}"}
# # ---------- LOGIN API (DEV BYPASS) ----------
# @app.post("/login")
# def login(request: LoginRequest):
#     print("⚠️ DEV MODE: Skipping slow facial recognition...")
    
#     # Hardcode your UID here so the system knows who is logging in
#     dev_uid = "2025101040" 

#     try:
#         # We still MUST update MySQL so Phase 3 knows you are online
#         mysql_cursor.execute(
#             "UPDATE users SET is_online=TRUE WHERE uid=%s", (dev_uid,)
#         )
#         mysql_conn.commit()

#         sessions[dev_uid] = True

#         # Instantly return success!
#         return {
#             "message": "Login Success",
#             "uid": dev_uid
#         }

#     except Exception as e:
#         return {"message": f"Error: {str(e)}"}
def check_winner(board):
    win_combinations = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8], # Rows
        [0, 3, 6], [1, 4, 7], [2, 5, 8], # Columns
        [0, 4, 8], [2, 4, 6]             # Diagonals
    ]
    for combo in win_combinations:
        a, b, c = combo
        if board[a] is not None and board[a] == board[b] == board[c]:
            return board[a]  # Returns "X" or "O"
            
    if None not in board:
        return "Draw" # Board is full
        
    return None # Game is still going
# ---------- PHASE 3: THE LIVE ARENA ----------
# ---------- PHASE 3: THE LIVE ARENA ----------
@app.websocket("/ws/{uid}")
async def websocket_endpoint(websocket: WebSocket, uid: str):
    await manager.connect(websocket, uid)

    try:
        # 1. Update MySQL: Mark user as online
        mysql_cursor.execute("UPDATE users SET is_online=TRUE WHERE uid=%s", (uid,))
        mysql_conn.commit()

        # 2. Fetch the updated list of online players
        mysql_cursor.execute("SELECT uid, name, elo_rating FROM users WHERE is_online=TRUE")
        online_users = [{"uid": row[0], "name": row[1], "elo": row[2]} for row in mysql_cursor.fetchall()]

        # 3. Broadcast the new lobby state to everyone
        await manager.broadcast({"type": "lobby_update", "users": online_users})

        # Keep the connection open and listen for incoming messages
        while True:
            # WAIT FOR A MESSAGE FIRST
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # --- 1. MATCHMAKING CHALLENGE ---
            if message["type"] == "challenge":
                target_uid = message["target_uid"]
                from_uid = message["from_uid"]
                
                mysql_cursor.execute("SELECT name FROM users WHERE uid=%s", (from_uid,))
                challenger_name = mysql_cursor.fetchone()[0]
                
                forward_msg = {
                    "type": "incoming_challenge",
                    "from_uid": from_uid,
                    "from_name": challenger_name
                }
                await manager.send_personal_message(forward_msg, target_uid)
                print(f"Routed challenge from {challenger_name} to UID {target_uid}")

            # --- 2. MATCHMAKING RESPONSE ---
            elif message["type"] == "challenge_response":
                target_uid = message["target_uid"] # The original challenger
                from_uid = message["from_uid"]     # The person responding
                accepted = message["accepted"]

                if accepted:
                    game_id = str(uuid.uuid4())
                    
                    active_games[game_id] = {
                        "player1": target_uid, 
                        "player2": from_uid,   
                        "turn": target_uid,    
                        "board": [None] * 9    
                    }

                    start_msg = {"type": "match_start", "game_id": game_id}
                    await manager.send_personal_message(start_msg, target_uid)
                    await manager.send_personal_message(start_msg, from_uid)
                    print(f"Match started! Room: {game_id} | {target_uid} vs {from_uid}")
                    
                else:
                    reject_msg = {
                        "type": "challenge_rejected", 
                        "message": "Your challenge was declined."
                    }
                    await manager.send_personal_message(reject_msg, target_uid)
            # --- 4. FETCH INITIAL GAME STATE ---
            elif message["type"] == "fetch_state":
                game_id = message["game_id"]
                if game_id in active_games:
                    game = active_games[game_id]
                    state_msg = {
                        "type": "game_state",
                        "board": game["board"],
                        "turn": game["turn"]
                    }
                    await manager.send_personal_message(state_msg, uid)

# --- 3. TIC-TAC-TOE MOVES (SERVER AUTHORITATIVE) ---
 # --- 3. TIC-TAC-TOE MOVES (SERVER AUTHORITATIVE) ---
            elif message["type"] == "move":
                game_id = message["game_id"]
                cell_index = message["cell_index"]

                if game_id in active_games:
                    game = active_games[game_id]

                    # Anti-Cheat: Is it their turn? Is the cell empty?
                    if game["turn"] == uid and game["board"][cell_index] is None:
                        
                        mark = "X" if game["player1"] == uid else "O"
                        game["board"][cell_index] = mark
                        
                        next_turn = game["player2"] if game["player1"] == uid else game["player1"]
                        game["turn"] = next_turn

                        # CHECK FOR A WINNER BEFORE BROADCASTING
                        winner_mark = check_winner(game["board"])

                        if winner_mark:
                            # Game is over!
                            if winner_mark == "Draw":
                                winner_uid = "Draw"
                            else:
                                winner_uid = game["player1"] if winner_mark == "X" else game["player2"]
                                loser_uid = game["player2"] if winner_mark == "X" else game["player1"]
                                
                                # --- NEW: UPDATE ELO RATINGS IN MYSQL ---
                                mysql_cursor.execute("UPDATE users SET elo_rating = elo_rating + 25 WHERE uid=%s", (winner_uid,))
                                mysql_cursor.execute("UPDATE users SET elo_rating = elo_rating - 25 WHERE uid=%s", (loser_uid,))
                                mysql_conn.commit()

                                # Broadcast the new lobby so everyone sees the updated scores!
                                mysql_cursor.execute("SELECT uid, name, elo_rating FROM users WHERE is_online=TRUE")
                                updated_users = [{"uid": row[0], "name": row[1], "elo": row[2]} for row in mysql_cursor.fetchall()]
                                await manager.broadcast({"type": "lobby_update", "users": updated_users})
                            
                            game_over_msg = {
                                "type": "game_over",
                                "board": game["board"],
                                "winner": winner_uid
                            }
                            await manager.send_personal_message(game_over_msg, game["player1"])
                            await manager.send_personal_message(game_over_msg, game["player2"])
                            
                            # Clean up the server memory
                            del active_games[game_id]
                            print(f"Game Over! Room {game_id} closed.")

                        else:
                            # Game continues normally
                            state_msg = {
                                "type": "game_state",
                                "board": game["board"],
                                "turn": game["turn"]
                            }
                            await manager.send_personal_message(state_msg, game["player1"])
                            await manager.send_personal_message(state_msg, game["player2"])
    except WebSocketDisconnect:
        # 1. Disconnect the specific socket
        manager.disconnect(websocket, uid)
        
        # 2. Update MySQL: Mark user as offline
        mysql_cursor.execute("UPDATE users SET is_online=FALSE WHERE uid=%s", (uid,))
        mysql_conn.commit()

        # 3. Broadcast the updated Lobby to everyone else so the disconnected player disappears
        mysql_cursor.execute("SELECT uid, name, elo_rating FROM users WHERE is_online=TRUE")
        online_users = [{"uid": row[0], "name": row[1], "elo": row[2]} for row in mysql_cursor.fetchall()]
        await manager.broadcast({"type": "lobby_update", "users": online_users})