# 📚 Biblioteca Personal - Backend (FastAPI)

API REST desarrollada con **FastAPI** para la gestión de una biblioteca personal. Permite administrar libros mediante operaciones CRUD, con una arquitectura clara y escalable.

---

## 🚀 Tecnologías
- Python 3
- FastAPI
- Uvicorn
- Pydantic

---

## 🧠 Arquitectura

El proyecto sigue una estructura modular para facilitar mantenimiento y escalabilidad:
app/
│── main.py
│── models/
│── schemas/
│── routers/
│── services/
│── database/


---

## ✨ Funcionalidades

- 📖 Listar libros
- ➕ Crear nuevos libros
- ✏️ Actualizar información
- ❌ Eliminar libros
- 🔍 Búsqueda por criterios

---

## 📌 Endpoints

| Método | Endpoint       | Descripción            |
|--------|--------------|------------------------|
| GET    | /libros      | Obtener todos los libros |
| GET    | /libros/{id} | Obtener libro por ID     |
| POST   | /libros      | Crear nuevo libro        |
| PUT    | /libros/{id} | Actualizar libro         |
| DELETE | /libros/{id} | Eliminar libro           |

---

## 📥 Ejemplo de Request

### Crear libro

```json
{
  "titulo": "Clean Code",
  "autor": "Robert C. Martin",
  "anio": 2008
}
git clone https://github.com/luisangel566/biblioteca-fastapi.git
cd biblioteca-fastapi

# Crear entorno virtual
python -m venv venv

# Activar entorno
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar servidor
uvicorn app.main:app --reload

📡 Documentación automática

FastAPI genera documentación interactiva:

Swagger UI: http://127.0.0.1:8000/docs
Redoc: http://127.0.0.1:8000/redoc

🔗 Frontend

Este backend se integra con el frontend en React:

👉 https://github.com/luisangel566/biblio-react
