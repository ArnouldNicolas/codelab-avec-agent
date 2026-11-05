---
name: gerer-salles
description: Charger cette skill quand l'utilisateur veut ajouter, modifier, supprimer ou lister une salle dans le projet de réservation universitaire.
user-invocable: true
---

# Gestion des salles

## Quand l'utiliser ?
- **Ajouter une nouvelle salle** (ex: "Ajoute une salle 'Amphi B' avec 50 places").
- **Modifier une salle existante** (ex: "Change la capacité de la salle 1 à 30").
- **Supprimer une salle** (⚠️ supprime aussi ses réservations).
- **Lister toutes les salles** (ex: "Affiche la liste des salles disponibles").

---

## Règles métier (À RESPECTER)
1. **Suppression en cascade** : Supprimer une salle **supprime automatiquement toutes ses réservations**. 
   → *Exemple* : Si la salle 1 a 5 réservations, les supprimer toutes avant de supprimer la salle.
2. **Champs obligatoires** : Une salle doit avoir un **nom** et une **capacité** (entier > 0).
3. **Nom unique** : Deux salles ne peuvent pas avoir le même nom (recommandé, mais pas obligatoire dans le projet actuel).

---

## Structure de la table `salles` (SQLite)
| Champ | Type | Description | Exemple |
|-------|------|-------------|---------|
| `id` | INTEGER | Clé primaire (auto-incrémentée) | `1` |
| `nom` | TEXT | Nom de la salle | `"Amphi A"` |
| `capacite` | INTEGER | Nombre de places | `100` |

---

## Instructions par action

### 1️⃣ **Ajouter une salle**
#### Étapes :
1. Vérifier que le **nom** n’existe pas déjà (optionnel, mais recommandé).
2. Vérifier que la **capacité** est un entier > 0.
3. Insérer dans la table `salles`.

#### Requête SQL :
```sql
INSERT INTO salles (nom, capacite) VALUES (?, ?);
```

#### Exemple en Python (Flask/Streamlit) :
```python
import sqlite3

def ajouter_salle(nom: str, capacite: int) -> int:
    if capacite <= 0:
        raise ValueError("La capacité doit être supérieure à 0.")
    
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    
    # Vérifier si le nom existe déjà (optionnel)
    cursor.execute("SELECT id FROM salles WHERE nom = ?", (nom,))
    if cursor.fetchone():
        raise ValueError(f"Une salle nommé '{nom}' existe déjà.")
    
    cursor.execute("INSERT INTO salles (nom, capacite) VALUES (?, ?)", (nom, capacite))
    salle_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return salle_id
```

---

### 2️⃣ **Modifier une salle**
#### Étapes :
1. Vérifier que la salle existe.
2. Vérifier que la nouvelle **capacité** est valide (> 0).
3. Mettre à jour la table `salles`.

#### Requête SQL :
```sql
UPDATE salles SET nom = ?, capacite = ? WHERE id = ?;
```

#### Exemple en Python :
```python
def modifier_salle(salle_id: int, nouveau_nom: str = None, nouvelle_capacite: int = None):
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    
    # Vérifier que la salle existe
    cursor.execute("SELECT * FROM salles WHERE id = ?", (salle_id,))
    if not cursor.fetchone():
        raise ValueError(f"Salle avec ID {salle_id} introuvable.")
    
    # Construire la requête dynamique
    updates = []
    params = []
    if nouveau_nom is not None:
        updates.append("nom = ?")
        params.append(nouveau_nom)
    if nouvelle_capacite is not None:
        if nouvelle_capacite <= 0:
            raise ValueError("La capacité doit être supérieure à 0.")
        updates.append("capacite = ?")
        params.append(nouvelle_capacite)
    
    if not updates:
        raise ValueError("Aucune modification spécifiée.")
    
    params.append(salle_id)
    query = f"UPDATE salles SET {', '.join(updates)} WHERE id = ?"
    cursor.execute(query, params)
    conn.commit()
    conn.close()
```

---

### 3️⃣ **Supprimer une salle**
#### ⚠️ **Règle critique** : **Supprime toutes ses réservations** (cascade).
#### Étapes :
1. Supprimer toutes les réservations associées à la salle (`DELETE FROM reservations WHERE salle_id = ?`).
2. Supprimer la salle (`DELETE FROM salles WHERE id = ?`).

#### Requête SQL :
```sql
-- Étape 1 : Supprimer les réservations
DELETE FROM reservations WHERE salle_id = ?;

-- Étape 2 : Supprimer la salle
DELETE FROM salles WHERE id = ?;
```

#### Exemple en Python :
```python
def supprimer_salle(salle_id: int):
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    
    # Vérifier que la salle existe
    cursor.execute("SELECT * FROM salles WHERE id = ?", (salle_id,))
    if not cursor.fetchone():
        raise ValueError(f"Salle avec ID {salle_id} introuvable.")
    
    # Supprimer les réservations associées
    cursor.execute("DELETE FROM reservations WHERE salle_id = ?", (salle_id,))
    
    # Supprimer la salle
    cursor.execute("DELETE FROM salles WHERE id = ?", (salle_id,))
    conn.commit()
    conn.close()
```

---

### 4️⃣ **Lister les salles**
#### Requêtes SQL utiles :
- **Toutes les salles** :
  ```sql
  SELECT * FROM salles ORDER BY nom;
  ```
- **Salles avec capacité > X** :
  ```sql
  SELECT * FROM salles WHERE capacite >= ? ORDER BY capacite DESC;
  ```
- **Salles avec réservations** :
  ```sql
  SELECT s.*, COUNT(r.id) AS reservations_count 
  FROM salles s 
  LEFT JOIN reservations r ON s.id = r.salle_id 
  GROUP BY s.id 
  HAVING reservations_count > 0;
  ```
- **Salles disponibles pour une date/horaire** :
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

## Outils recommandés
| Outil | Utilisation |
|-------|-------------|
| `bash` | Exécuter `sqlite3 data.db "SELECT * FROM salles;"` |
| `read_file` | Lire `base.sql` pour vérifier le schéma |
| `edit` | Modifier `app.py` pour ajouter des endpoints/flux |
| `run_typescript` | Manipuler des données via des outils |

---

## Exemples de commandes SQLite3
```bash
# Lister toutes les salles
sqlite3 data.db "SELECT * FROM salles;"

# Ajouter une salle
sqlite3 data.db "INSERT INTO salles (nom, capacite) VALUES ('Salle C', 25);"

# Supprimer une salle (et ses réservations)
sqlite3 data.db "DELETE FROM reservations WHERE salle_id = 3; DELETE FROM salles WHERE id = 3;"

# Vérifier le schéma
sqlite3 data.db ".schema salles"
```

---

## Erreurs courantes
❌ **Oublier la suppression en cascade** : Supprimer une salle sans supprimer ses réservations → **erreur de contrainte** (si `FOREIGN KEY` est activé).
❌ **Capacité <= 0** : Toujours vérifier que `capacite > 0`.
❌ **Ne pas vérifier l’existence** : Toujours vérifier que la salle existe avant de la modifier/supprimer.

---

## Intégration avec Flask/Streamlit
### Flask (exemple d’API) :
```python
from flask import Flask, request, jsonify
import sqlite3

app = Flask(__name__)

@app.route('/salles', methods=['POST'])
def ajouter_salle_flask():
    data = request.json
    nom = data.get('nom')
    capacite = data.get('capacite')
    try:
        salle_id = ajouter_salle(nom, capacite)
        return jsonify({"id": salle_id, "nom": nom, "capacite": capacite}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

@app.route('/salles/<int:salle_id>', methods=['DELETE'])
def supprimer_salle_flask(salle_id):
    try:
        supprimer_salle(salle_id)
        return jsonify({"message": f"Salle {salle_id} supprimée avec succès."}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
```

### Streamlit (exemple d’interface) :
```python
import streamlit as st
import sqlite3

st.title("Gestion des salles")

# Ajouter une salle
with st.form("ajouter_salle"):
    nom = st.text_input("Nom de la salle")
    capacite = st.number_input("Capacité", min_value=1, step=1)
    if st.form_submit_button("Ajouter"):
        try:
            salle_id = ajouter_salle(nom, capacite)
            st.success(f"Salle '{nom}' ajoutée avec ID {salle_id} !")
        except ValueError as e:
            st.error(str(e))

# Lister les salles
st.subheader("Liste des salles")
conn = sqlite3.connect('data.db')
cursor = conn.cursor()
cursor.execute("SELECT * FROM salles")
salles = cursor.fetchall()
for salle in salles:
    st.write(f"ID: {salle[0]}, Nom: {salle[1]}, Capacité: {salle[2]}")
conn.close()
```
