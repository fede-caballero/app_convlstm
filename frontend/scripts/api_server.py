from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import json
import asyncio
from pathlib import Path
import logging
from typing import List, Dict
from datetime import datetime
import uvicorn

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Radar Prediction API", version="1.0.0")

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar dominios específicos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lista de conexiones WebSocket activas
active_connections: List[WebSocket] = []

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Nueva conexión WebSocket. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"Conexión WebSocket cerrada. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Envía mensaje a todas las conexiones activas"""
        if self.active_connections:
            message_str = json.dumps(message)
            for connection in self.active_connections.copy():
                try:
                    await connection.send_text(message_str)
                except:
                    # Remover conexiones cerradas
                    self.active_connections.remove(connection)

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Mantener conexión activa
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/")
async def root():
    return {"message": "Radar Prediction API", "status": "running"}

@app.get("/status")
async def get_status():
    """Obtiene el estado actual del sistema"""
    # Aquí podrías leer el estado desde archivos o base de datos
    return {
        "model_status": "ready",
        "buffer_size": 12,
        "active_connections": len(manager.active_connections),
        "last_update": datetime.now().isoformat()
    }

@app.get("/predictions")
async def get_predictions():
    """Obtiene las predicciones más recientes"""
    predictions_dir = Path("/data/radar/predictions")
    
    # Buscar archivos de resultados JSON
    result_files = list(predictions_dir.glob("result_*.json"))
    result_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    
    predictions = []
    for result_file in result_files[:10]:  # Últimas 10 predicciones
        try:
            with open(result_file, 'r') as f:
                prediction_data = json.load(f)
                predictions.append(prediction_data)
        except Exception as e:
            logger.error(f"Error leyendo {result_file}: {e}")
    
    return {"predictions": predictions}

@app.get("/buffer")
async def get_buffer_status():
    """Obtiene el estado actual del buffer"""
    # En una implementación real, esto vendría del RadarProcessor
    # Por ahora, simulamos el estado
    return {
        "current_size": 8,
        "max_size": 12,
        "last_scan": datetime.now().isoformat(),
        "ready_for_prediction": False
    }

# Función para monitorear cambios y notificar via WebSocket
async def monitor_predictions():
    """Monitorea nuevas predicciones y notifica a los clientes"""
    predictions_dir = Path("/data/radar/predictions")
    last_check = datetime.now()
    
    while True:
        try:
            # Buscar nuevos archivos de resultados
            result_files = list(predictions_dir.glob("result_*.json"))
            
            for result_file in result_files:
                file_time = datetime.fromtimestamp(result_file.stat().st_mtime)
                if file_time > last_check:
                    # Nuevo archivo encontrado
                    try:
                        with open(result_file, 'r') as f:
                            prediction_data = json.load(f)
                        
                        # Notificar a todos los clientes conectados
                        await manager.broadcast({
                            "type": "new_prediction",
                            "data": prediction_data
                        })
                        
                        logger.info(f"Nueva predicción notificada: {result_file}")
                        
                    except Exception as e:
                        logger.error(f"Error procesando {result_file}: {e}")
            
            last_check = datetime.now()
            await asyncio.sleep(5)  # Verificar cada 5 segundos
            
        except Exception as e:
            logger.error(f"Error en monitor_predictions: {e}")
            await asyncio.sleep(10)

@app.on_event("startup")
async def startup_event():
    """Inicia tareas en background al arrancar la API"""
    # Iniciar monitoreo de predicciones
    asyncio.create_task(monitor_predictions())
    logger.info("API iniciada. Monitoreo de predicciones activo.")

if __name__ == "__main__":
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
