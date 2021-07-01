from fastapi import FastAPI, Depends
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from routes.v1 import app_v1
from starlette.requests import Request
from utils.security import check_jwt_token, create_jwt_token
from utils.db_functions import db_realizar_login
from utils.db_object import db, mongo_client, minio_client
from utils.const import REDIS_URL
import utils.redis_object as re
import aioredis
import pickle
from datetime import datetime
from models.usuario import Usuario

app = FastAPI(title="UFCSmartCampus", description="API da SmartCampus", version="1.0.0")

#adiciona os templates HTML e os statics CSS e JS para serem reconhecidos.
#Static é montado no app, já o template precisa ser definido no Endpoint Http para funcionar.
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

#Para utilizar troca de informações entre origens diferentes, ex: FastAPI e REACT, é necessário colocar a origem do outro local.
origins = [
    #adicionar aqui as origens do React.
    "http://localhost:3000",
    "localhost:3000"
]

#Aqui é onde é definido que tipo de informações podem ser trocadas entre as origens e esse backend. (É para estar definido tudo).
app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"]
)

app.include_router(app_v1, prefix="/v1", dependencies= [Depends(check_jwt_token)])

@app.on_event("startup")
async def connect_db():
    await db.connect()
    if not minio_client.bucket_exists("imagens"):
        minio_client.make_bucket("imagens")
    re.redis = await aioredis.create_redis_pool(REDIS_URL)

@app.on_event("shutdown")
async def disconnect_db():
    await db.disconnect()
    await mongo_client.close()
    re.redis.close()
    await re.redis.wait_closed()

@app.post("/token")
async def login_for_acess_token(form_data: OAuth2PasswordRequestForm = Depends()):
    redis_key = f"token:{form_data.username},{form_data.password}"
    user = await re.redis.get(redis_key)

    if not user:
        # caso não tenha salvo no redis
        usuario = await db_realizar_login(form_data.username, form_data.password)
        usuario_obj = Usuario(**usuario)

        # salva objeto usuario no redis
        await re.redis.set(redis_key, pickle.dumps(usuario_obj))
    else:
        # caso já tenha salvo no redis
        usuario_obj = pickle.loads(user)

    jwt_token = create_jwt_token(usuario_obj)
    return {"access_token": jwt_token, "token_type": "bearer"}

#Exemplo de página HTML funcionando no FastAPI
@app.get("/pagina", response_class=HTMLResponse)
async def videopage(request: Request):
    return templates.TemplateResponse("pagina.html", {"request": request})

#middleware teste! adiciona tempo de execução no header de resposta.
@app.middleware("http")
async def middleware(request: Request, call_next):
    start_time = datetime.utcnow()
    response = await call_next(request)
    #modify response
    execution_time = (datetime.utcnow()- start_time).microseconds
    response.headers["x-execution-time"] = str(execution_time)
    return response
