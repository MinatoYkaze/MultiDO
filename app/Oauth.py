from authlib.integrations.starlette_client import OAuth
import os

def _clean(val: str | None) -> str | None:
    return val.strip() if val else None

client_id = _clean(os.getenv("CLIENT_ID"))
client_secret = _clean(os.getenv("CLIENT_SECRET"))

oauth = OAuth()
oauth.register(
    name="google",
    client_id=client_id,
    client_secret=client_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile"
    },
)
