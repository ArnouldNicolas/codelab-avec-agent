import pytest


@pytest.fixture
def client():
    from app import app
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_accueil(client):
    resp = client.get("/")
    assert resp.status_code == 200


def test_reservation_reussie(client):
    """Lundi 12h-13h doit être accepté (S1 finit à 12h, début à 12h autorisé)."""
    client.post(
        "/reserver",
        data=dict(
            salle_id="1",
            personne="Alice",
            date="2026-11-10",
            debut="12:00",
            fin="13:00",
            participants="10",
        ),
        follow_redirects=True,
    )
    resp = client.get("/planning/1")
    assert b"Alice" in resp.data


def test_chevauchement_refuse(client):
    """Lundi 11h-13h refusée : chevauchement avec S1 10h-12h."""
    resp = client.post(
        "/reserver",
        data=dict(
            salle_id="1",
            personne="Bob",
            date="2026-11-10",
            debut="11:00",
            fin="13:00",
            participants="10",
        ),
        follow_redirects=True,
    )
    assert b"chevauchement" in resp.data.lower()


def test_capacite_depassee(client):
    """Lundi 14h-15h, 25 participants refusée : capacité dépassée (S1: 20)."""
    resp = client.post(
        "/reserver",
        data=dict(
            salle_id="1",
            personne="Charlie",
            date="2026-11-10",
            debut="14:00",
            fin="15:00",
            participants="25",
        ),
        follow_redirects=True,
    )
    assert b"participants" in resp.data.lower()


def test_avant_8h_refuse(client):
    """Lundi 7h30-9h refusée : avant 8 h."""
    resp = client.post(
        "/reserver",
        data=dict(
            salle_id="1",
            personne="David",
            date="2026-11-10",
            debut="07:30",
            fin="09:00",
            participants="10",
        ),
        follow_redirects=True,
    )
    assert b"avant 8 h" in resp.data.lower()


def test_moins_30_min_refuse(client):
    """Mardi 14h-14h20 refusée : moins de 30 min."""
    resp = client.post(
        "/reserver",
        data=dict(
            salle_id="1",
            personne="Eve",
            date="2026-11-11",
            debut="14:00",
            fin="14:20",
            participants="10",
        ),
        follow_redirects=True,
    )
    assert b"30 minutes" in resp.data.lower()


def test_plus_4h_refuse(client):
    """Mardi 8h-13h refusée : plus de 4 h."""
    resp = client.post(
        "/reserver",
        data=dict(
            salle_id="1",
            personne="Frank",
            date="2026-11-11",
            debut="08:00",
            fin="13:00",
            participants="10",
        ),
        follow_redirects=True,
    )
    assert b"4 heures" in resp.data.lower() or b"4 h" in resp.data.lower()


def test_annulation(client):
    """Tester l'annulation d'une réservation."""
    client.post(
        "/reserver",
        data=dict(
            salle_id="1",
            personne="Test",
            date="2026-11-10",
            debut="15:00",
            fin="16:00",
            participants="5",
        ),
        follow_redirects=True,
    )
    resp = client.get("/planning/1")
    assert resp.status_code == 200


def test_planning(client):
    """Tester l'affichage du planning."""
    client.post(
        "/reserver",
        data=dict(
            salle_id="1",
            personne="Test",
            date="2026-11-10",
            debut="15:00",
            fin="16:00",
            participants="5",
        ),
        follow_redirects=True,
    )
    resp = client.get("/planning/1")
    assert resp.status_code == 200
    assert b"Planning" in resp.data