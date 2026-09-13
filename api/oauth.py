"""
Comptes externes : liaison et connexion avec Discord (Microsoft / Minecraft à venir).

Aucune création de compte depuis un fournisseur : l'utilisateur crée d'abord un compte Tetrago, lie son compte externe
depuis son profil, puis peut s'en servir pour se connecter. Un compte externe n'est lié qu'à un seul compte Tetrago,
et un compte Tetrago n'a qu'un compte par fournisseur. Les jetons des fournisseurs ne sont jamais conservés.

Configuration (config.json) : oauth2.discord.client_id, client_secret, redirect_uri (page /auth/discord/callback du site).
Variables d'environnement prioritaires (tests) : DISCORD_OAUTH_CLIENT_ID, DISCORD_OAUTH_CLIENT_SECRET,
DISCORD_OAUTH_REDIRECT_URI, DISCORD_API_BASE_URL.
"""
import datetime as dt
import os
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException
from sqlmodel import Session, select

from . import crud, models, schemas, utils

STATE_LIFETIME = dt.timedelta(minutes=10)
MODES = ("login", "link")


#region Fournisseurs

def _discord_settings():
    conf = (utils.OAUTH2 or {}).get("discord") or {}
    return {
        "client_id": os.environ.get("DISCORD_OAUTH_CLIENT_ID") or conf.get("client_id"),
        "client_secret": os.environ.get("DISCORD_OAUTH_CLIENT_SECRET") or conf.get("client_secret"),
        "redirect_uri": os.environ.get("DISCORD_OAUTH_REDIRECT_URI") or conf.get("redirect_uri"),
        "api_base": (os.environ.get("DISCORD_API_BASE_URL") or conf.get("api_base") or "https://discord.com/api").rstrip("/"),
        "authorize_url": "https://discord.com/oauth2/authorize",
        "scope": "identify",
    }

def _discord_error(response: httpx.Response) -> str:
    # Motif renvoyé par Discord ({"error": "invalid_grant", "error_description": "..."}), ou début de la réponse brute
    try:
        data = response.json()
        return " – ".join(str(part) for part in (data.get("error"), data.get("error_description") or data.get("message")) if part)
    except ValueError:
        return response.text[:200]

def _discord_identity(settings: dict, code: str):
    # Discord peut rejeter les requêtes sans User-Agent identifiable
    headers = {"User-Agent": "ShardAPI (https://tetrago.fr, 2.0)"}
    try:
        with httpx.Client(timeout=10, headers=headers) as client:
            token = client.post(f"{settings['api_base']}/oauth2/token", data={
                "client_id": str(settings["client_id"]),
                "client_secret": str(settings["client_secret"]).strip(),
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": str(settings["redirect_uri"]).strip(),
            })
            if token.status_code != 200:
                reason = _discord_error(token)
                print(f"OAuth Discord : échange du code refusé ({token.status_code}) : {reason}")
                raise HTTPException(status_code=400, detail=f"Discord a refusé l'autorisation ({reason or token.status_code}) : recommencez la connexion")
            me = client.get(f"{settings['api_base']}/users/@me", headers={"Authorization": f"Bearer {token.json().get('access_token')}"})
            if me.status_code != 200:
                reason = _discord_error(me)
                print(f"OAuth Discord : lecture du profil refusée ({me.status_code}) : {reason}")
                raise HTTPException(status_code=400, detail=f"Impossible de lire votre profil Discord ({reason or me.status_code}) : recommencez la connexion")
            data = me.json()
    except httpx.HTTPError as error:
        print(f"OAuth Discord : Discord injoignable : {error}")
        raise HTTPException(status_code=502, detail="Discord est momentanément injoignable : réessayez dans un instant")

    avatar = f"https://cdn.discordapp.com/avatars/{data['id']}/{data['avatar']}.png" if data.get("avatar") else None
    return {"uid": str(data["id"]), "username": data.get("global_name") or data.get("username"), "avatar_url": avatar}

# fournisseur -> libellé, réglages, lecture de l'identité à partir du code d'autorisation
PROVIDERS = {
    "discord": {"label": "Discord", "settings": _discord_settings, "identity": _discord_identity},
}

def _is_configured(settings: dict) -> bool:
    values = [settings.get(key) for key in ("client_id", "client_secret", "redirect_uri")]
    return all(values) and not any(str(value).startswith("your_") for value in values)

def _provider(provider: str):
    if provider not in PROVIDERS:
        raise HTTPException(status_code=404, detail="Fournisseur de connexion inconnu")
    config = PROVIDERS[provider]
    settings = config["settings"]()
    if not _is_configured(settings):
        raise HTTPException(status_code=503, detail=f"La connexion avec {config['label']} n'est pas encore configurée sur ce serveur")
    return config, settings

def providers_status():
    return [
        {"provider": key, "label": config["label"], "enabled": _is_configured(config["settings"]())}
        for key, config in PROVIDERS.items()
    ]

#endregion
#region Comptes liés

def _platform_link(db: Session, provider: str, uid: str):
    statement = select(models.UserPlatforms).where(models.UserPlatforms.platform == provider, models.UserPlatforms.uid == uid)
    return db.exec(statement).first()

def _user_link(db: Session, userID: int, provider: str):
    statement = select(models.UserPlatforms).where(models.UserPlatforms.user_id == userID, models.UserPlatforms.platform == provider)
    return db.exec(statement).first()

def platform_infos(link: models.UserPlatforms):
    return {"platform": link.platform, "uid": link.uid, "username": link.username, "avatar_url": link.avatar_url, "linked_at": link.linked_at}

def list_platforms(db: Session, user: schemas.Users):
    statement = select(models.UserPlatforms).where(models.UserPlatforms.user_id == user.id)
    return [platform_infos(link) for link in db.exec(statement).all() if link.platform in PROVIDERS]

def unlink_platform(db: Session, user: schemas.Users, provider: str):
    link = _user_link(db, user.id, provider)
    if not link:
        raise HTTPException(status_code=404, detail="Aucun compte de ce fournisseur n'est lié à votre compte")
    db.delete(link)
    db.commit()
    return {"text": f"Votre compte {PROVIDERS.get(provider, {}).get('label', provider)} a été délié"}

#endregion
#region Autorisation

def start_authorization(db: Session, provider: str, mode: str, user: schemas.Users | None = None):
    config, settings = _provider(provider)
    if mode not in MODES:
        raise HTTPException(status_code=400, detail="Mode d'autorisation inconnu")

    now = dt.datetime.now()
    for expired in db.exec(select(models.OAuthStates).where(models.OAuthStates.expires_at < now)).all():
        db.delete(expired)

    state = secrets.token_urlsafe(32)
    db.add(models.OAuthStates(state=state, provider=provider, mode=mode, user_id=user.id if user else None, expires_at=now + STATE_LIFETIME))
    db.commit()

    params = {
        "client_id": settings["client_id"],
        "redirect_uri": settings["redirect_uri"],
        "response_type": "code",
        "scope": settings["scope"],
        "state": state,
        "prompt": "none",
    }
    return {"url": f"{settings['authorize_url']}?{urlencode(params)}", "mode": mode, "label": config["label"]}

def complete_authorization(db: Session, provider: str, code: str, state: str):
    config, settings = _provider(provider)
    label = config["label"]

    # State à usage unique : supprimé avant tout appel au fournisseur
    db_state = db.exec(select(models.OAuthStates).where(models.OAuthStates.state == state, models.OAuthStates.provider == provider)).first()
    if not db_state:
        raise HTTPException(status_code=400, detail="Ce lien de connexion n'est plus valide : recommencez depuis le site")
    mode, user_id, expired = db_state.mode, db_state.user_id, db_state.expires_at < dt.datetime.now()
    db.delete(db_state)
    db.commit()
    if expired:
        raise HTTPException(status_code=400, detail="Ce lien de connexion a expiré : recommencez depuis le site")

    identity = config["identity"](settings, code)
    link = _platform_link(db, provider, identity["uid"])

    if mode == "link":
        user = crud.get_user_by_id(db, user_id) if user_id else None
        if not user:
            raise HTTPException(status_code=404, detail="Le compte à lier n'existe plus")
        if link and link.user_id != user.id:
            raise HTTPException(status_code=400, detail=f"Ce compte {label} est déjà lié à un autre compte Tetrago")
        existing = _user_link(db, user.id, provider)
        if existing and existing.uid != identity["uid"]:
            raise HTTPException(status_code=400, detail=f"Votre compte est déjà lié à un autre compte {label} : déliez-le d'abord")
        link = link or models.UserPlatforms(user_id=user.id, platform=provider, uid=identity["uid"], linked_at=dt.datetime.now())
    else:
        if not link:
            raise HTTPException(status_code=404, detail=f"Aucun compte Tetrago n'est lié à ce compte {label}. Créez un compte sur le site, puis liez {label} depuis votre profil.")
        user = crud.get_user_by_id(db, link.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Le compte Tetrago lié n'existe plus")
        if user.is_disabled:
            raise HTTPException(status_code=403, detail="Ce compte Tetrago est désactivé")

    # Pseudo et avatar tenus à jour à chaque passage
    link.username = identity["username"]
    link.avatar_url = identity["avatar_url"]
    db.add(link)
    db.commit()
    db.refresh(link)

    if mode == "link":
        return {"mode": "link", "text": f"Votre compte {label} est lié", "platform": platform_infos(link)}

    session = crud.create_active_session(db, user.username)
    return {"mode": "login", "access_token": session.access_token, "token_type": "bearer", "user": crud.build_user_read(user)}

#endregion
