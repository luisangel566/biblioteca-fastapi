import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.libros import router as libros_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="API Biblioteca Personal",
    description=(
        "Backend REST construido con FastAPI y MySQL.\n\n"
        "Permite gestionar un catálogo personal de libros con operaciones:\n"
        "- **GET** /api/libros → Listar todos los libros\n"
        "- **POST** /api/libros → Crear un nuevo libro\n"
        "- **GET** /api/libros/{id} → Obtener un libro por id\n"
        "- **PUT** /api/libros/{id} → Actualizar un libro\n"
        "- **DELETE** /api/libros/{id} → Eliminar un libro"
    ),
    version="1.0.0",
)

ALLOWED_ORIGINS = [
    "http://localhost:4200",
    "http://localhost:5173",
    "http://localhost:5176",  # ← tu puerto actual de React
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(libros_router)
logger.info("✅ Router de libros registrado correctamente.")

@app.get("/", tags=["Health"], summary="Verificar estado de la API")
def health_check():
    return {
        "status" : "ok",
        "mensaje": "✅ API Biblioteca Personal funcionando correctamente 📚",
        "docs"   : "http://localhost:8080/docs",
        "version": "1.0.0",
    }