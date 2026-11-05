---
name: reserver-salle
description: Charger cette skill quand l'utilisateur veut réserver, modifier, supprimer ou lister une salle/réservation dans le projet de réservation universitaire. Appliquer les règles métier du AGENTS.md.
user-invocable: true
---

# Réservation de salles - Gestion complète

## Quand l'utiliser ?
- **Ajouter/Modifier/Supprimer** une salle ou une réservation.
- **Vérifier les conflits** entre réservations.
- **Lister** les salles ou réservations disponibles.
- **Appliquer les règles métier** définies dans `AGENTS.md`.

---

## Règles métier (À RESPECTER ABSOLUMENT)
1. **Pas de chevauchement** : Deux réservations pour une même salle ne peuvent pas se chevaucher.
   - *Autorisé* : Une réservation qui finit à **12h00** peut être suivie par une autre qui commence à **12h00**.
   - *Interdit* : Une réservation de 10h-11h30 et une autre de 11h00-12h00 pour la même salle.
2. **Capacité** : Le nombre de participants ne doit **jamais** dépasser la capacité de la salle.
3. **Horaires** :
   - Réservations **uniquement entre 8h00 et 20h00**.
   - Durée **minimale** : 30 minutes.
   - Durée **maximale** : 4 heures.
4. **Suppression en cascade** : Supprimer une salle **supprime automatiquement** toutes ses réservations.
5. **Pas d'authentification** : Le système ne gère pas les utilisateurs.
6. **Semaine** : Du **lundi au dimanche**.

---

## Structure du projet
- **Technologies** : Python, SQLite, pytest.
- **Frameworks** : Flask (`code-flask/`) ou Streamlit (`code-streamlit/`).
- **Base de données** :
  - Fichier `base.sql` : Schéma et exemples de données.
  - Fichier `data.db` : Créé automatiquement au premier lancement.
  - *Astuce* : Supprimer `data.db` après une modification de `base.sql`.

---

## Fichiers clés
| Fichier | Rôle |
|---------|------|
| `base.sql` | Schéma de la base (tables `salles`, `reservations`). |
| `app.py` | Application principale (Flask/Streamlit). |
| `data.db` | Base de données SQLite (générée automatiquement). |
| `test_*.py` | Tests pytest pour valider les règles métier. |

---

## Instructions par action

### 1️⃣ **Ajouter une réservation**
#### Étapes :
1. **Vérifier la salle** :
   - Lister les salles avec `SELECT * FROM salles;` (via `sqlite3 data.db`).
   - Vérifier que `salle_id` existe et que `capacite >= participants`.
2. **Vérifier les conflits** :
   ```sql
   SELECT * FROM reservations 
   WHERE salle_id = ? AND date = ? AND (
       (heure_debut <= ? AND heure_fin > ?) OR  -- Nouvelle réservation commence pendant une existante
       (heure_debut < ? AND heure_fin >= ?)     -- Nouvelle réservation finit pendant une existante
   );
   ```
   - *Paramètres* : `salle_id`, `date`, `heure_debut`, `heure_fin`, `heure_debut`, `heure_fin`.
3. **Vérifier les horaires** :
   - `heure_debut` et `heure_fin` doivent être entre **08:00 et 20:00**.
   - Durée (`heure_fin - heure_debut`) doit être entre **0.5h et 4h**.
4. **Insérer la réservation** :
   ```sql
   INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
   VALUES (?, ?, ?, ?, ?, ?);
   ```
5. **Mettre à jour les tests** :
   - Ajouter un test dans `test_*.py` pour valider la nouvelle fonctionnalité.
   - Exécuter `pytest` pour vérifier que tout fonctionne.

#### Exemple de code Python (Flask) :
```python
import sqlite3
from datetime import datetime, time

def ajouter_reservation(salle_id, date, heure_debut, heure_fin, nom, participants):
    # Vérifier les horaires
    if not (time(8, 0) <= heure_debut <= time(20, 0) and time(8, 0) <= heure_fin <= time(20, 0)):
        raise ValueError("Les réservations doivent être entre 8h et 20h.")
    
    duree = (heure_fin.hour - heure_debut.hour) + (heure_fin.minute - heure_debut.minute) / 60
    if not (0.5 <= duree <= 4):
        raise ValueError("La durée doit être entre 30 min et 4h.")
    
    # Vérifier la capacité de la salle
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT capacite FROM salles WHERE id = ?", (salle_id,))
    salle = cursor.fetchone()
    if not salle or salle[0] < participants:
        raise ValueError("Capacité de la salle insuffisante.")
    
    # Vérifier les conflits
    cursor.execute("""
        SELECT * FROM reservations 
        WHERE salle_id = ? AND date = ? AND (
            (heure_debut <= ? AND heure_fin > ?) OR 
            (heure_debut < ? AND heure_fin >= ?)
        )
    """, (salle_id, date, heure_debut, heure_debut, heure_fin, heure_fin))
    
    if cursor.fetchone():
        raise ValueError("Conflit de réservation : la salle est déjà réservée à cet horaire.")
    
    # Ajouter la réservation
    cursor.execute("""
        INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (salle_id, date, heure_debut, heure_fin, nom, participants))
    conn.commit()
    conn.close()
```

---

### 2️⃣ **Modifier une réservation**
#### Étapes :
1. **Supprimer l’ancienne réservation** (si les horaires ou la salle changent).
2. **Ajouter une nouvelle réservation** avec les nouvelles valeurs (en utilisant la procédure ci-dessus).

#### Exemple :
```python
def modifier_reservation(id, nouvelle_salle_id=None, nouvelle_date=None, nouvelle_heure_debut=None, nouvelle_heure_fin=None, nouveau_nom=None, nouveaux_participants=None):
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    
    # Récupérer l'ancienne réservation
    cursor.execute("SELECT * FROM reservations WHERE id = ?", (id,))
    ancienne_reservation = cursor.fetchone()
    if not ancienne_reservation:
        raise ValueError("Réservation introuvable.")
    
    # Supprimer l'ancienne réservation
    cursor.execute("DELETE FROM reservations WHERE id = ?", (id,))
    
    # Créer la nouvelle réservation avec les valeurs mises à jour
    salle_id = nouvelle_salle_id if nouvelle_salle_id is not None else ancienne_reservation[1]
    date = nouvelle_date if nouvelle_date is not None else ancienne_reservation[2]
    heure_debut = nouvelle_heure_debut if nouvelle_heure_debut is not None else ancienne_reservation[3]
    heure_fin = nouvelle_heure_fin if nouvelle_heure_fin is not None else ancienne_reservation[4]
    nom = nouveau_nom if nouveau_nom is not None else ancienne_reservation[5]
    participants = nouveaux_participants if nouveaux_participants is not None else ancienne_reservation[6]
    
    # Réutiliser la fonction ajouter_reservation
    ajouter_reservation(salle_id, date, heure_debut, heure_fin, nom, participants)
    conn.commit()
    conn.close()
```

---

### 3️⃣ **Supprimer une réservation**
#### Étapes :
1. Vérifier que la réservation existe.
2. Supprimer de la table `reservations`.

#### Exemple :
```python
def supprimer_reservation(id):
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reservations WHERE id = ?", (id,))
    if cursor.rowcount == 0:
        raise ValueError("Réservation introuvable.")
    conn.commit()
    conn.close()
```

---

### 4️⃣ **Supprimer une salle**
#### ⚠️ **Règle critique** : Supprimer une salle **supprime toutes ses réservations** (cascade).
#### Étapes :
1. Supprimer toutes les réservations associées à la salle.
2. Supprimer la salle.

#### Exemple :
```python
def supprimer_salle(salle_id):
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    
    # Supprimer les réservations de la salle
    cursor.execute("DELETE FROM reservations WHERE salle_id = ?", (salle_id,))
    
    # Supprimer la salle
    cursor.execute("DELETE FROM salles WHERE id = ?", (salle_id,))
    conn.commit()
    conn.close()
```

---

### 5️⃣ **Lister les salles/réservations**
#### Exemples de requêtes SQL :
- **Lister toutes les salles** :
  ```sql
  SELECT * FROM salles;
  ```
- **Lister les réservations pour une salle** :
  ```sql
  SELECT * FROM reservations WHERE salle_id = ? ORDER BY date, heure_debut;
  ```
- **Lister les salles disponibles pour une plage horaire** :
  ```sql
  SELECT s.* FROM salles s
  WHERE s.id NOT IN (
      SELECT r.salle_id FROM reservations r
      WHERE r.date = ? AND (
          (r.heure_debut <= ? AND r.heure_fin > ?) OR
          (r.heure_debut < ? AND r.heure_fin >= ?)
      )
  );
  ```

---

## Méthode de travail (À SUIVRE)
1. **Une fonctionnalité à la fois** : Traiter une seule tâche (ex: ajouter une réservation) avant de passer à la suivante.
2. **Tests d’abord** :
   - Ajouter ou mettre à jour les tests **avant** de coder la fonctionnalité.
   - Exécuter `pytest` après chaque modification pour valider.
3. **Pas de dépendances supplémentaires** : Ne pas ajouter de bibliothèques sans demande explicite.
4. **Git** :
   - Ne faire `git push` **que si le binôme le demande**.
   - Commiter après chaque fonctionnalité terminée et testée.

---

## Exemples de tests (pytest)
```python
# test_reservations.py
import sqlite3
import pytest
from datetime import date, time

@pytest.fixture
def setup_db():
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    # Charger le schéma depuis base.sql
    with open('base.sql', 'r') as f:
        cursor.executescript(f.read())
    yield conn
    conn.close()

def test_ajouter_reservation_valide(setup_db):
    conn = setup_db
    cursor = conn.cursor()
    cursor.execute("INSERT INTO salles (nom, capacite) VALUES ('Salle A', 20)")
    salle_id = cursor.lastrowid
    
    # Réservation valide (10h-11h30, 10 participants)
    ajouter_reservation(salle_id, date(2024, 1, 15), time(10, 0), time(11, 30), "Réunion", 10)
    
    # Vérifier que la réservation existe
    cursor.execute("SELECT * FROM reservations WHERE salle_id = ?", (salle_id,))
    assert cursor.fetchone() is not None

def test_ajouter_reservation_conflit(setup_db):
    conn = setup_db
    cursor = conn.cursor()
    cursor.execute("INSERT INTO salles (nom, capacite) VALUES ('Salle A', 20)")
    salle_id = cursor.lastrowid
    
    # Première réservation (10h-11h30)
    ajouter_reservation(salle_id, date(2024, 1, 15), time(10, 0), time(11, 30), "Réunion 1", 10)
    
    # Deuxième réservation en conflit (11h-12h)
    with pytest.raises(ValueError, match="Conflit de réservation"):
        ajouter_reservation(salle_id, date(2024, 1, 15), time(11, 0), time(12, 0), "Réunion 2", 10)

def test_ajouter_reservation_capacite_insuffisante(setup_db):
    conn = setup_db
    cursor = conn.cursor()
    cursor.execute("INSERT INTO salles (nom, capacite) VALUES ('Salle B', 10)")
    salle_id = cursor.lastrowid
    
    with pytest.raises(ValueError, match="Capacité de la salle insuffisante"):
        ajouter_reservation(salle_id, date(2024, 1, 15), time(10, 0), time(11, 0), "Réunion", 15)
```

---

## Outils recommandés
| Outil | Utilisation |
|-------|-------------|
| `bash` | Exécuter des commandes SQLite (`sqlite3 data.db`). |
| `read_file`/`write_file` | Lire/écrire `app.py`, `base.sql`, ou les tests. |
| `edit` | Modifier des fichiers existants (ex: `app.py`). |
| `run_typescript` | Manipuler des données ou lancer des requêtes SQL via des outils. |
| `pytest` | Lancer les tests pour valider les règles métier. |

---

## Commandes utiles
| Commande | Description |
|----------|-------------|
| `python app.py` | Lancer l’application (Flask). |
| `streamlit run app.py` | Lancer l’application (Streamlit). |
| `pytest` | Lancer tous les tests. |
| `sqlite3 data.db` | Ouvrir la base de données en ligne de commande. |
| `rm data.db` | Supprimer la base pour la recréer après un changement de `base.sql`. |

---

## Erreurs courantes à éviter
❌ **Oublier les règles métier** : Toujours vérifier les chevauchements, la capacité, et les horaires.
❌ **Ne pas tester** : Toujours exécuter `pytest` après une modification.
❌ **Modifier `base.sql` sans recréer `data.db`** : Supprimer `data.db` après un changement de schéma.
❌ **Ajouter des dépendances sans demande** : Respecter la contrainte du projet.

---

## Besoin d’aide ?
- **Vérifier le schéma** : Lire `base.sql` pour comprendre les tables.
- **Debugger** : Utiliser `sqlite3 data.db` pour inspecter les données.
- **Tester manuellement** : Lancer l’application et essayer les fonctionnalités.
