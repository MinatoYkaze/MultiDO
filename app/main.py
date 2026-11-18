import os
from typing import List
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv

from . import schemas, database, models, auth
from .routes import tasks, groups, ai

load_dotenv()

from sqlalchemy import text

models.Base.metadata.create_all(bind=database.engine)

try:
    with database.engine.connect() as conn:
        conn.execute(text('ALTER TABLE "Tasks" ADD COLUMN IF NOT EXISTS priority VARCHAR DEFAULT \'medium\';'))
        conn.execute(text('ALTER TABLE "Tasks" ADD COLUMN IF NOT EXISTS due_date TIMESTAMPTZ;'))
        conn.execute(text('ALTER TABLE "group_tasks" ADD COLUMN IF NOT EXISTS priority VARCHAR DEFAULT \'medium\';'))
        conn.execute(text('ALTER TABLE "group_tasks" ADD COLUMN IF NOT EXISTS due_date TIMESTAMPTZ;'))
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS "group_subtasks" (
                id BIGSERIAL PRIMARY KEY,
                group_task_id BIGINT NOT NULL REFERENCES group_tasks(id) ON DELETE CASCADE,
                title VARCHAR NOT NULL,
                completed BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ DEFAULT now()
            );
        '''))
        conn.commit()
except Exception as e:
    print(f"[DB] Migration notice: {e}")

app = FastAPI(title="MultiDO Task API")

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
app.include_router(ai.router)

@app.get("/")
def root():
    return {"message": "Welcome to taskapi"}
