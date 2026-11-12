"""
Tests pytest pour les nouvelles fonctionnalites ajoutees.
1. Ajouter une salle avec un responsable
2. Afficher le planning d'une salle
"""

import pytest
import sqlite3
import os
from datetime import date, time
from app import app

DATABASE = 'data.db'


@pytest.fixture
def client():
    """Fixture pour le client Flask."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def setup_db():
    """Fixture pour initialiser la base de donnees avec le nouveau schema."""
    if os.path.exists(DATABASE):
        try:
            os.remove(DATABASE)
        except:
            pass
    
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    with open('base.sql', 'r', encoding='utf-8') as f:
        schema = f.read()
    cursor.executescript(schema)
    
    cursor.execute("PRAGMA foreign_keys = ON")
    conn.commit()
    
    yield conn
    
    conn.close()
    
    if os.path.exists(DATABASE):
        try:
            os.remove(DATABASE)
        except:
            pass


class TestResponsableSalle:
    """Tests pour la gestion du responsable d'une salle."""

    def test_ajouter_salle_avec_responsable(self, setup_db):
        conn = setup_db
        cursor = conn.cursor()
        cursor.execute("INSERT INTO salles (nom, capacite, responsable) VALUES ('Salle avec responsable', 30, 'Jean Dupont')")
        conn.commit()
        cursor.execute("SELECT * FROM salles WHERE nom = 'Salle avec responsable'")
        salle = cursor.fetchone()
        assert salle is not None
        assert salle['responsable'] == 'Jean Dupont'

    def test_ajouter_salle_sans_responsable(self, setup_db):
        conn = setup_db
        cursor = conn.cursor()
        cursor.execute("INSERT INTO salles (nom, capacite) VALUES ('Salle sans responsable', 25)")
        conn.commit()
        cursor.execute("SELECT * FROM salles WHERE nom = 'Salle sans responsable'")
        salle = cursor.fetchone()
        assert salle is not None
        assert salle['responsable'] is None


class TestPlanningSalle:
    """Tests pour la route de planning d'une salle."""

    def test_planning_salle_existante(self, client, setup_db):
        conn = setup_db
        cursor = conn.cursor()
        cursor.execute("INSERT INTO salles (nom, capacite) VALUES ('Salle Test', 20)")
        salle_id = cursor.lastrowid
        cursor.execute("INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants) VALUES (?, '2026-01-20', '10:00', '12:00', 'Reservation Test', 10)", (salle_id,))
        conn.commit()
        resp = client.get(f'/salles/{salle_id}/planning')
        assert resp.status_code == 200
        assert b'Salle Test' in resp.data

    def test_planning_salle_inexistante(self, client, setup_db):
        resp = client.get('/salles/9999/planning')
        assert resp.status_code == 302

    def test_planning_salle_sans_reservations(self, client, setup_db):
        conn = setup_db
        cursor = conn.cursor()
        cursor.execute("INSERT INTO salles (nom, capacite) VALUES ('Salle Vide', 30)")
        salle_id = cursor.lastrowid
        conn.commit()
        resp = client.get(f'/salles/{salle_id}/planning')
        assert resp.status_code == 200
        assert b'Salle Vide' in resp.data
        assert b'Aucune reservation' in resp.data
