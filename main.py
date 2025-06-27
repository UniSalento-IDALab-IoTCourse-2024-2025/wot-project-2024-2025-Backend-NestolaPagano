import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import auth, sessions, behavior, report

app = FastAPI(title="Driving App Server")
app.include_router(auth.router)
app.include_router(sessions.router)
app.include_router(behavior.router)
app.include_router(report.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)