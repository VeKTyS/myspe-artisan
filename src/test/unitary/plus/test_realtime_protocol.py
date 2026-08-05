"""Tests de plus.realtime — protocole d'abonnement temps réel.

Ce qui est testé ici, c'est le contrat avec Supabase Realtime : l'URL dérivée,
le message d'abonnement et la reconnaissance des événements. Le reste
(WebSocket, minuteries) appartient à Qt et se vérifie en conditions réelles.

Un faux positif sur changed_table() ferait rafraîchir le stock à chaque
battement de cœur ; un faux négatif rendrait le temps réel silencieux. Les deux
sont couverts.
"""

import json

from plus.realtime_protocol import (
    WATCHED_TABLES,
    changed_table,
    heartbeat_payload,
    join_payload,
    realtime_url,
)


def test_url_derivee_de_lapi() -> None:
    url = realtime_url('https://xyz.supabase.co/functions/v1/artisan-api/v1', 'anon-key')
    assert url == ('wss://xyz.supabase.co/realtime/v1/websocket?apikey=anon-key&vsn=1.0.0')


def test_url_en_clair_pour_un_serveur_local() -> None:
    url = realtime_url('http://localhost:54321/functions/v1/artisan-api/v1', 'anon')
    assert url is not None
    assert url.startswith('ws://localhost:54321/realtime/v1/websocket')


def test_url_absente_si_api_non_configuree() -> None:
    # sans URL d'API, le poste n'est connecté à rien : pas de temps réel non plus
    assert realtime_url('', 'anon') is None
    assert realtime_url('https://x.example', '') is None
    assert realtime_url('pas-une-url', 'anon') is None


def test_join_demande_toutes_les_tables_surveillees() -> None:
    payload = join_payload(WATCHED_TABLES, 1)
    assert payload['event'] == 'phx_join'
    changes = payload['payload']['config']['postgres_changes']
    assert [c['table'] for c in changes] == list(WATCHED_TABLES)
    assert all(c['event'] == '*' and c['schema'] == 'public' for c in changes)
    assert payload['ref'] == '1'


def test_les_tables_surveillees_couvrent_le_stock() -> None:
    # transactions porte les mouvements ; sans elle, aucun changement de stock
    # ne serait signalé
    assert 'transactions' in WATCHED_TABLES
    assert 'beans' in WATCHED_TABLES


def test_heartbeat_bien_forme() -> None:
    assert heartbeat_payload(7) == {
        'topic': 'phoenix', 'event': 'heartbeat', 'payload': {}, 'ref': '7'}


def test_changement_reconnu() -> None:
    raw = json.dumps({
        'event': 'postgres_changes',
        'payload': {'data': {'table': 'transactions', 'type': 'INSERT'}},
    })
    assert changed_table(raw) == 'transactions'


def test_messages_de_service_ignores() -> None:
    # une réponse de join ou un heartbeat ne doit pas déclencher de rafraîchissement
    assert changed_table(json.dumps({'event': 'phx_reply', 'payload': {'status': 'ok'}})) is None
    assert changed_table(json.dumps({'event': 'heartbeat', 'payload': {}})) is None
    assert changed_table(json.dumps({'event': 'presence_state', 'payload': {}})) is None


def test_messages_malformes_ignores() -> None:
    assert changed_table('') is None
    assert changed_table('pas du json') is None
    assert changed_table(json.dumps([1, 2, 3])) is None
    assert changed_table(json.dumps({'event': 'postgres_changes'})) is None
    assert changed_table(json.dumps({'event': 'postgres_changes', 'payload': {}})) is None
    assert changed_table(json.dumps(
        {'event': 'postgres_changes', 'payload': {'data': {'table': ''}}})) is None
