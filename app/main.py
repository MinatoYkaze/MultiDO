import os
from typing import List
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv

from . import schemas, database, models, auth
from .routes import tasks, groups

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware, 
    secret_key=os.getenv("SESSION_SECRET_KEY", "fallback-secret-key-change-in-prod")
)

app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(groups.router)

@app.get("/")
def root():
    return {"message": "Welcome to taskapi"}
