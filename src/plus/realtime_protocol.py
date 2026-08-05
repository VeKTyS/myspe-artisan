#
# realtime_protocol.py
#
# Protocole d'abonnement temps réel à ZABAWA.plus (Supabase Realtime).
#
# Volontairement sans Qt : le contrat avec le serveur doit rester vérifiable
# sans interface ni socket. Le transport vit dans plus/realtime.py.
#
# POURQUOI
# --------
# Le poste ne rafraîchissait son stock qu'à l'ouverture des Propriétés : un
# achat, un transfert ou une torréfaction faite ailleurs restait invisible tant
# que l'opérateur ne rouvrait pas le dialogue. Un rafraîchissement périodique
# corrige la dérive mais pas la latence.
#
# Supabase publie déjà `transactions`, `beans`, `stores` et `blends` dans la
# publication `supabase_realtime` (migration 20260520010000) — c'est ce à quoi
# l'application web s'abonne. Le poste s'y branche de la même façon.
#
# PROTOCOLE
# ---------
# Realtime v1 parle Phoenix Channels sur WebSocket :
#   1. connexion à wss://<projet>.supabase.co/realtime/v1/websocket?apikey=…&vsn=1.0.0
#   2. `phx_join` sur un topic, avec la liste des tables écoutées ;
#   3. `heartbeat` régulier, sinon le serveur ferme la connexion ;
#   4. réception d'événements `postgres_changes`.
#
# QWebSocket (fourni avec PyQt6) évite toute dépendance supplémentaire et vit
# dans la boucle d'événements Qt : pas de thread à gérer.
#
# Le temps réel ne remplace pas le rafraîchissement périodique : un WebSocket
# peut mourir silencieusement (proxy, veille, coupure Wi-Fi). Les deux se
# complètent — l'un donne la réactivité, l'autre la garantie.

import json
import logging
from typing import Any, Final
from urllib.parse import urlparse

_log: Final[logging.Logger] = logging.getLogger(__name__)

# Tables dont un changement peut modifier ce que le poste affiche : mouvements
# de stock, fiches grain, magasins et mélanges.
WATCHED_TABLES: Final[tuple[str, ...]] = ('transactions', 'beans', 'stores', 'blends')

# Phoenix ferme la connexion sans heartbeat ; on reste sous la minute.
HEARTBEAT_MS: Final[int] = 25_000

# Reprise après coupure. Plafonnée : un serveur indisponible ne doit pas être
# martelé, mais la reconnexion doit rester rapide sur une micro-coupure.
RECONNECT_DELAYS_MS: Final[tuple[int, ...]] = (1_000, 2_000, 5_000, 10_000, 30_000, 60_000)

# Les changements arrivent souvent par rafales (un import en crée des centaines).
# On attend un court instant avant de rafraîchir, pour ne le faire qu'une fois.
COALESCE_MS: Final[int] = 800


def realtime_url(api_base_url: str, anon_key: str) -> str | None:
    """URL du WebSocket Realtime, dérivée de l'URL de l'API.

    'https://xyz.supabase.co/functions/v1/artisan-api/v1'
      -> 'wss://xyz.supabase.co/realtime/v1/websocket?apikey=…&vsn=1.0.0'

    Renvoie None si l'URL de l'API n'est pas configurée : sans elle, le poste
    n'est de toute façon connecté à rien.
    """
    if not api_base_url or not anon_key:
        return None
    parsed = urlparse(api_base_url)
    if not parsed.scheme or not parsed.netloc:
        return None
    scheme = 'wss' if parsed.scheme == 'https' else 'ws'
    return (f'{scheme}://{parsed.netloc}/realtime/v1/websocket'
            f'?apikey={anon_key}&vsn=1.0.0')


def join_payload(tables: tuple[str, ...], ref: int) -> dict[str, Any]:
    """Message `phx_join` demandant les changements des tables écoutées.

    Un seul topic pour toutes les tables : autant de canaux que de tables
    multiplierait les connexions sans rien apporter, le poste rafraîchissant de
    toute façon l'ensemble de son référentiel.
    """
    return {
        'topic': 'realtime:public',
        'event': 'phx_join',
        'payload': {
            'config': {
                'postgres_changes': [
                    {'event': '*', 'schema': 'public', 'table': t} for t in tables
                ],
            },
        },
        'ref': str(ref),
    }


def heartbeat_payload(ref: int) -> dict[str, Any]:
    return {'topic': 'phoenix', 'event': 'heartbeat', 'payload': {}, 'ref': str(ref)}


def changed_table(raw: str) -> str | None:
    """Nom de la table modifiée si le message en est un, sinon None.

    Les messages de service (réponses de join, heartbeats, présence) ne doivent
    pas déclencher de rafraîchissement.
    """
    try:
        msg = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(msg, dict) or msg.get('event') != 'postgres_changes':
        return None
    payload = msg.get('payload')
    if not isinstance(payload, dict):
        return None
    data = payload.get('data')
    if not isinstance(data, dict):
        return None
    table = data.get('table')
    return table if isinstance(table, str) and table else None


