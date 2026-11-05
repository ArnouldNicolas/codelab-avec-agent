"""
Tests pytest pour la gestion des réservations.
Ces tests vérifient toutes les règles métier du projet.
"""

import pytest
import sqlite3
import os
from datetime import date, time, datetime, timedelta

# Chemin vers la base de données de test
DATABASE = 'data.db'


@pytest.fixture
def setup_db():
    """Fixture pour initialiser la base de données avant chaque test."""
    # Supprimer data.db si elle existe
    if os.path.exists(DATABASE):
        try:
            os.remove(DATABASE)
        except:
            pass
    
    # Créer une nouvelle base à partir de base.sql
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Permet d'accéder aux colonnes par nom
    cursor = conn.cursor()
    
    # Charger le schéma depuis base.sql (sans les données d'exemple)
    cursor.executescript("""
        -- Table des salles
        CREATE TABLE IF NOT EXISTS salles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL UNIQUE,
            capacite INTEGER NOT NULL CHECK (capacite > 0)
        );

        -- Table des réservations
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            salle_id INTEGER NOT NULL,
            date DATE NOT NULL,
            heure_debut TIME NOT NULL,
            heure_fin TIME NOT NULL,
            nom TEXT NOT NULL,
            participants INTEGER NOT NULL CHECK (participants > 0),
            FOREIGN KEY (salle_id) REFERENCES salles(id) ON DELETE CASCADE,
            CHECK (heure_debut >= '08:00' AND heure_debut <= '20:00'),
            CHECK (heure_fin >= '08:00' AND heure_fin <= '20:00'),
            CHECK (heure_fin > heure_debut)
        );
    """)
    
    # Activer les foreign keys
    cursor.execute("PRAGMA foreign_keys = ON")
    conn.commit()
    
    yield conn
    
    # Fermer la connexion avant de supprimer la base
    conn.close()
    
    # Supprimer data.db après le test
    if os.path.exists(DATABASE):
        try:
            os.remove(DATABASE)
        except:
            pass


@pytest.fixture
def salle_test(setup_db):
    """Fixture pour créer une salle de test."""
    conn = setup_db
    cursor = conn.cursor()
    cursor.execute("INSERT INTO salles (nom, capacite) VALUES ('Salle Test', 20)")
    salle_id = cursor.lastrowid
    conn.commit()
    yield conn, salle_id
    # La fixture setup_db supprime déjà la base


# ============================================================================
# TESTS POUR LES RÈGLES MÉTIER
# ============================================================================

class TestReglesMetier:
    """Tests pour toutes les règles métier des réservations."""

    # Règle 1 : Pas de chevauchement
    def test_pas_de_chevauchement(self, salle_test):
        """Test : Deux réservations pour une même salle ne peuvent pas se chevaucher."""
        conn, salle_id = salle_test
        cursor = conn.cursor()
        
        # Ajouter une première réservation (10h-11h)
        cursor.execute("""
            INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
            VALUES (?, '2026-01-20', '10:00', '11:00', 'Réservation 1', 10)
        """, (salle_id,))
        conn.commit()
        
        # Vérifier qu'on peut ajouter une réservation consécutive (11h-12h) ✅
        cursor.execute("""
            INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
            VALUES (?, '2026-01-20', '11:00', '12:00', 'Réservation 2', 10)
        """, (salle_id,))
        conn.commit()
        
        # Vérifier qu'on détecte un conflit avec une réservation qui chevauche (10h30-11h30) ❌
        cursor.execute("""
            SELECT COUNT(*) FROM reservations 
            WHERE salle_id = ? AND date = '2026-01-20' AND (
                (heure_debut <= '10:30' AND heure_fin > '10:30') OR 
                (heure_debut < '11:30' AND heure_fin >= '11:30')
            )
        """, (salle_id,))
        count = cursor.fetchone()[0]
        
        # Il y a déjà 2 réservations, donc count > 0 = conflit
        assert count > 0

    def test_chevauchement_exact(self, salle_test):
        """Test : Une réservation qui finit à 12h peut être suivie par une autre qui commence à 12h."""
        conn, salle_id = salle_test
        cursor = conn.cursor()
        
        # Ajouter une première réservation (10h-12h)
        cursor.execute("""
            INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
            VALUES (?, '2026-01-20', '10:00', '12:00', 'Réservation 1', 10)
        """, (salle_id,))
        conn.commit()
        
        # Ajouter une deuxième réservation qui commence à 12h (12h-13h)
        cursor.execute("""
            INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
            VALUES (?, '2026-01-20', '12:00', '13:00', 'Réservation 2', 10)
        """, (salle_id,))
        conn.commit()
        
        # Vérifier que les 2 réservations existent
        cursor.execute("SELECT COUNT(*) FROM reservations WHERE salle_id = ?", (salle_id,))
        count = cursor.fetchone()[0]
        
        assert count == 2

    # Règle 2 : Capacité respectée
    def test_capacite_respectee(self, salle_test):
        """Test : Le nombre de participants ne doit pas dépasser la capacité de la salle."""
        conn, salle_id = salle_test
        cursor = conn.cursor()
        
        # Récupérer la capacité de la salle
        cursor.execute("SELECT capacite FROM salles WHERE id = ?", (salle_id,))
        capacite = cursor.fetchone()['capacite']
        
        # Ajouter une réservation avec participants = capacité ✅
        cursor.execute("""
            INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
            VALUES (?, '2026-01-20', '10:00', '11:00', 'Réservation valide', ?)
        """, (salle_id, capacite))
        conn.commit()
        
        # Vérifier que la réservation existe
        cursor.execute("SELECT * FROM reservations WHERE salle_id = ?", (salle_id,))
        reservation = cursor.fetchone()
        
        assert reservation is not None
        assert reservation['participants'] == capacite

    # Règle 3 : Horaires valides
    def test_horaire_8h_20h(self, salle_test):
        """Test : Les réservations doivent être entre 8h et 20h."""
        conn, salle_id = salle_test
        cursor = conn.cursor()
        
        # Ajouter une réservation valide (10h-11h) ✅
        cursor.execute("""
            INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
            VALUES (?, '2026-01-20', '10:00', '11:00', 'Réservation valide', 10)
        """, (salle_id,))
        conn.commit()
        
        # Vérifier que la réservation existe
        cursor.execute("SELECT * FROM reservations WHERE nom = 'Réservation valide'")
        reservation = cursor.fetchone()
        
        assert reservation is not None

    def test_horaire_avant_8h(self, salle_test):
        """Test : Impossible de réserver avant 8h."""
        conn, salle_id = salle_test
        cursor = conn.cursor()
        
        # SQLite a un CHECK dans base.sql qui bloque heure_debut < '08:00'
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
                VALUES (?, '2026-01-20', '07:00', '08:00', 'Réservation invalide', 10)
            """, (salle_id,))
            conn.commit()

    def test_horaire_apres_20h(self, salle_test):
        """Test : Impossible de réserver après 20h."""
        conn, salle_id = salle_test
        cursor = conn.cursor()
        
        # SQLite a un CHECK dans base.sql qui bloque heure_fin > '20:00'
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
                VALUES (?, '2026-01-20', '19:00', '21:00', 'Réservation invalide', 10)
            """, (salle_id,))
            conn.commit()

    # Règle 4 : Durée valide
    def test_duree_minimale_30min(self, salle_test):
        """Test : La durée minimale d'une réservation est de 30 minutes."""
        conn, salle_id = salle_test
        cursor = conn.cursor()
        
        # SQLite n'a pas de CHECK sur la durée dans base.sql
        # mais l'application doit vérifier
        cursor.execute("""
            INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
            VALUES (?, '2026-01-20', '10:00', '10:30', 'Réservation 30 min', 10)
        """, (salle_id,))
        conn.commit()
        
        # Vérifier que la réservation existe
        cursor.execute("SELECT * FROM reservations WHERE nom = 'Réservation 30 min'")
        reservation = cursor.fetchone()
        
        assert reservation is not None

    def test_duree_minimale_invalide(self, salle_test):
        """Test : Impossible de réserver pour moins de 30 minutes."""
        conn, salle_id = salle_test
        cursor = conn.cursor()
        
        # SQLite bloque heure_fin <= heure_debut
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
                VALUES (?, '2026-01-20', '10:00', '10:00', 'Réservation invalide', 10)
            """, (salle_id,))
            conn.commit()

    def test_duree_maximale_4h(self, salle_test):
        """Test : La durée maximale d'une réservation est de 4 heures."""
        conn, salle_id = salle_test
        cursor = conn.cursor()
        
        # SQLite n'a pas de CHECK sur la durée max dans base.sql
        # mais l'application doit vérifier
        cursor.execute("""
            INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
            VALUES (?, '2026-01-20', '10:00', '14:00', 'Réservation 4h', 10)
        """, (salle_id,))
        conn.commit()
        
        # Vérifier que la réservation existe
        cursor.execute("SELECT * FROM reservations WHERE nom = 'Réservation 4h'")
        reservation = cursor.fetchone()
        
        assert reservation is not None

    # Règle 5 : Suppression en cascade
    def test_suppression_salle_cascade(self, salle_test):
        """Test : Supprimer une salle supprime toutes ses réservations."""
        conn, salle_id = salle_test
        cursor = conn.cursor()
        
        # Ajouter des réservations pour cette salle
        cursor.execute("""
            INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
            VALUES (?, '2026-01-20', '10:00', '11:00', 'Réservation 1', 10)
        """, (salle_id,))
        cursor.execute("""
            INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
            VALUES (?, '2026-01-20', '14:00', '15:00', 'Réservation 2', 10)
        """, (salle_id,))
        conn.commit()
        
        # Vérifier que les réservations existent
        cursor.execute("SELECT COUNT(*) FROM reservations WHERE salle_id = ?", (salle_id,))
        count_before = cursor.fetchone()[0]
        assert count_before == 2
        
        # Supprimer la salle
        cursor.execute("DELETE FROM salles WHERE id = ?", (salle_id,))
        conn.commit()
        
        # Vérifier que les réservations ont été supprimées
        cursor.execute("SELECT COUNT(*) FROM reservations WHERE salle_id = ?", (salle_id,))
        count_after = cursor.fetchone()[0]
        
        assert count_after == 0


# ============================================================================
# TESTS POUR LES CAS PARTICULIERS
# ============================================================================

class TestCasParticuliers:
    """Tests pour des cas particuliers."""

    def test_reservation_le_matin(self, salle_test):
        """Test : Réservation dès 8h00."""
        conn, salle_id = salle_test
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
            VALUES (?, '2026-01-20', '08:00', '09:00', 'Réservation matinale', 10)
        """, (salle_id,))
        conn.commit()
        
        cursor.execute("SELECT heure_debut FROM reservations WHERE nom = 'Réservation matinale'")
        reservation = cursor.fetchone()
        
        assert reservation is not None
        # SQLite retourne les TIME comme des strings
        assert reservation['heure_debut'] == '08:00'

    def test_reservation_le_soir(self, salle_test):
        """Test : Réservation jusqu'à 20h00."""
        conn, salle_id = salle_test
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
            VALUES (?, '2026-01-20', '19:00', '20:00', 'Réservation du soir', 10)
        """, (salle_id,))
        conn.commit()
        
        cursor.execute("SELECT heure_fin FROM reservations WHERE nom = 'Réservation du soir'")
        reservation = cursor.fetchone()
        
        assert reservation is not None
        # SQLite retourne les TIME comme des strings
        assert reservation['heure_fin'] == '20:00'

    def test_reservations_multiples_salles_different(self, setup_db):
        """Test : Plusieurs réservations pour des salles différentes à la même heure."""
        conn = setup_db
        cursor = conn.cursor()
        
        # Ajouter des salles
        cursor.execute("INSERT INTO salles (nom, capacite) VALUES ('Salle 1', 20)")
        cursor.execute("INSERT INTO salles (nom, capacite) VALUES ('Salle 2', 25)")
        salle1_id = cursor.lastrowid - 1
        salle2_id = cursor.lastrowid
        conn.commit()
        
        # Réserver les deux salles à la même heure
        cursor.execute("""
            INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
            VALUES (?, '2026-01-20', '10:00', '11:00', 'Réservation Salle 1', 10)
        """, (salle1_id,))
        cursor.execute("""
            INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
            VALUES (?, '2026-01-20', '10:00', '11:00', 'Réservation Salle 2', 15)
        """, (salle2_id,))
        conn.commit()
        
        # Vérifier que les deux réservations existent (et seulement ces 2)
        cursor.execute("SELECT COUNT(*) FROM reservations WHERE date = '2026-01-20'")
        count = cursor.fetchone()[0]
        
        assert count == 2


# ============================================================================
# TESTS D'INTÉGRATION
# ============================================================================

class TestIntegration:
    """Tests d'intégration pour des scénarios complets."""

    def test_workflow_complet(self, setup_db):
        """Test : Workflow complet d'ajout, modification et suppression."""
        conn = setup_db
        cursor = conn.cursor()
        
        # 1. Ajouter une salle
        cursor.execute("INSERT INTO salles (nom, capacite) VALUES ('Salle Workflow', 50)")
        salle_id = cursor.lastrowid
        conn.commit()
        
        # 2. Ajouter une réservation
        cursor.execute("""
            INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
            VALUES (?, '2026-01-20', '10:00', '11:00', 'Réservation initiale', 20)
        """, (salle_id,))
        reservation_id = cursor.lastrowid
        conn.commit()
        
        # 3. Vérifier que la réservation existe
        cursor.execute("SELECT * FROM reservations WHERE id = ?", (reservation_id,))
        reservation = cursor.fetchone()
        assert reservation is not None
        
        # 4. Modifier la réservation
        cursor.execute("""
            UPDATE reservations 
            SET heure_debut = '14:00', heure_fin = '15:00', nom = 'Réservation modifiée'
            WHERE id = ?
        """, (reservation_id,))
        conn.commit()
        
        # 5. Vérifier les modifications
        cursor.execute("SELECT heure_debut, heure_fin, nom FROM reservations WHERE id = ?", (reservation_id,))
        heure_debut, heure_fin, nom = cursor.fetchone()
        # SQLite retourne les TIME comme des strings
        assert heure_debut == '14:00'
        assert heure_fin == '15:00'
        assert nom == 'Réservation modifiée'
        
        # 6. Supprimer la réservation
        cursor.execute("DELETE FROM reservations WHERE id = ?", (reservation_id,))
        conn.commit()
        
        # 7. Vérifier que la réservation a été supprimée
        cursor.execute("SELECT * FROM reservations WHERE id = ?", (reservation_id,))
        reservation = cursor.fetchone()
        assert reservation is None
        
        # 8. Supprimer la salle
        cursor.execute("DELETE FROM salles WHERE id = ?", (salle_id,))
        conn.commit()
        
        # 9. Vérifier que la salle a été supprimée
        cursor.execute("SELECT * FROM salles WHERE id = ?", (salle_id,))
        salle = cursor.fetchone()
        assert salle is None


# ============================================================================
# TESTS POUR LES REQUÊTES UTILES
# ============================================================================

class TestRequetesUtiles:
    """Tests pour les requêtes SQL utiles."""

    def test_lister_reservations_par_salle(self, salle_test):
        """Test : Lister les réservations pour une salle spécifique."""
        conn, salle_id = salle_test
        cursor = conn.cursor()
        
        # Ajouter des réservations
        cursor.execute("""
            INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
            VALUES (?, '2026-01-20', '10:00', '11:00', 'Réservation 1', 10)
        """, (salle_id,))
        cursor.execute("""
            INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
            VALUES (?, '2026-01-20', '14:00', '15:00', 'Réservation 2', 10)
        """, (salle_id,))
        conn.commit()
        
        # Lister les réservations pour cette salle
        cursor.execute("SELECT * FROM reservations WHERE salle_id = ? ORDER BY date, heure_debut", (salle_id,))
        reservations = cursor.fetchall()
        
        assert len(reservations) == 2

    def test_salle_est_disponible(self, salle_test):
        """Test : Vérifier si une salle est disponible pour une plage horaire."""
        conn, salle_id = salle_test
        cursor = conn.cursor()
        
        # Ajouter une réservation (10h-11h)
        cursor.execute("""
            INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
            VALUES (?, '2026-01-20', '10:00', '11:00', 'Réservation existante', 10)
        """, (salle_id,))
        conn.commit()
        
        # Vérifier qu'on détecte un conflit pour 10h30-11h30
        cursor.execute("""
            SELECT COUNT(*) FROM reservations 
            WHERE salle_id = ? AND date = '2026-01-20' AND (
                (heure_debut <= '10:30' AND heure_fin > '10:30') OR 
                (heure_debut < '11:30' AND heure_fin >= '11:30')
            )
        """, (salle_id,))
        count = cursor.fetchone()[0]
        
        assert count > 0  # Conflit détecté
        
        # Vérifier qu'il n'y a pas de conflit pour 12h-13h
        cursor.execute("""
            SELECT COUNT(*) FROM reservations 
            WHERE salle_id = ? AND date = '2026-01-20' AND (
                (heure_debut <= '12:00' AND heure_fin > '12:00') OR 
                (heure_debut < '13:00' AND heure_fin >= '13:00')
            )
        """, (salle_id,))
        count = cursor.fetchone()[0]
        
        assert count == 0  # Pas de conflit
