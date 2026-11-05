---
name: base-de-donnees
description: Charger cette skill quand l'utilisateur veut gérer le schéma, initialiser, modifier ou réinitialiser la base de données SQLite du projet de réservation.
user-invocable: true
---

# Gestion de la base de données SQLite

## Quand l'utiliser ?
- **Créer ou modifier le schéma** (fichier `base.sql`).
- **Initialiser la base** (`data.db`) à partir de `base.sql`.
- **Réinitialiser la base** (supprimer et recréer `data.db`).
- **Exporter/importer des données**.
- **Vérifier l’intégrité** des tables ou des contraintes.
- **Corriger des erreurs** dans `base.sql` ou `data.db`.

---

## Fichiers clés
| Fichier | Rôle | Emplacement |
|---------|------|-------------|
| `base.sql` | **Schéma de la base** (tables, index, exemples de données) | Racine du projet (`code-flask/` ou `code-streamlit/`) |
| `data.db` | **Base de données SQLite** (générée automatiquement) | Racine du projet |

---

## Structure attendue de `base.sql`
Le fichier `base.sql` doit contenir **au minimum** :

### 1. Table `salles`
```sql
CREATE TABLE IF NOT EXISTS salles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    capacite INTEGER NOT NULL CHECK (capacite > 0)
);
```

### 2. Table `reservations`
```sql
CREATE TABLE IF NOT EXISTS reservations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    salle_id INTEGER NOT NULL,
    date DATE NOT NULL,
    heure_debut TIME NOT NULL,
    heure_fin TIME NOT NULL,
    nom TEXT NOT NULL,
    participants INTEGER NOT NULL CHECK (participants > 0),
    FOREIGN KEY (salle_id) REFERENCES salles(id) ON DELETE CASCADE
);
```

### 3. Exemples de données (optionnel mais utile)
```sql
-- Exemples de salles
INSERT INTO salles (nom, capacite) VALUES ('Amphi A', 100);
INSERT INTO salles (nom, capacite) VALUES ('Salle B1', 20);
INSERT INTO salles (nom, capacite) VALUES ('Salle B2', 25);

-- Exemples de réservations
INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants) 
VALUES (1, '2025-01-20', '08:00', '10:00', 'Cours de Maths', 80);

INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants) 
VALUES (2, '2025-01-20', '14:00', '16:00', 'Réunion équipe', 15);
```

---

## Instructions par action

### 1️⃣ **Créer ou modifier `base.sql`**
#### Étapes :
1. **Lire le fichier existant** (si il existe) :
   ```bash
   read_file base.sql
   ```
2. **Modifier le schéma** :
   - Ajouter des tables, colonnes, ou contraintes.
   - Exemple : Ajouter une colonne `etage` à la table `salles`.
3. **Vérifier la syntaxe SQL** :
   - Utiliser un validateur en ligne (ex: [SQLite Online](https://sqliteonline.com/)).
   - Ou tester avec :
     ```bash
     sqlite3 :memory: < base.sql
     ```

#### Exemple de modification :
```sql
-- Ajouter une colonne 'etage' à la table salles
ALTER TABLE salles ADD COLUMN etage INTEGER DEFAULT 1;

-- Ajouter une table 'utilisateurs' (si besoin futur)
CREATE TABLE IF NOT EXISTS utilisateurs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL
);
```

---

### 2️⃣ **Initialiser `data.db` à partir de `base.sql`**
#### **Méthode 1 : Automatique (recommandée)**
Au premier lancement de `app.py` (Flask/Streamlit), ajouter ce code :
```python
import sqlite3
import os

def init_db():
    if not os.path.exists('data.db'):
        conn = sqlite3.connect('data.db')
        with open('base.sql', 'r') as f:
            conn.executescript(f.read())
        conn.close()

# Appeler au démarrage de l'app
init_db()
```

#### **Méthode 2 : Manuelle**
Exécuter depuis le terminal :
```bash
sqlite3 data.db < base.sql
```

---

### 3️⃣ **Réinitialiser la base (`data.db`)**
#### ⚠️ **Attention** : Cela supprime **toutes les données** existantes !
#### Étapes :
1. **Fermer l’application** (si elle utilise `data.db`).
2. **Supprimer `data.db`** :
   ```bash
   rm data.db
   ```
3. **Recréer `data.db`** à partir de `base.sql` :
   ```bash
   sqlite3 data.db < base.sql
   ```

#### **Pourquoi réinitialiser ?**
- Après une **modification de `base.sql`** (ajout/suppression de colonnes ou tables).
- Si la base est **corrompue**.
- Pour **réinitialiser les données** (ex: après des tests).

---

### 4️⃣ **Vérifier le schéma de la base**
#### Commandes SQLite3 utiles :
```bash
# Voir le schéma complet
sqlite3 data.db ".schema"

# Voir le schéma d'une table spécifique
sqlite3 data.db ".schema salles"
sqlite3 data.db ".schema reservations"

# Lister toutes les tables
sqlite3 data.db ".tables"

# Voir les contraintes de clé étrangère
sqlite3 data.db "PRAGMA foreign_key_list(reservations);"
```

---

### 5️⃣ **Exporter/Importer des données**
#### Exporter en CSV :
```bash
# Exporter la table 'salles' en CSV
sqlite3 data.db -csv "SELECT * FROM salles;" > salles.csv

# Exporter la table 'reservations' en CSV
sqlite3 data.db -csv "SELECT * FROM reservations;" > reservations.csv
```

#### Importer depuis CSV :
```bash
# Importer depuis un CSV (nécessite un outil comme csvsql ou un script Python)
echo ".mode csv
.import salles.csv salles" | sqlite3 data.db
```

#### Exporter/Importer en SQL :
```bash
# Exporter toutes les données en SQL
sqlite3 data.db .dump > backup.sql

# Importer depuis un fichier SQL
sqlite3 data.db < backup.sql
```

---

### 6️⃣ **Corriger des erreurs courantes**

#### Problème 1 : **`FOREIGN KEY` non activé**
SQLite ne vérifie **pas** les clés étrangères par défaut. Pour l’activer :
```python
# Dans app.py
conn = sqlite3.connect('data.db')
conn.execute("PRAGMA foreign_keys = ON;");  # Active les clés étrangères
```

#### Problème 2 : **Colonnes manquantes** après modification de `base.sql`
Si tu as ajouté une colonne à `base.sql` mais que `data.db` existe déjà :
1. Supprimer `data.db` :
   ```bash
   rm data.db
   ```
2. Recréer `data.db` :
   ```bash
   sqlite3 data.db < base.sql
   ```

#### Problème 3 : **Données invalides** (ex: `participants > capacite`)
- **Corriger manuellement** :
  ```bash
  sqlite3 data.db
  ```
  Puis exécuter des requêtes `UPDATE` ou `DELETE`.
- **Réinitialiser la base** :
  ```bash
  rm data.db && sqlite3 data.db < base.sql
  ```

#### Problème 4 : **`data.db` corrompu**
- **Symptômes** : Erreurs du type `database disk image is malformed`.
- **Solution** : Supprimer `data.db` et le recréer.

---

## Outils recommandés
| Outil | Utilisation |
|-------|-------------|
| `bash` | Exécuter des commandes SQLite3 (`sqlite3 data.db`). |
| `read_file`/`write_file` | Lire/écrire `base.sql`. |
| `edit` | Modifier `base.sql` ou `app.py`. |
| [SQLite Browser](https://sqlitebrowser.org/) | Interface graphique pour explorer `data.db`. |
| [SQLite Online](https://sqliteonline.com/) | Tester des requêtes SQL en ligne. |

---

## Exemples complets

### Exemple 1 : Ajouter une colonne `etage` à `salles`
1. Modifier `base.sql` :
   ```sql
   -- Dans base.sql
   CREATE TABLE IF NOT EXISTS salles (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       nom TEXT NOT NULL,
       capacite INTEGER NOT NULL CHECK (capacite > 0),
       etage INTEGER DEFAULT 1  -- Nouvelle colonne
   );
   ```
2. Réinitialiser `data.db` :
   ```bash
   rm data.db && sqlite3 data.db < base.sql
   ```

### Exemple 2 : Ajouter une contrainte de temps pour `reservations`
1. Modifier `base.sql` :
   ```sql
   -- Dans base.sql
   CREATE TABLE IF NOT EXISTS reservations (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       salle_id INTEGER NOT NULL,
       date DATE NOT NULL,
       heure_debut TIME NOT NULL CHECK (heure_debut >= '08:00' AND heure_debut <= '20:00'),
       heure_fin TIME NOT NULL CHECK (heure_fin >= '08:00' AND heure_fin <= '20:00'),
       nom TEXT NOT NULL,
       participants INTEGER NOT NULL CHECK (participants > 0),
       FOREIGN KEY (salle_id) REFERENCES salles(id) ON DELETE CASCADE,
       CHECK (heure_fin > heure_debut)  -- heure_fin doit être après heure_debut
   );
   ```
2. Réinitialiser `data.db` :
   ```bash
   rm data.db && sqlite3 data.db < base.sql
   ```

### Exemple 3 : Vérifier l’intégrité des données
```bash
# Vérifier qu'il n'y a pas de réservations avec participants > capacite
sqlite3 data.db "SELECT r.id, r.participants, s.capacite FROM reservations r JOIN salles s ON r.salle_id = s.id WHERE r.participants > s.capacite;"

# Vérifier qu'il n'y a pas de chevauchements
sqlite3 data.db "
SELECT r1.id, r2.id, r1.heure_debut, r1.heure_fin, r2.heure_debut, r2.heure_fin 
FROM reservations r1, reservations r2 
WHERE r1.salle_id = r2.salle_id AND r1.date = r2.date AND r1.id < r2.id 
AND r1.heure_debut < r2.heure_fin AND r1.heure_fin > r2.heure_debut;
"
```

---

## Bonnes pratiques
✅ **Toujours versionner `base.sql`** :
   - `git add base.sql` après chaque modification.
   - Ne **jamais** versionner `data.db` (ajouter `data.db` à `.gitignore`).

✅ **Utiliser des transactions** :
   ```python
   conn = sqlite3.connect('data.db')
   cursor = conn.cursor()
   try:
       cursor.execute("BEGIN TRANSACTION;")
       # Exécuter plusieurs requêtes
       cursor.execute("INSERT INTO salles ...")
       cursor.execute("INSERT INTO reservations ...")
       conn.commit()
   except Exception as e:
       conn.rollback()
       raise e
   finally:
       conn.close()
   ```

✅ **Activer les `FOREIGN KEY`** :
   ```python
   conn.execute("PRAGMA foreign_keys = ON;");
   ```

✅ **Utiliser des `CHECK` dans le schéma** :
   - `CHECK (capacite > 0)` pour `salles`.
   - `CHECK (participants > 0)` pour `reservations`.

✅ **Documenter `base.sql`** :
   - Ajouter des commentaires pour expliquer les tables et contraintes.
   - Exemple :
     ```sql
     -- Table des salles : nom unique, capacité > 0
     CREATE TABLE IF NOT EXISTS salles (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         nom TEXT NOT NULL UNIQUE,  -- Nom unique pour éviter les doublons
         capacite INTEGER NOT NULL CHECK (capacite > 0)  -- Capacité positive
     );
     ```

---

## Erreurs à éviter
❌ **Ne pas réinitialiser `data.db` après modification de `base.sql`** → Risque d’incohérence.
❌ **Versionner `data.db`** → Fichier binaire, lourd, et spécifique à chaque machine.
❌ **Oublier `ON DELETE CASCADE`** → Les réservations ne seront pas supprimées automatiquement.
❌ **Ne pas activer `FOREIGN KEY`** → Les contraintes ne seront pas vérifiées.
❌ **Utiliser des types de données incorrects** :
   - `date` doit être au format `YYYY-MM-DD`.
   - `heure_debut`/`heure_fin` doivent être au format `HH:MM` ou `HH:MM:SS`.

---

## Fichier `.gitignore` recommandé
```gitignore
# Base de données SQLite
data.db
data.db-shm
data.db-wal

# Fichiers temporaires
*.pyc
__pycache__/
.env

# Fichiers IDE
.idea/
.vscode/
```
