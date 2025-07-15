import socketio
import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.templating import Jinja2Templates

from src.api.admin.events.admin_namespace import AdminNamespace
from src.socketio_instance import sio

from src.api.admin import router as admin_router
from src.api.app import router as app_router


#Base.metadata.create_all(bind=database.engine)

# Registra namespaces ANTES de criar o ASGIApp
sio.register_namespace(AdminNamespace('/admin'))

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


templates = Jinja2Templates(directory="src/templates")

fast_app.include_router(admin_router)
fast_app.include_router(app_router)

app = socketio.ASGIApp(sio, fast_app)





if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)