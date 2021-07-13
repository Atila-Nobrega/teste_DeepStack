from imutils.video import VideoStream
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.status import HTTP_201_CREATED
import threading
import cv2
from starlette.responses import StreamingResponse
from deepstack_sdk import ServerConfig, Detection


cap = cv2.VideoCapture("http://187.19.204.20/mjpg/video.mjpg")
#rtsp://wowzaec2demo.streamlock.net/vod/mp4:BigBuckBunny_115k.mov


config = ServerConfig("http://localhost:80")
detection = Detection(config)

ativado = False


# Iniciliza o frame de exibição
saidaFrame = None

# Iniciliza uma trava de segurança do processamento no servidor
lock = threading.Lock()

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

vs = VideoStream(src="http://187.19.204.20/mjpg/video.mjpg").start()
#http://200.122.223.34:8001/mjpg/video.mjpg

@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse("pagina.html", context={"request": request})


def object_detection():
	
	global vs, saidaFrame, lock, ativado


	while True:
		
		_, frame = cap.read()
		#Mudar para True/False para Ativar/Desativar (Serve para teste de frames)
		if(ativado):
			response = detection.detectObject(frame, min_confidence=0.4)
			for obj in response:
				cv2.rectangle(frame, (obj.x_min, obj.y_min), (obj.x_max, obj.y_max), (0,255,0), 1)
				cv2.putText(frame, obj.label, (obj.x_max +10, obj.y_max), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 2)

		
		# Determina o frame de exibição de forma que todos os clientes estejam sincronizados com a saida obtida
		with lock:
			saidaFrame = frame.copy()
			

def generate():
	global saidaFrame, lock

	while True:

		with lock:
			if saidaFrame is None:
				continue
		
			# Codificar o frame de exibição em JPG
			(flag, encodedImage) = cv2.imencode(".jpg", saidaFrame)
			
			# Caso o frame não tenha sido codificado
			if not flag:
				continue

			# Gerar em formato binário a imagem a ser reproduzida na página
			
		yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + bytearray(encodedImage) + b'\r\n')




@app.get("/video_feed")
async def video_feed():
	return StreamingResponse(generate(), media_type="multipart/x-mixed-replace;boundary=frame")



@app.get("/ativar")
async def ativar_deteccao():
	print("Clicou o")

	global ativado

	if ativado == False:
		ativado = True
	else:
		ativado = False

t = threading.Thread(target=object_detection)
t.daemon = True
t.start()