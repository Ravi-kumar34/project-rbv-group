import os
from dotenv import load_dotenv
from fastapi import APIRouter
import mysql.connector

# Load the environment variables
load_dotenv()

router = APIRouter()

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD"),      # <-- Securely loaded!
        database=os.getenv("MYSQL_DATABASE", "project")
    )

def update_elo_and_record(winner_uid, p1_uid, p2_uid):
    """
    Calculates Elo using the standard formula and updates the database.
    Also records the match in the matches table.
    winner_uid is 'Draw', player1's UID, or player2's UID.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Fetch current ratings before the calculation
    cursor.execute("SELECT uid, elo_rating FROM users WHERE uid IN (%s, %s)", (p1_uid, p2_uid))
    rows = cursor.fetchall()
    ratings = {row[0]: row[1] for row in rows}

    r1 = ratings[p1_uid]
    r2 = ratings[p2_uid]

    # 2. Compute Expected Win Probability (E)
    e1 = 1 / (1 + 10 ** ((r2 - r1) / 400))
    e2 = 1 / (1 + 10 ** ((r1 - r2) / 400))

    # 3. Determine the actual score (S)
    K = 32
    db_winner = None
    
    if winner_uid == "Draw":
        s1, s2 = 0.5, 0.5
    elif winner_uid == p1_uid:
        s1, s2 = 1.0, 0.0
        db_winner = p1_uid
    else:
        s1, s2 = 0.0, 1.0
        db_winner = p2_uid

    # 4. Calculate New Ratings
    new_r1 = round(r1 + K * (s1 - e1))
    new_r2 = round(r2 + K * (s2 - e2))

    # 5. Update Users Table
    cursor.execute("UPDATE users SET elo_rating=%s WHERE uid=%s", (new_r1, p1_uid))
    cursor.execute("UPDATE users SET elo_rating=%s WHERE uid=%s", (new_r2, p2_uid))

    # 6. Record Match in matches table
    cursor.execute(
        "INSERT INTO matches (player1_uid, player2_uid, winner_uid) VALUES (%s, %s, %s)",
        (p1_uid, p2_uid, db_winner)
    )

    conn.commit()
    conn.close()

@router.get("/leaderboard")
def get_leaderboard():
    """Fetches all users sorted by Elo for the leaderboard.html page"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT uid, name, elo_rating, is_online FROM users ORDER BY elo_rating DESC")
    users = cursor.fetchall()
    conn.close()
    
    return {"leaderboard": users}