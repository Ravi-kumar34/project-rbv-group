from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Import centralized configuration
from backend.config.database import image_collection

# Import modular routers
from backend.routers import auth, game, leaderboard

# Import the black-box facial recognition module logic
#from backend.services.face_verifier import build_encodings_cache

# ---------- APPLICATION LIFECYCLE MANAGMENT ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles background processing required before the server 
    begins accepting client HTTP/WebSocket traffic.
    """
    print("Initializing server deployment protocols...")
    print("Syncing MongoDB document records and building face encodings cache...")
    
    try:
        # Fetch data mapping from MongoDB cluster
        db_images = {doc["uid"]: doc["image"] for doc in image_collection.find()}
        
        # Build cache and hand it off cleanly to the auth router context
        # auth.initialize_encodings_cache(db_images, build_encodings_cache)
    except Exception as e:
        print(f"CRITICAL: Failed to build startup face encodings cache: {str(e)}")
        
    yield
    print("Shutting down server environment...")


app = FastAPI(lifespan=lifespan)


# ---------- GLOBAL CORS MIDDLEWARE CONFIGURATION ----------
# Configured for multi-device network testing across local systems
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://websocket-tictactoe-engine.vercel.app"], 
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- ROUTER ROUTING INTEGRATION ----------
app.include_router(auth.router)
app.include_router(game.router)
app.include_router(leaderboard.router)


# ---------- STATIC FILE LAYOUT SERVICES ----------
# Serves UI documents, styles, and web scripts natively out of your frontend folder
app.mount("/", StaticFiles(directory="frontend", html=True), name="static")