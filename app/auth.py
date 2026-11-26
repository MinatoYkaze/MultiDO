from datetime import timedelta, datetime
from typing import Annotated, Optional
from urllib.parse import quote
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Body, status
from fastapi.responses import RedirectResponse, HTMLResponse
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

def get_google_redirect_uri(request: Request) -> str:
    env_redirect = os.getenv("GOOGLE_REDIRECT_URI")
    if env_redirect and env_redirect.strip():
        return env_redirect.strip()
    url = str(request.url_for("google_callback"))
    if request.headers.get("x-forwarded-proto") == "https" or "onrender.com" in url:
        if url.startswith("http://"):
            url = "https://" + url[7:]
    return url

@router.get("/google/login")
async def google_login(request: Request):
    client_id = (os.getenv("CLIENT_ID") or "").strip()
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="CLIENT_ID environment variable is missing on Render. Please configure CLIENT_ID in your Render dashboard environment variables."
        )
    redirect_uri = get_google_redirect_uri(request)
    return await oauth.google.authorize_redirect(
        request,
        redirect_uri
    )

def _render_mobile_redirect_html(
    target_url: str,
    title: str = "Connecting to MultiDO...",
    subtitle: str = "Returning you to the MultiDO app...",
    button_text: str = "Open MultiDO App"
) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title}</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #0B0F19;
            color: #F8FAFC;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            margin: 0;
            padding: 24px;
            text-align: center;
        }}
        .card {{
            background: #141B2D;
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 20px;
            padding: 36px 24px;
            max-width: 400px;
            width: 100%;
            box-shadow: 0 12px 32px rgba(0, 0, 0, 0.6);
        }}
        h2 {{ margin: 0 0 12px; font-size: 22px; font-weight: 700; }}
        p {{ color: #94A3B8; font-size: 14px; margin: 0 0 24px; line-height: 1.5; }}
        .btn {{
            display: inline-block;
            background: linear-gradient(135deg, #6366F1, #8B5CF6);
            color: #FFFFFF !important;
            text-decoration: none;
            font-weight: 600;
            font-size: 16px;
            padding: 14px 32px;
            border-radius: 14px;
            box-shadow: 0 4px 16px rgba(99, 102, 241, 0.4);
            cursor: pointer;
        }}
        .spinner {{
            width: 40px;
            height: 40px;
            border: 3px solid rgba(99, 102, 241, 0.2);
            border-top-color: #6366F1;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin: 0 auto 20px;
        }}
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
    </style>
    <script>
        function launch() {{
            window.location.href = "{target_url}";
        }}
        launch();
        setTimeout(launch, 300);
    </script>
</head>
<body>
    <div class="card">
        <div class="spinner"></div>
        <h2>{title}</h2>
        <p>{subtitle}</p>
        <a class="btn" href="{target_url}" onclick="launch()">{button_text}</a>
    </div>
</body>
</html>"""

@router.get("/google/callback")
async def google_callback(request: Request, response: Response, db: Session = Depends(database.get_db)):
    code = request.query_params.get("code")
    error = request.query_params.get("error")
    error_desc = request.query_params.get("error_description", error)

    def _error_response(message: str):
        print(f"[Google Auth ERROR] {message}")
        mobile_redirect = f"obsidiantodo://auth?error={quote(message)}"
        html = _render_mobile_redirect_html(
            target_url=mobile_redirect,
            title="Authentication Error",
            subtitle=f"{message}<br><br>Tap below to return to the app:",
            button_text="Return to MultiDO"
        )
        return HTMLResponse(content=html, status_code=200)

    if error:
        return _error_response(f"Google sign-in error: {error_desc or error}")

    if not code:
        return _error_response("Missing authorization code from Google.")

    client_id = (os.getenv("CLIENT_ID") or "").strip()
    client_secret = (os.getenv("CLIENT_SECRET") or "").strip()

    if not client_id or not client_secret:
        return _error_response("CLIENT_ID or CLIENT_SECRET is not configured in Render environment variables.")

    redirect_uri = get_google_redirect_uri(request)
    user_info = None

    # Step 1: Attempt standard Authlib authorization (if session cookie is present)
    try:
        token = await oauth.google.authorize_access_token(request)
        if token:
            user_info = token.get("userinfo")
            if not user_info and "access_token" in token:
                async with httpx.AsyncClient() as client:
                    ui_resp = await client.get(
                        "https://www.googleapis.com/oauth2/v3/userinfo",
                        headers={"Authorization": f"Bearer {token['access_token']}"}
                    )
                    if ui_resp.status_code == 200:
                        user_info = ui_resp.json()
    except Exception as e:
        print(f"[Google Auth Notice] Authlib token exchange returned {type(e).__name__}: {e}. Falling back to direct exchange...")

    # Step 2: Fallback direct token exchange with Google (handles session loss / state mismatch)
    if not user_info:
        try:
            async with httpx.AsyncClient() as client:
                token_resp = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "code": code,
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "redirect_uri": redirect_uri,
                        "grant_type": "authorization_code",
                    },
                    headers={"Accept": "application/json"}
                )
                token_data = token_resp.json()
                if token_resp.status_code != 200:
                    err_detail = token_data.get("error_description") or token_data.get("error") or str(token_data)
                    return _error_response(f"Google token exchange failed ({token_resp.status_code}): {err_detail}. Please verify CLIENT_SECRET in Render dashboard.")

                access_tok = token_data.get("access_token")
                if access_tok:
                    ui_resp = await client.get(
                        "https://www.googleapis.com/oauth2/v3/userinfo",
                        headers={"Authorization": f"Bearer {access_tok}"}
                    )
                    if ui_resp.status_code == 200:
                        user_info = ui_resp.json()
                    else:
                        return _error_response(f"Failed to fetch user profile from Google: {ui_resp.text}")
                else:
                    return _error_response("No access token returned by Google.")
        except Exception as ex:
            return _error_response(f"Connection error exchanging Google token: {str(ex)}")

    if not user_info or not user_info.get("email"):
        return _error_response("Could not retrieve email profile from Google.")

    google_id = str(user_info.get("sub", ""))
    email = user_info.get("email", "").strip()
    name = user_info.get("name", email.split("@")[0] if email else "User")

    try:
        user = db.query(models.Users).filter(
            (models.Users.google_id == google_id) | (models.Users.email == email)
        ).first()

        if not user:
            user = models.Users(
                google_id=google_id,
                username=name,
                email=email
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            changed = False
            if not user.google_id or user.google_id != google_id:
                user.google_id = google_id
                changed = True
            if name and (not user.username or user.username == user.email):
                user.username = name
                changed = True
            if changed:
                db.commit()
                db.refresh(user)
    except Exception as db_err:
        db.rollback()
        return _error_response(f"Database error registering user: {str(db_err)}")

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

    html = _render_mobile_redirect_html(
        target_url=mobile_redirect,
        title="Welcome to MultiDO!",
        subtitle="Sign-in successful. Returning you to the app... If it does not open automatically, tap below:",
        button_text="Open MultiDO App"
    )
    res = HTMLResponse(content=html, status_code=200)
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

@router.post("/google/verify", response_model=schemas.TokenResponse)
async def google_verify(
    payload: schemas.GoogleTokenVerify,
    response: Response,
    db: Session = Depends(database.get_db)
):
    """
    Direct verification of Google tokens obtained natively from mobile GoogleSignIn SDK.
    Eliminates browser redirects and cookie dependency.
    """
    if not payload.id_token and not payload.access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="id_token or access_token is required"
        )

    user_info = None

    # Step 1: Verify Google ID token via Google's tokeninfo endpoint
    if payload.id_token:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(
                    f"https://oauth2.googleapis.com/tokeninfo?id_token={payload.id_token}"
                )
                if res.status_code == 200:
                    user_info = res.json()
        except Exception as e:
            print(f"[Google Verify] tokeninfo request failed: {e}")

    # Step 2: Fallback to access_token userinfo endpoint
    if not user_info and payload.access_token:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(
                    "https://www.googleapis.com/oauth2/v3/userinfo",
                    headers={"Authorization": f"Bearer {payload.access_token}"}
                )
                if res.status_code == 200:
                    user_info = res.json()
        except Exception as e:
            print(f"[Google Verify] userinfo request failed: {e}")

    if not user_info or not user_info.get("email"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google credentials or unable to retrieve email profile"
        )

    google_id = str(user_info.get("sub", ""))
    email = user_info.get("email", "").strip()
    name = user_info.get("name", email.split("@")[0] if email else "User")

    try:
        user = db.query(models.Users).filter(
            (models.Users.google_id == google_id) | (models.Users.email == email)
        ).first()

        if not user:
            user = models.Users(
                google_id=google_id,
                username=name,
                email=email
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            changed = False
            if not user.google_id or user.google_id != google_id:
                user.google_id = google_id
                changed = True
            if name and (not user.username or user.username == user.email):
                user.username = name
                changed = True
            if changed:
                db.commit()
                db.refresh(user)
    except Exception as db_err:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error registering user: {str(db_err)}"
        )

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

    response.set_cookie(
        key="access_token",
        value=acc_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=7 * 24 * 3600
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=30 * 24 * 3600
    )

    return {
        "access_token": acc_token,
        "refresh_token": refresh,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "name": user.username,
        }
    }

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
