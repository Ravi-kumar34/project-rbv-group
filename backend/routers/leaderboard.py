from fastapi import APIRouter
from backend.config.database import get_mysql_connection

router = APIRouter(tags=["Leaderboard & Profiles"])

# ---------- 1. USER PROFILE API ----------
@router.get("/user/{uid}")
def get_user_profile(uid: str):
    conn = get_mysql_connection()
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


# ---------- 2. GLOBAL LEADERBOARD API ----------
@router.get("/leaderboard")
def get_leaderboard():
    """Fetches all users sorted by Elo for the leaderboard layout"""
    conn = get_mysql_connection()
    # Using dictionary=True so rows are automatically formatted as JSON objects
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT uid, name, elo_rating, is_online FROM users ORDER BY elo_rating DESC")
        users = cursor.fetchall()
        return {"leaderboard": users}
    except Exception as e:
        return {"error": str(e)}
    finally:
        cursor.close()
        conn.close()