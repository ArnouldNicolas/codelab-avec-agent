"""Tests des réservations hebdomadaires sur plusieurs semaines et du bug d'affichage de la modification."""
import os
import sqlite3
from datetime import date, timedelta

import pytest

import app as appmod
from app import app

@pytest.fixture
def client(tmp_path, monkeypatch):
    """Base temporaire : ne touche pas à data.db."""
    monkeypatch.setattr(appmod, "DATABASE", str(tmp_path / "test.db"))
    app.config["TESTING"] = True
    with app.test_client() as c:
        conn = appmod.get_db()
        conn.execute("DELETE FROM reservations")
        conn.execute("DELETE FROM salles")
        conn.execute("INSERT INTO salles (id, nom, capacite) VALUES (1, 'S1', 20)")
        conn.commit()
        conn.close()
        yield c


def lundi_futur():
    d = date.today() + timedelta(days=60)
    return d - timedelta(days=d.weekday())


def reserver(client, debut, fin, d=None, participants=10, jusqua=None, nom="Alice"):
    d = d or lundi_futur()
    data = {"salle_id": 1, "date": d.isoformat(), "heure_debut": debut, "heure_fin": fin,
            "nom": nom, "participants": participants}
    if jusqua:
        data.update(repetition="on", date_fin_repetition=jusqua.isoformat())
    return client.post("/reservations", data=data)


def dates_reservees():
    conn = appmod.get_db()
    lignes = conn.execute("SELECT date FROM reservations ORDER BY date").fetchall()
    conn.close()
    return [l[0] for l in lignes]


def test_page_modifier_affiche_la_date_texte(client):
    reserver(client, "10:00", "12:00")
    conn = appmod.get_db()
    rid = conn.execute("SELECT id FROM reservations").fetchone()[0]
    conn.close()
    r = client.get(f"/reservations/{rid}/modifier")
    assert r.status_code == 200
    assert lundi_futur().isoformat() in r.get_data(as_text=True)


def test_filtre_date_accepte_chaine_et_objet():
    assert appmod.date_filter("2026-11-09") == "2026-11-09"
    assert appmod.date_filter(date(2026, 11, 9)) == "2026-11-09"
    assert appmod.date_filter(None) == ""


def test_reservation_sur_plusieurs_semaines(client):
    d = lundi_futur()
    reserver(client, "10:00", "12:00", d, jusqua=d + timedelta(weeks=3))
    assert dates_reservees() == [(d + timedelta(weeks=i)).isoformat() for i in range(4)]


def test_conflit_une_semaine_refuse_toute_la_serie(client):
    d = lundi_futur()
    reserver(client, "11:00", "13:00", d + timedelta(weeks=2), nom="Bob")
    reserver(client, "10:00", "12:00", d, jusqua=d + timedelta(weeks=3))
    assert len(dates_reservees()) == 1


def test_finir_a_12h_et_commencer_a_12h_en_serie(client):
    d = lundi_futur()
    reserver(client, "10:00", "12:00", d, nom="Bob")
    reserver(client, "12:00", "13:00", d, jusqua=d + timedelta(weeks=2))
    assert len(dates_reservees()) == 4


def test_chevauchement_creneau_englobant(client):
    d = lundi_futur()
    reserver(client, "10:00", "11:00", d, nom="Bob")
    reserver(client, "09:00", "12:00", d)
    assert len(dates_reservees()) == 1


def test_capacite_refusee_sur_serie(client):
    d = lundi_futur()
    reserver(client, "10:00", "12:00", d, participants=25, jusqua=d + timedelta(weeks=2))
    assert dates_reservees() == []


def test_modifier_toute_la_serie_ne_entre_pas_en_conflit_avec_elle_meme(client):
    d = lundi_futur()
    reserver(client, "10:00", "12:00", d, jusqua=d + timedelta(weeks=3))
    conn = appmod.get_db()
    fille = conn.execute("SELECT id FROM reservations WHERE reservation_mere_id IS NOT NULL ORDER BY date LIMIT 1").fetchone()[0]
    conn.close()
    r = client.post(f"/reservations/{fille}/modifier", data={
        "salle_id": 1, "date": (d + timedelta(weeks=1)).isoformat(), "heure_debut": "10:30", "heure_fin": "12:30",
        "nom": "Alice", "participants": 12, "modifier_toutes": "on",
        "repetition": "on", "date_fin_repetition": (d + timedelta(weeks=3)).isoformat()})
    assert r.status_code == 302
    conn = appmod.get_db()
    heures = {l[0] for l in conn.execute("SELECT heure_debut FROM reservations")}
    conn.close()
    assert heures == {"10:30:00"}


def test_reduire_capacite_refuse_si_serie_a_venir_trop_grande(client):
    d = lundi_futur()
    reserver(client, "10:00", "12:00", d, participants=15, jusqua=d + timedelta(weeks=2))
    r = client.post("/salles/1/modifier", data={"nom": "S1", "capacite": 10}, follow_redirects=False)
    assert r.status_code == 200
    conn = appmod.get_db()
    assert conn.execute("SELECT capacite FROM salles WHERE id = 1").fetchone()[0] == 20
    conn.close()


def test_desactiver_repetition_depuis_une_occurrence(client):
    d = lundi_futur()
    reserver(client, "10:00", "12:00", d, jusqua=d + timedelta(weeks=3))
    conn = appmod.get_db()
    fille = conn.execute("SELECT id FROM reservations WHERE reservation_mere_id IS NOT NULL ORDER BY date LIMIT 1").fetchone()[0]
    conn.close()
    r = client.post(f"/reservations/{fille}/modifier", data={
        "salle_id": 1, "date": (d + timedelta(weeks=1)).isoformat(), "heure_debut": "10:00", "heure_fin": "12:00",
        "nom": "Alice", "participants": 10, "modifier_toutes": "on"})
    assert r.status_code == 302
    conn = appmod.get_db()
    lignes = conn.execute("SELECT date, repetition, reservation_mere_id FROM reservations").fetchall()
    conn.close()
    assert [tuple(l) for l in lignes] == [(d.isoformat(), 0, None)]


def ajouter_salle2():
    conn = appmod.get_db()
    conn.execute("INSERT INTO salles (id, nom, capacite) VALUES (2, 'S2', 20)")
    conn.commit()
    conn.close()


def reserver_salle2(client, d, debut, fin, nom, **extra):
    data = {"salle_id": 2, "date": d.isoformat(), "heure_debut": debut, "heure_fin": fin,
            "nom": nom, "participants": 5}
    data.update(extra)
    return client.post("/reservations", data=data)


def test_supprimer_les_occurrences_les_supprime_de_la_base_et_de_la_liste(client):
    d = date.today() - timedelta(weeks=2)
    d -= timedelta(days=d.weekday())
    reserver(client, "10:00", "12:00", d, jusqua=d + timedelta(weeks=6))
    conn = appmod.get_db()
    ids = [r[0] for r in conn.execute("SELECT id FROM reservations ORDER BY date")]
    conn.close()
    r = client.post(f"/reservations/{ids[2]}/supprimer-repetition", follow_redirects=True)
    assert "6 occurrence(s)" in r.get_data(as_text=True)
    conn = appmod.get_db()
    lignes = conn.execute("SELECT id, repetition, date_fin_repetition, reservation_mere_id FROM reservations").fetchall()
    conn.close()
    assert [tuple(l) for l in lignes] == [(ids[0], 0, None, None)]


def test_supprimer_les_occurrences_serie_passee(client):
    d = date(2026, 1, 5)
    reserver(client, "10:00", "12:00", d, jusqua=d + timedelta(weeks=2))
    assert len(dates_reservees()) == 3
    conn = appmod.get_db()
    mere = conn.execute("SELECT id FROM reservations ORDER BY date").fetchone()[0]
    conn.close()
    client.post(f"/reservations/{mere}/supprimer-repetition")
    assert dates_reservees() == [d.isoformat()]


def test_personne_ne_peut_pas_se_chevaucher_dans_deux_salles(client):
    d = lundi_futur()
    ajouter_salle2()
    reserver(client, "10:00", "12:00", d, nom="Alice")
    reserver_salle2(client, d, "11:00", "13:00", " alice ")
    assert len(dates_reservees()) == 1


def test_meme_personne_creneaux_qui_se_touchent_ou_autre_personne(client):
    d = lundi_futur()
    ajouter_salle2()
    reserver(client, "10:00", "12:00", d, nom="Alice")
    reserver_salle2(client, d, "12:00", "13:00", "Alice")
    reserver_salle2(client, d, "10:00", "12:00", "Bob")
    assert len(dates_reservees()) == 3


def test_personne_chevauchement_dans_une_serie_refuse_tout(client):
    d = lundi_futur()
    ajouter_salle2()
    reserver(client, "10:00", "12:00", d + timedelta(weeks=2), nom="Alice")
    reserver_salle2(client, d, "11:00", "12:30", "Alice", repetition="on",
                    date_fin_repetition=(d + timedelta(weeks=3)).isoformat())
    assert len(dates_reservees()) == 1


def test_modifier_reservation_ne_chevauche_pas_une_autre_de_la_personne(client):
    d = lundi_futur()
    reserver(client, "10:00", "12:00", d, nom="Alice")
    reserver(client, "14:00", "15:00", d, nom="Alice")
    conn = appmod.get_db()
    second = conn.execute("SELECT id FROM reservations ORDER BY heure_debut DESC").fetchone()[0]
    conn.close()
    client.post(f"/reservations/{second}/modifier", data={
        "salle_id": 1, "date": d.isoformat(), "heure_debut": "11:00", "heure_fin": "13:00",
        "nom": "Alice", "participants": 5})
    conn = appmod.get_db()
    assert conn.execute("SELECT heure_debut FROM reservations WHERE id = ?", (second,)).fetchone()[0] == "14:00:00"
    conn.close()
