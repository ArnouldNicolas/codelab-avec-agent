"""
Tests pytest pour la gestion des salles.
Ces tests vérifient les règles métier et les fonctionnalités de base.
"""

import pytest
import sqlite3
import os
from datetime import date, time

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
    
    # Créer une nouvelle base à partir de base.sql (sans les données d'exemple)
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Permet d'accéder aux colonnes par nom
    cursor = conn.cursor()
    
    # Charger le schéma
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


# ============================================================================
# TESTS POUR LA TABLE SALLES
# ============================================================================

class TestSalles:
    """Tests pour la gestion des salles."""

    def test_ajouter_salle_valide(self, setup_db):
        """Test : Ajouter une salle avec des données valides."""
        conn = setup_db
        cursor = conn.cursor()
        
        # Ajouter une salle
        cursor.execute("INSERT INTO salles (nom, capacite, type_de_local) VALUES ('Salle Test', 30, 'Salle de réunion')")
        conn.commit()
        
        # Vérifier que la salle a été ajoutée
        cursor.execute("SELECT * FROM salles WHERE nom = 'Salle Test'")
        salle = cursor.fetchone()
        
        assert salle is not None
        assert salle['nom'] == 'Salle Test'
        assert salle['capacite'] == 30
        assert salle['type_de_local'] == 'Salle de réunion'

    def test_ajouter_salle_capacite_nulle(self, setup_db):
        """Test : Impossible d'ajouter une salle avec capacité <= 0."""
        conn = setup_db
        cursor = conn.cursor()
        
        # Essayer d'ajouter une salle avec capacité = 0
        # SQLite a un CHECK dans base.sql qui bloque capacite <= 0
        try:
            cursor.execute("INSERT INTO salles (nom, capacite, type_de_local) VALUES ('Salle Invalide', 0, 'Salle de réunion')")
            conn.commit()
            assert False, "Devrait avoir échoué à cause de la contrainte CHECK"
        except sqlite3.IntegrityError:
            # C'est le comportement attendu
            pass

    def test_ajouter_salle_nom_duplique(self, setup_db):
        """Test : Impossible d'ajouter deux salles avec le même nom (UNIQUE)."""
        conn = setup_db
        cursor = conn.cursor()
        
        # Ajouter une première salle
        cursor.execute("INSERT INTO salles (nom, capacite, type_de_local) VALUES ('Salle Unique', 20, 'Salle de réunion')")
        conn.commit()
        
        # Essayer d'ajouter une deuxième salle avec le même nom
        try:
            cursor.execute("INSERT INTO salles (nom, capacite, type_de_local) VALUES ('Salle Unique', 30, 'Salle de réunion')")
            conn.commit()
            assert False, "Devrait avoir échoué à cause de la contrainte UNIQUE"
        except sqlite3.IntegrityError:
            # C'est le comportement attendu
            pass

    def test_supprimer_salle_avec_reservations(self, setup_db):
        """Test : Supprimer une salle supprime aussi ses réservations (ON DELETE CASCADE)."""
        conn = setup_db
        cursor = conn.cursor()
        
        # Ajouter une salle
        cursor.execute("INSERT INTO salles (nom, capacite, type_de_local) VALUES ('Salle à supprimer', 20, 'Salle de réunion')")
        salle_id = cursor.lastrowid
        conn.commit()
        
        # Ajouter des réservations pour cette salle
        cursor.execute("""
            INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
            VALUES (?, '2026-01-20', '10:00', '11:00', 'Réservation 1', 10)
        """, (salle_id,))
        cursor.execute("""
            INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
            VALUES (?, '2026-01-20', '14:00', '15:00', 'Réservation 2', 15)
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

    def test_supprimer_salle_inexistante(self, setup_db):
        """Test : Supprimer une salle qui n'existe pas ne fait rien."""
        conn = setup_db
        cursor = conn.cursor()
        
        # Essayer de supprimer une salle qui n'existe pas
        cursor.execute("DELETE FROM salles WHERE id = 999")
        conn.commit()
        
        # Vérifier que le nombre de salles n'a pas changé
        cursor.execute("SELECT COUNT(*) FROM salles")
        count = cursor.fetchone()[0]
        
        # Il n'y a aucune salle dans cette base vide
        assert count == 0

    def test_modifier_salle(self, setup_db):
        """Test : Modifier une salle existante."""
        conn = setup_db
        cursor = conn.cursor()
        
        # Ajouter une salle
        cursor.execute("INSERT INTO salles (nom, capacite, type_de_local) VALUES ('Salle à modifier', 20, 'Salle de réunion')")
        salle_id = cursor.lastrowid
        conn.commit()
        
        # Modifier la salle
        cursor.execute("UPDATE salles SET nom = 'Salle modifiée', capacite = 25 WHERE id = ?", (salle_id,))
        conn.commit()
        
        # Vérifier les modifications
        cursor.execute("SELECT * FROM salles WHERE id = ?", (salle_id,))
        salle = cursor.fetchone()
        
        assert salle is not None
        assert salle['nom'] == 'Salle modifiée'
        assert salle['capacite'] == 25

    def test_lister_salles_par_nom(self, setup_db):
        """Test : Lister les salles triées par nom."""
        conn = setup_db
        cursor = conn.cursor()
        
        # Ajouter des salles
        cursor.execute("INSERT INTO salles (nom, capacite, type_de_local) VALUES ('Z Salles', 10, 'Salle de réunion')")
        cursor.execute("INSERT INTO salles (nom, capacite, type_de_local) VALUES ('A Salles', 20, 'Salle de réunion')")
        cursor.execute("INSERT INTO salles (nom, capacite, type_de_local) VALUES ('M Salles', 15, 'Salle de réunion')")
        conn.commit()
        
        # Lister les salles triées par nom
        cursor.execute("SELECT nom FROM salles ORDER BY nom")
        noms = [row['nom'] for row in cursor.fetchall()]
        
        # Vérifier que les noms sont triés
        assert noms == sorted(noms)


# ============================================================================
# TESTS POUR LES RÈGLES MÉTIER LIÉES AUX SALLES
# ============================================================================

class TestReglesMetierSalles:
    """Tests pour les règles métier liées aux salles."""

    def test_capacite_positive(self, setup_db):
        """Test : La capacité d'une salle doit être positive."""
        conn = setup_db
        cursor = conn.cursor()
        
        # Ajouter des salles avec capacité positive
        cursor.execute("INSERT INTO salles (nom, capacite, type_de_local) VALUES ('Salle A', 10, 'Salle de réunion')")
        cursor.execute("INSERT INTO salles (nom, capacite, type_de_local) VALUES ('Salle B', 20, 'Salle de réunion')")
        conn.commit()
        
        # Récupérer toutes les salles
        cursor.execute("SELECT capacite FROM salles")
        capacites = [row['capacite'] for row in cursor.fetchall()]
        
        # Vérifier que toutes les capacités sont > 0
        for capacite in capacites:
            assert capacite > 0

    def test_nom_unique(self, setup_db):
        """Test : Les noms de salles doivent être uniques."""
        conn = setup_db
        cursor = conn.cursor()
        
        # Ajouter des salles avec des noms uniques
        cursor.execute("INSERT INTO salles (nom, capacite, type_de_local) VALUES ('Salle A', 10, 'Salle de réunion')")
        cursor.execute("INSERT INTO salles (nom, capacite, type_de_local) VALUES ('Salle B', 20, 'Salle de réunion')")
        conn.commit()
        
        # Récupérer tous les noms
        cursor.execute("SELECT nom FROM salles")
        noms = [row['nom'] for row in cursor.fetchall()]
        
        # Vérifier que tous les noms sont uniques
        assert len(noms) == len(set(noms))
