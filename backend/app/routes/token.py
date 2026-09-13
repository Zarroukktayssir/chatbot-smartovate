# routes/token.py — Endpoint Direct Line Token (US 3.2)
#
# Rôle : fournir au frontend Web Chat un token Direct Line sécurisé.
#
# Deux modes :
# 1. DIRECT_LINE_SECRET configuré → échange le secret contre un token éphémère
#    via l'API Microsoft Direct Line (token valide 30 min, non réutilisable).
# 2. DIRECT_LINE_SECRET vide (développement local) → retourne un token simulé
#    pour permettre au frontend de fonctionner en mode REST API direct.
#
# Le secret ne transite jamais vers le frontend — seul le token éphémère est exposé.

import httpx
from fastapi import APIRouter, HTTPException
from app.config import get_settings

router = APIRouter()
settings = get_settings()

# URL de l'API Direct Line Microsoft
_DIRECT_LINE_TOKEN_URL = "https://directline.botframework.com/v3/directline/tokens/generate"


@router.get(
    "/token",
    summary="Obtenir un token Direct Line pour le Web Chat",
    description=(
        "Retourne un token Direct Line éphémère pour initialiser la connexion Web Chat. "
        "Si DIRECT_LINE_SECRET est configuré, échange le secret contre un vrai token Azure. "
        "Sinon, retourne un token simulé pour le développement local en mode REST API."
    ),
)
async def get_directline_token():
    """
    Génère ou simule un token Direct Line (US 3.2 critère 4).

    Le frontend appelle cet endpoint au démarrage pour obtenir le token
    nécessaire à l'initialisation du composant Web Chat.
    Le secret Direct Line n'est jamais exposé côté client.
    """
    secret = settings.direct_line_secret

    # ── Mode production : échange secret → token éphémère ────────────────
    if secret:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    _DIRECT_LINE_TOKEN_URL,
                    headers={
                        "Authorization": f"Bearer {secret}",
                        "Content-Type": "application/json",
                    },
                    timeout=10.0,
                )
            if response.status_code != 200:
                raise HTTPException(
                    status_code=502,
                    detail="Impossible d'obtenir un token Direct Line depuis Azure.",
                )
            data = response.json()
            return {
                "token": data.get("token"),
                "expires_in": data.get("expires_in", 1800),
                "mode": "directline",
            }
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=502,
                detail=f"Erreur de connexion à Direct Line API. ({type(e).__name__})",
            )

    # ── Mode développement local : token simulé ───────────────────────────
    # Le frontend détecte ce mode et appelle directement /api/chat/message
    # au lieu d'utiliser le protocole Direct Line.
    return {
        "token": None,
        "expires_in": None,
        "mode": "rest_api",   # Le frontend utilisera l'API REST FastAPI directement
    }
