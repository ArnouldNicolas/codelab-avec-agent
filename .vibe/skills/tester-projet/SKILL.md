---
name: tester-projet
description: Charger cette skill quand l'utilisateur veut écrire, exécuter, déboguer ou corriger les tests pytest du projet de réservation universitaire.
user-invocable: true
---

# Tests pytest pour le projet Réservation de salles

## Quand l'utiliser ?
- **Écrire de nouveaux tests** (ex: "Ajoute un test pour vérifier les chevauchements").
- **Exécuter les tests** (`pytest`).
- **Déboguer un test qui échoue**.
- **Mettre à jour les tests** après une modification du code.
- **Vérifier la couverture de test**.

---

## Structure des tests
- **Fichiers** : `test_*.py` (ex: `test_reservations.py`, `test_salles.py`).
- **Framework** : `pytest`.
- **Bonnes pratiques** :
  - **1 fichier par module** (ex: `test_reservations.py` pour `reservations`).
  - **1 fonction par cas de test** (nommée `test_*` ou `*_test`).
  - **Utiliser des fixtures** pour initialiser/réinitialiser la base de données.

---

## Règles métier à tester (OBLIGATOIRE)
Toute fonctionnalité doit valider **toutes** ces règles :

| Règle | Description | Exemple de test |
|-------|-------------|-----------------|
| **Pas de chevauchement** | Deux réservations pour une même salle ne peuvent pas se chevaucher. | `test_ajouter_reservation_conflit` |
| **Capacité respectée** | `participants <= capacite` de la salle. | `test_ajouter_reservation_capacite_insuffisante` |
| **Horaires valides** | Réservations entre **8h et 20h**. | `test_ajouter_reservation_heure_invalide` |
| **Durée valide** | Durée entre **30 min et 4h**. | `test_ajouter_reservation_duree_invalide` |
| **Suppression en cascade** | Supprimer une salle supprime ses réservations. | `test_supprimer_salle_cascade` |

---

## Configuration de pytest
### Installer pytest (si ce n’est pas déjà fait) :
```bash
pip install pytest
```

### Fichier `pytest.ini` (optionnel, pour des options globales) :
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_functions = test_*
addopts = -v --tb=short
```

---

## Fixtures pytest (INCONTOURNABLES)
Les fixtures permettent d’**initialiser et réinitialiser la base de données** avant chaque test.

### Exemple de fixture de base :
```python
# Dans conftest.py ou test_*.py
import sqlite3
import pytest
import os

@pytest.fixture
def setup_db():
    """Initialise une base de données temporaire pour chaque test."""
    # Supprimer data.db si elle existe
    if os.path.exists('data.db'):
        os.remove('data.db')
    
    # Créer une nouvelle base à partir de base.sql
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    
    # Charger le schéma depuis base.sql
    with open('base.sql', 'r') as f:
        cursor.executescript(f.read())
    
    # Activer les foreign keys
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    yield conn  # Retourne la connexion pour le test
    
    # Fermer la connexion après le test
    conn.close()
    
    # Supprimer data.db après le test
    if os.path.exists('data.db'):
        os.remove('data.db')
```

### Fixture pour des données de test :
```python
@pytest.fixture
def salle_avec_reservation(setup_db):
    """Crée une salle avec une réservation pour les tests."""
    conn = setup_db
    cursor = conn.cursor()
    
    # Ajouter une salle
    cursor.execute("INSERT INTO salles (nom, capacite) VALUES ('Salle Test', 20)")
    salle_id = cursor.lastrowid
    
    # Ajouter une réservation
    cursor.execute("""
        INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
        VALUES (?, '2025-01-20', '10:00', '11:00', 'Test Réservation', 10)
    """, (salle_id,))
    
    yield conn, salle_id  # Retourne la connexion et l'ID de la salle
    conn.rollback()  # Annuler les modifications après le test
```

---

## Exemples de tests complets

### 1️⃣ **Tests pour `salles`** (`test_salles.py`)
```python
import sqlite3
import pytest
from datetime import date, time

# Importer les fonctions à tester (si dans un module)
# from app import ajouter_salle, modifier_salle, supprimer_salle

@pytest.fixture
def setup_db():
    """Fixture pour initialiser la base."""
    if os.path.exists('data.db'):
        os.remove('data.db')
    
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    with open('base.sql', 'r') as f:
        cursor.executescript(f.read())
    cursor.execute("PRAGMA foreign_keys = ON;")
    yield conn
    conn.close()
    if os.path.exists('data.db'):
        os.remove('data.db')


# Test : Ajouter une salle valide
def test_ajouter_salle_valide(setup_db):
    conn = setup_db
    cursor = conn.cursor()
    
    # Appeler la fonction (ou exécuter SQL directement)
    cursor.execute("INSERT INTO salles (nom, capacite) VALUES ('Salle A', 30)")
    
    # Vérifier que la salle a été ajoutée
    cursor.execute("SELECT * FROM salles WHERE nom = 'Salle A'")
    salle = cursor.fetchone()
    assert salle is not None
    assert salle[1] == 'Salle A'
    assert salle[2] == 30


# Test : Ajouter une salle avec capacité <= 0
def test_ajouter_salle_capacite_invalide(setup_db):
    conn = setup_db
    cursor = conn.cursor()
    
    # SQLite n'a pas de CHECK par défaut dans la fixture de base
    # Si tu as ajouté CHECK (capacite > 0) dans base.sql, ceci échouera :
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute("INSERT INTO salles (nom, capacite) VALUES ('Salle Invalide', 0)")
    
    # Sinon, vérifier manuellement :
    cursor.execute("INSERT INTO salles (nom, capacite) VALUES ('Salle Invalide', 0)")
    cursor.execute("SELECT capacite FROM salles WHERE nom = 'Salle Invalide'")
    capacite = cursor.fetchone()[0]
    assert capacite == 0  # Mais c'est invalide selon les règles métier


# Test : Supprimer une salle et ses réservations (cascade)
def test_supprimer_salle_cascade(setup_db):
    conn = setup_db
    cursor = conn.cursor()
    
    # Ajouter une salle
    cursor.execute("INSERT INTO salles (nom, capacite) VALUES ('Salle à supprimer', 20)")
    salle_id = cursor.lastrowid
    
    # Ajouter des réservations
    cursor.execute("""
        INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
        VALUES (?, '2025-01-20', '10:00', '11:00', 'Réservation 1', 10)
    """, (salle_id,))
    cursor.execute("""
        INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
        VALUES (?, '2025-01-20', '14:00', '15:00', 'Réservation 2', 15)
    """, (salle_id,))
    
    # Vérifier que les réservations existent
    cursor.execute("SELECT COUNT(*) FROM reservations WHERE salle_id = ?", (salle_id,))
    assert cursor.fetchone()[0] == 2
    
    # Supprimer la salle
    cursor.execute("DELETE FROM salles WHERE id = ?", (salle_id,))
    
    # Vérifier que les réservations ont été supprimées (cascade)
    cursor.execute("SELECT COUNT(*) FROM reservations WHERE salle_id = ?", (salle_id,))
    assert cursor.fetchone()[0] == 0
```

---

### 2️⃣ **Tests pour `reservations`** (`test_reservations.py`)
```python
import sqlite3
import pytest
from datetime import date, time

# Importer les fonctions à tester (si dans un module)
# from app import ajouter_reservation, modifier_reservation, supprimer_reservation

@pytest.fixture
def setup_db():
    if os.path.exists('data.db'):
        os.remove('data.db')
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    with open('base.sql', 'r') as f:
        cursor.executescript(f.read())
    cursor.execute("PRAGMA foreign_keys = ON;")
    yield conn
    conn.close()
    if os.path.exists('data.db'):
        os.remove('data.db')


# Test : Ajouter une réservation valide
def test_ajouter_reservation_valide(setup_db):
    conn = setup_db
    cursor = conn.cursor()
    
    # Ajouter une salle
    cursor.execute("INSERT INTO salles (nom, capacite) VALUES ('Salle Test', 20)")
    salle_id = cursor.lastrowid
    
    # Ajouter une réservation valide
    cursor.execute("""
        INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
        VALUES (?, '2025-01-20', '10:00', '11:00', 'Réunion', 10)
    """, (salle_id,))
    
    # Vérifier que la réservation existe
    cursor.execute("SELECT * FROM reservations WHERE salle_id = ?", (salle_id,))
    reservation = cursor.fetchone()
    assert reservation is not None
    assert reservation[2] == date(2025, 1, 20)  # date
    assert reservation[3] == time(10, 0)      # heure_debut
    assert reservation[4] == time(11, 0)      # heure_fin


# Test : Ajouter une réservation avec chevauchement (DOIT ÉCHOUER)
def test_ajouter_reservation_conflit(setup_db):
    conn = setup_db
    cursor = conn.cursor()
    
    # Ajouter une salle
    cursor.execute("INSERT INTO salles (nom, capacite) VALUES ('Salle Test', 20)")
    salle_id = cursor.lastrowid
    
    # Ajouter une première réservation (10h-11h)
    cursor.execute("""
        INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
        VALUES (?, '2025-01-20', '10:00', '11:00', 'Réunion 1', 10)
    """, (salle_id,))
    
    # Essayer d'ajouter une réservation en conflit (10h30-11h30)
    # Si tu utilises une fonction Python avec vérification :
    with pytest.raises(ValueError, match="Conflit de réservation"):
        # Appeler ajouter_reservation(salle_id, date(2025, 1, 20), time(10, 30), time(11, 30), "Réunion 2", 10)
        pass
    
    # Sinon, vérifier manuellement avec SQL :
    cursor.execute("""
        INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
        VALUES (?, '2025-01-20', '10:30', '11:30', 'Réunion 2', 10)
    """, (salle_id,))
    
    # Vérifier qu'il y a maintenant 2 réservations (ce qui est invalide)
    cursor.execute("SELECT COUNT(*) FROM reservations WHERE salle_id = ?", (salle_id,))
    assert cursor.fetchone()[0] == 2  # Mais c'est un bug à corriger !


# Test : Ajouter une réservation avec participants > capacité
def test_ajouter_reservation_capacite_insuffisante(setup_db):
    conn = setup_db
    cursor = conn.cursor()
    
    # Ajouter une salle avec capacité 10
    cursor.execute("INSERT INTO salles (nom, capacite) VALUES ('Salle Petite', 10)")
    salle_id = cursor.lastrowid
    
    # Essayer d'ajouter une réservation avec 15 participants
    with pytest.raises(ValueError, match="Capacité de la salle insuffisante"):
        # Appeler ajouter_reservation(salle_id, date(2025, 1, 20), time(10, 0), time(11, 0), "Réunion", 15)
        pass


# Test : Ajouter une réservation avec horaires invalides (avant 8h)
def test_ajouter_reservation_heure_invalide(setup_db):
    conn = setup_db
    cursor = conn.cursor()
    
    # Ajouter une salle
    cursor.execute("INSERT INTO salles (nom, capacite) VALUES ('Salle Test', 20)")
    salle_id = cursor.lastrowid
    
    # Essayer d'ajouter une réservation à 7h (invalide)
    with pytest.raises(ValueError, match="entre 8h00 et 20h00"):
        # Appeler ajouter_reservation(salle_id, date(2025, 1, 20), time(7, 0), time(8, 0), "Réunion", 10)
        pass


# Test : Ajouter une réservation avec durée invalide (< 30 min)
def test_ajouter_reservation_duree_invalide(setup_db):
    conn = setup_db
    cursor = conn.cursor()
    
    # Ajouter une salle
    cursor.execute("INSERT INTO salles (nom, capacite) VALUES ('Salle Test', 20)")
    salle_id = cursor.lastrowid
    
    # Essayer d'ajouter une réservation de 15 min (invalide)
    with pytest.raises(ValueError, match="entre 30 minutes et 4 heures"):
        # Appeler ajouter_reservation(salle_id, date(2025, 1, 20), time(10, 0), time(10, 15), "Réunion", 10)
        pass


# Test : Ajouter une réservation avec durée invalide (> 4h)
def test_ajouter_reservation_duree_trop_longue(setup_db):
    conn = setup_db
    cursor = conn.cursor()
    
    # Ajouter une salle
    cursor.execute("INSERT INTO salles (nom, capacite) VALUES ('Salle Test', 20)")
    salle_id = cursor.lastrowid
    
    # Essayer d'ajouter une réservation de 5h (invalide)
    with pytest.raises(ValueError, match="entre 30 minutes et 4 heures"):
        # Appeler ajouter_reservation(salle_id, date(2025, 1, 20), time(10, 0), time(15, 0), "Réunion", 10)
        pass


# Test : Réservations consécutives (12h-13h et 13h-14h = VALIDE)
def test_reservations_consecutives_valides(setup_db):
    conn = setup_db
    cursor = conn.cursor()
    
    # Ajouter une salle
    cursor.execute("INSERT INTO salles (nom, capacite) VALUES ('Salle Test', 20)")
    salle_id = cursor.lastrowid
    
    # Ajouter deux réservations consécutives (pas de chevauchement)
    cursor.execute("""
        INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
        VALUES (?, '2025-01-20', '12:00', '13:00', 'Réunion 1', 10)
    """, (salle_id,))
    cursor.execute("""
        INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
        VALUES (?, '2025-01-20', '13:00', '14:00', 'Réunion 2', 10)
    """, (salle_id,))
    
    # Vérifier que les 2 réservations existent
    cursor.execute("SELECT COUNT(*) FROM reservations WHERE salle_id = ?", (salle_id,))
    assert cursor.fetchone()[0] == 2
```

---

### 3️⃣ **Tests d’intégration** (`test_integration.py`)
Tester des scénarios complets (ex: réserver une salle, modifier, supprimer).

```python
import sqlite3
import pytest
from datetime import date, time

@pytest.fixture
def setup_db():
    if os.path.exists('data.db'):
        os.remove('data.db')
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    with open('base.sql', 'r') as f:
        cursor.executescript(f.read())
    cursor.execute("PRAGMA foreign_keys = ON;")
    yield conn
    conn.close()
    if os.path.exists('data.db'):
        os.remove('data.db')


# Test : Workflow complet (ajouter salle + réservation + modifier + supprimer)
def test_workflow_complet(setup_db):
    conn = setup_db
    cursor = conn.cursor()
    
    # 1. Ajouter une salle
    cursor.execute("INSERT INTO salles (nom, capacite) VALUES ('Salle Intégration', 50)")
    salle_id = cursor.lastrowid
    
    # 2. Ajouter une réservation
    cursor.execute("""
        INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
        VALUES (?, '2025-01-20', '10:00', '11:00', 'Réunion initiale', 20)
    """, (salle_id,))
    reservation_id = cursor.lastrowid
    
    # 3. Vérifier que la réservation existe
    cursor.execute("SELECT * FROM reservations WHERE id = ?", (reservation_id,))
    assert cursor.fetchone() is not None
    
    # 4. Modifier la réservation (changer l'heure)
    cursor.execute("""
        UPDATE reservations 
        SET heure_debut = '14:00', heure_fin = '15:00', nom = 'Réunion modifiée'
        WHERE id = ?
    """, (reservation_id,))
    
    # 5. Vérifier les modifications
    cursor.execute("SELECT heure_debut, heure_fin, nom FROM reservations WHERE id = ?", (reservation_id,))
    heure_debut, heure_fin, nom = cursor.fetchone()
    assert heure_debut == time(14, 0)
    assert heure_fin == time(15, 0)
    assert nom == 'Réunion modifiée'
    
    # 6. Supprimer la réservation
    cursor.execute("DELETE FROM reservations WHERE id = ?", (reservation_id,))
    
    # 7. Vérifier que la réservation a été supprimée
    cursor.execute("SELECT * FROM reservations WHERE id = ?", (reservation_id,))
    assert cursor.fetchone() is None
    
    # 8. Supprimer la salle (et vérifier la cascade)
    cursor.execute("DELETE FROM salles WHERE id = ?", (salle_id,))
    cursor.execute("SELECT COUNT(*) FROM reservations WHERE salle_id = ?", (salle_id,))
    assert cursor.fetchone()[0] == 0
```

---

## Exécuter les tests

### Commandes de base :
```bash
# Lancer tous les tests
pytest

# Lancer avec plus de détails (verbose)
pytest -v

# Lancer un fichier de test spécifique
pytest test_reservations.py

# Lancer une fonction de test spécifique
pytest test_reservations.py::test_ajouter_reservation_valide

# Lancer avec affichage des prints
pytest -s

# Lancer avec arrêt au premier échec
pytest -x

# Lancer et afficher la couverture de code (nécessite pytest-cov)
pip install pytest-cov
pytest --cov=app --cov-report=term
```

---

## Déboguer un test qui échoue

### 1. **Lire le message d’erreur** :
```bash
pytest -v
```
Exemple de sortie :
```
test_reservations.py::test_ajouter_reservation_conflit FAILED
```

### 2. **Afficher plus de détails** :
```bash
pytest test_reservations.py::test_ajouter_reservation_conflit -v -tb=short
```
- `-tb=short` : Affiche un traceback court.
- `-tb=long` : Affiche un traceback complet.

### 3. **Utiliser `print` pour déboguer** :
Dans le test, ajoute des `print` pour afficher des valeurs :
```python
def test_ajouter_reservation_conflit(setup_db):
    conn = setup_db
    cursor = conn.cursor()
    
    # Ajouter une salle
    cursor.execute("INSERT INTO salles (nom, capacite) VALUES ('Salle Test', 20)")
    salle_id = cursor.lastrowid
    print(f"salle_id: {salle_id}")  # Débogage
    
    # Ajouter une première réservation
    cursor.execute("""
        INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
        VALUES (?, '2025-01-20', '10:00', '11:00', 'Réunion 1', 10)
    """, (salle_id,))
    
    # Vérifier les réservations existantes
    cursor.execute("SELECT * FROM reservations WHERE salle_id = ?", (salle_id,))
    print(f"Réservations existantes: {cursor.fetchall()}")  # Débogage
    
    # Essayer d'ajouter une réservation en conflit
    # ...
```

### 4. **Utiliser le débogueur Python** :
```bash
# Installer pdb (déjà inclus avec Python)
python -m pdb -m pytest test_reservations.py::test_ajouter_reservation_conflit
```

### 5. **Vérifier la base de données manuellement** :
```bash
# Après un test échoué, inspecter data.db
sqlite3 data.db "SELECT * FROM reservations;"
sqlite3 data.db "SELECT * FROM salles;"
```

---

## Outils recommandés
| Outil | Utilisation |
|-------|-------------|
| `pytest` | Exécuter les tests. |
| `pytest -v` | Mode verbose. |
| `pytest -s` | Afficher les `print`. |
| `pytest --cov` | Couverture de code (nécessite `pytest-cov`). |
| `sqlite3` | Inspecter `data.db` après un test. |
| `pdb` | Déboguer le code Python. |

---

## Bonnes pratiques
✅ **Un test par cas** : Un test doit vérifier **une seule chose** (ex: chevauchement, capacité, etc.).

✅ **Noms de tests clairs** :
- ✅ `test_ajouter_reservation_conflit`
- ❌ `test_1` ou `test_reservation`

✅ **Utiliser des fixtures** : Pour éviter de dupliquer le code d’initialisation.

✅ **Tester les cas limites** :
- Réservations à 8h00 et 20h00.
- Réservations de 30 min et 4h.
- Chevauchements exacts (10h-11h et 11h-12h).
- Capacité exactement égale au nombre de participants.

✅ **Tester les erreurs** : Utiliser `pytest.raises` pour vérifier que les erreurs sont levées.

✅ **Garder les tests rapides** : Éviter les `sleep` ou les boucles longues.

✅ **Ne pas dépendre de l’ordre des tests** : Chaque test doit être **isolé** (utiliser des fixtures).

---

## Erreurs courantes
❌ **Oublier de supprimer `data.db` après les tests** :
   - **Solution** : Utiliser une fixture qui supprime `data.db` après chaque test.

❌ **Tests qui dépendent de l’ordre d’exécution** :
   - **Solution** : Chaque test doit initialiser sa propre base.

❌ **Ne pas tester les cas d’erreur** :
   - **Solution** : Toujours tester les validations (ex: chevauchement, capacité).

❌ **Tests trop lents** :
   - **Solution** : Éviter les opérations coûteuses (ex: `time.sleep`).

❌ **Ne pas utiliser `pytest.raises`** :
   - ❌ `try/except` sans vérification.
   - ✅ `with pytest.raises(ValueError): ...`

---

## Exemple de fichier `requirements.txt` pour les tests
```
pytest>=7.0.0
pytest-cov>=4.0.0  # Optionnel, pour la couverture
```

---

## Résumé des commandes utiles
| Commande | Description |
|----------|-------------|
| `pytest` | Lancer tous les tests. |
| `pytest -v` | Lancer avec détails. |
| `pytest test_*.py` | Lancer les tests d’un fichier. |
| `pytest -k "conflit"` | Lancer les tests avec "conflit" dans le nom. |
| `pytest -x` | Arrêter au premier échec. |
| `pytest --cov=app` | Afficher la couverture de code. |
| `pytest --lf` | Relancer les tests échoués en dernier. |
