import base64
from fastapi import APIRouter
from pydantic import BaseModel
from backend.config.database import get_mysql_connection
from backend.services.face_verifier import build_encodings_cache

router = APIRouter(tags=["Authentication"])

# Global in-memory data structures for auth state
encodings_cache = {}
sessions = {}

class LoginRequest(BaseModel):
    image: str

# Helper function to let main.py populate the cache during server startup
def initialize_encodings_cache(db_images_dict, build_cache_func):
    global encodings_cache
    encodings_cache = build_cache_func(db_images_dict)


# ---------- 1. STANDARD FACE LOGIN API ----------
@router.post("/login")
def login(request: LoginRequest):
    conn = get_mysql_connection()
    cursor = conn.cursor(buffered=True)
    try:
        # Extract and decode image bytes from base64 string
        base64_data = request.image.split(",")[1]
        login_image_bytes = base64.b64decode(base64_data)

        # Match against our isolated local cache reference
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
@router.post("/loginroll")
def loginroll(dev_uid: str):
    conn = get_mysql_connection()
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