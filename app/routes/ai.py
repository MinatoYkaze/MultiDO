import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from ..auth import get_current_user

router = APIRouter(
    prefix='/ai',
    tags=['AI']
)

class AIChatRequest(BaseModel):
    message: str
    thread_id: Optional[str] = None

class AIChatResponse(BaseModel):
    reply: str
    thread_id: Optional[str] = None

class AIConversationResponse(BaseModel):
    thread_id: str
    title: Optional[str] = None
    last_message: Optional[str] = None
    reply: Optional[str] = None
    created_at: Optional[datetime] = None
    messages: List[Dict[str, Any]] = []

# Simple in-memory thread storage per process
_threads: Dict[str, Dict[str, Any]] = {}

def _get_groq_reply(prompt: str, thread_history: List[Dict[str, str]]) -> Optional[str]:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key == "your-groq-api-key":
        return None
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        
        messages = [
            {
                "role": "system",
                "content": (
                    "You are Pulse AI, the intelligent productivity assistant inside the MultiDO app. "
                    "You help users manage tasks, organize workspaces, prioritize deadlines, and focus. "
                    "Keep answers crisp, actionable, and formatted in clean markdown."
                )
            }
        ]
        for m in thread_history[-6:]:
            messages.append({"role": m.get("role", "user"), "content": m.get("content", "")})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"[AI] Groq error: {e}")
        return None

@router.post('/chat', response_model=AIChatResponse)
def chat(
    req: AIChatRequest,
    current_user = Depends(get_current_user)
):
    thread_id = req.thread_id or str(uuid.uuid4())
    user_msg = req.message.strip()
    
    if thread_id not in _threads:
        _threads[thread_id] = {
            "title": user_msg[:30] + ("..." if len(user_msg) > 30 else ""),
            "created_at": datetime.now(timezone.utc),
            "messages": []
        }
    
    thread_data = _threads[thread_id]
    history = thread_data["messages"]
    
    # Try Groq API first
    reply = _get_groq_reply(user_msg, history)
    if not reply:
        # Fallback intelligent productivity response
        reply = (
            f"I received your message: \"{user_msg}\". "
            "I'm ready to help you plan your tasks, maintain streaks, and focus with Pomodoro timers. "
            "(Configure GROQ_API_KEY in your .env to enable full AI completions)."
        )
    
    history.append({"role": "user", "content": user_msg})
    history.append({"role": "assistant", "content": reply})
    thread_data["last_message"] = user_msg
    thread_data["reply"] = reply

    return AIChatResponse(reply=reply, thread_id=thread_id)

@router.post('/conversation', response_model=AIConversationResponse)
def create_conversation(
    current_user = Depends(get_current_user)
):
    thread_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    _threads[thread_id] = {
        "title": "New Conversation",
        "created_at": now,
        "messages": []
    }
    return AIConversationResponse(
        thread_id=thread_id,
        title="New Conversation",
        created_at=now,
        messages=[]
    )

@router.get('/conversation', response_model=List[AIConversationResponse])
def get_conversations(
    current_user = Depends(get_current_user)
):
    result = []
    for tid, data in _threads.items():
        result.append(AIConversationResponse(
            thread_id=tid,
            title=data.get("title"),
            last_message=data.get("last_message"),
            reply=data.get("reply"),
            created_at=data.get("created_at"),
            messages=data.get("messages", [])
        ))
    return result
