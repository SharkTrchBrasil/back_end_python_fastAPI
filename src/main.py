import socketio
import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from src.api.app.routes.realtime import sio
from src.core import database
from src.core.models import Base

from src.api.admin import router as admin_router
from src.api.app import router as app_router


Base.metadata.create_all(bind=database.engine)

fast_app = FastAPI(
    title="PDVix API"
)



fast_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)




fast_app.include_router(admin_router)
fast_app.include_router(app_router)

app = socketio.ASGIApp(sio, fast_app)





if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)