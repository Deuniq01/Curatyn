from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import application_routes, auth_routes, cv_routes, jd_routes, send_routes

app = FastAPI(title="Curatyn API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router)
app.include_router(cv_routes.router)
app.include_router(jd_routes.router)
app.include_router(application_routes.router)
app.include_router(send_routes.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
