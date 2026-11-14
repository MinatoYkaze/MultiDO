from datetime import timedelta, datetime
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Body, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from .database import SessionLocal, get_db
from .models import Users
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from . import schemas, database, models
from app.Oauth import oauth
import os

SECRET_KEY = os.getenv("SECRET_KEY", "fallback-secret-key-change-in-prod")
ALGORITHM = os.getenv("ALGORITHM", "HS256")

router = APIRouter(
    prefix='/auth',
    tags=['auth']
)

security = HTTPBearer(auto_error=False)

def access_token(username: str, id: int, expires_delta: timedelta):
    encode = {"sub": username, "id": id, "type": "access"}
    expires = datetime.utcnow() + expires_delta
    encode.update({"exp": expires})
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(username: str, id: int, expires_delta: timedelta):
    encode = {"sub": username, "id": id, "type": "refresh"}
    expires = datetime.utcnow() + expires_delta
    encode.update({"exp": expires})
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(
    request: Request,
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(database.get_db),
):
    token = None
    # 1. Bearer Header (Mobile app standard)
    if auth and auth.credentials:
        token = auth.credentials
    # 2. Check Authorization header manually
    elif "Authorization" in request.headers:
        auth_hdr = request.headers.get("Authorization", "")
        if auth_hdr.lower().startswith("bearer "):
            token = auth_hdr[7:].strip()
        else:
            token = auth_hdr.strip()
    # 3. Check cookies (Web browser fallback)
    elif "access_token" in request.cookies:
        token = request.cookies.get("access_token")
        if token and token.startswith("Bearer "):
            token = token.split(" ")[1]

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")

    # Developer bypass token support
    if token in ("dev_secret_bypass_token", "DEV2026"):
        dev_user = db.query(models.Users).filter(models.Users.email == "developer@multido.local").first()
        if not dev_user:
            dev_user = models.Users(
                google_id="dev_bypass_001",
                username="Developer Mode",
                email="developer@multido.local"
            )
            db.add(dev_user)
            db.commit()
            db.refresh(dev_user)
        return {'username': dev_user.username, 'id': dev_user.id}

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get('sub')
        user_id: int = payload.get('id')
        token_type = payload.get('type')
        if token_type != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")
        if username is None or user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate user")
        return {'username': username, 'id': user_id}
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate user")

@router.get("/google/login")
async def google_login(request: Request):
    redirect_uri = request.url_for("google_callback")
    return await oauth.google.authorize_redirect(
        request,
        redirect_uri
    )

@router.get("/google/callback")
async def google_callback(request: Request, response: Response, db: Session = Depends(database.get_db)):
    token = await oauth.google.authorize_access_token(request)
    user_info = token.get("userinfo") or {}
    google_id = str(user_info.get("sub", ""))
    email = user_info.get("email", "")
    name = user_info.get("name", email.split("@")[0] if email else "User")

    user = db.query(models.Users).filter(models.Users.google_id == google_id).first()
    if not user:
        user = models.Users(
            google_id=google_id,
            username=name,
            email=email
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    acc_token = access_token(
        username=user.username,
        id=user.id,
        expires_delta=timedelta(days=7)
    )
    refresh = create_refresh_token(
        username=user.username,
        id=user.id,
        expires_delta=timedelta(days=30)
    )

    # Custom scheme redirect for mobile app (flutter_web_auth_2)
    mobile_redirect = f"obsidiantodo://auth?access_token={acc_token}&refresh_token={refresh}"

    res = RedirectResponse(url=mobile_redirect)
    res.set_cookie(
        key="access_token",
        value=acc_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=7 * 24 * 3600
    )
    res.set_cookie(
        key="refresh_token",
        value=refresh,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=30 * 24 * 3600
    )
    return res

@router.get("/me", response_model=schemas.UserPost)
def get_login(current_user=Depends(get_current_user), db: Session = Depends(database.get_db)):
    user = db.query(models.Users).filter(models.Users.id == current_user["id"]).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authorized")
    return schemas.UserPost(
        id=user.id,
        email=user.email,
        name=user.username,
        username=user.username,
    )

@router.post("/refresh")
async def refresh_token(request: Request, response: Response, body: Optional[dict] = Body(default=None)):
    refresh = None
    if body and isinstance(body, dict):
        refresh = body.get("refresh_token")
    if not refresh and "Authorization" in request.headers:
        auth_hdr = request.headers.get("Authorization", "")
        if auth_hdr.lower().startswith("bearer "):
            refresh = auth_hdr[7:].strip()
        else:
            refresh = auth_hdr.strip()
    if not refresh:
        refresh = request.cookies.get("refresh_token")

    if not refresh:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")

    try:
        payload = jwt.decode(refresh, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        user_id = payload.get("id")
        token_type = payload.get("type")
        if token_type != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
        if username is None or user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate user")

        new_access = access_token(username=username, id=user_id, expires_delta=timedelta(days=7))
        new_refresh = create_refresh_token(username=username, id=user_id, expires_delta=timedelta(days=30))

        response.set_cookie(
            key="access_token",
            value=new_access,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=7 * 24 * 3600
        )
        response.set_cookie(
            key="refresh_token",
            value=new_refresh,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=30 * 24 * 3600
        )
        return {
            "access_token": new_access,
            "refresh_token": new_refresh,
            "token_type": "bearer",
            "message": "Access token refreshed successfully"
        }
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate user")

@router.post("/Logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"message": "Logged out successfully"}
