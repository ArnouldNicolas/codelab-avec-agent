---
name: gerer-reservations
description: Charger cette skill quand l'utilisateur veut ajouter, modifier, supprimer ou lister une réservation dans le projet de réservation universitaire.
user-invocable: true
---

# Gestion des réservations

## Quand l'utiliser ?
- **Ajouter une réservation** (ex: "Réserve la salle 1 pour le 15/01/2025 de 10h à 11h30").
- **Modifier une réservation existante** (ex: "Change l'heure de la réservation 5 à 14h-15h").
- **Supprimer une réservation** (ex: "Annule la réservation n°3").
- **Lister les réservations** (ex: "Affiche les réservations pour demain").
- **Vérifier les conflits** (ex: "Est-ce que la salle 2 est libre le 20/01 de 14h à 16h ?").

---

## Règles métier (À RESPECTER ABSOLUMENT)
1. **Pas de chevauchement** : Deux réservations pour une même salle ne peuvent pas se chevaucher.
   - ✅ **Autorisé** : Finir à 12h00 et commencer à 12h00.
   - ❌ **Interdit** : 10h-11h30 et 11h-12h pour la même salle.
2. **Capacité** : Le nombre de participants **ne doit pas dépasser** la capacité de la salle.
3. **Horaires** :
   - Réservations **uniquement entre 8h00 et 20h00**.
   - Durée **minimale** : 30 minutes.
   - Durée **maximale** : 4 heures.
4. **Dates** : La semaine va du **lundi au dimanche** (pas de contrainte sur les jours fériés).
5. **Pas d'authentification** : Pas de gestion des utilisateurs.

---

## Structure de la table `reservations` (SQLite)
| Champ | Type | Description | Exemple |
|-------|------|-------------|---------|
| `id` | INTEGER | Clé primaire (auto-incrémentée) | `1` |
| `salle_id` | INTEGER | ID de la salle (clé étrangère) | `1` |
| `date` | DATE | Date de la réservation | `"2025-01-15"` |
| `heure_debut` | TIME | Heure de début | `"10:00:00"` |
| `heure_fin` | TIME | Heure de fin | `"11:30:00"` |
| `nom` | TEXT | Nom de la réservation (ex: "Réunion", "Cours") | `"Réunion équipe"` |
| `participants` | INTEGER | Nombre de participants | `10` |

---

## Instructions par action

### 1️⃣ **Ajouter une réservation**
#### Étapes :
1. **Vérifier la salle** :
   - Vérifier que `salle_id` existe dans `salles`.
   - Vérifier que `participants <= capacite` de la salle.
2. **Vérifier les horaires** :
   - `heure_debut` et `heure_fin` entre **08:00 et 20:00**.
   - Durée (`heure_fin - heure_debut`) entre **0.5h et 4h**.
3. **Vérifier les conflits** :
   - Aucune autre réservation pour la même salle ne doit chevaucher les horaires.
4. **Insérer la réservation**.

#### Requête SQL pour vérifier les conflits :
```sql
SELECT * FROM reservations 
WHERE salle_id = ? AND date = ? AND (
    (heure_debut <= ? AND heure_fin > ?) OR  -- Nouvelle réservation commence pendant une existante
    (heure_debut < ? AND heure_fin >= ?)     -- Nouvelle réservation finit pendant une existante
);
```
*Paramètres :* `salle_id`, `date`, `heure_debut`, `heure_debut`, `heure_fin`, `heure_fin`

#### Requête SQL pour ajouter :
```sql
INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
VALUES (?, ?, ?, ?, ?, ?);
```

#### Exemple en Python :
```python
from datetime import time, date
import sqlite3

def ajouter_reservation(salle_id: int, date_obj: date, heure_debut: time, heure_fin: time, nom: str, participants: int) -> int:
    # Vérifier les horaires
    if not (time(8, 0) <= heure_debut <= time(20, 0) and time(8, 0) <= heure_fin <= time(20, 0)):
        raise ValueError("Les réservations doivent être entre 8h00 et 20h00.")
    
    # Vérifier la durée (en heures)
    duree_heures = (heure_fin.hour - heure_debut.hour) + (heure_fin.minute - heure_debut.minute) / 60
    if not (0.5 <= duree_heures <= 4):
        raise ValueError("La durée doit être entre 30 minutes et 4 heures.")
    
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    
    # Vérifier que la salle existe et que la capacité est suffisante
    cursor.execute("SELECT capacite FROM salles WHERE id = ?", (salle_id,))
    salle = cursor.fetchone()
    if not salle:
        raise ValueError(f"Salle avec ID {salle_id} introuvable.")
    if salle[0] < participants:
        raise ValueError(f"Capacité de la salle insuffisante (max: {salle[0]} participants).")
    
    # Vérifier les conflits
    cursor.execute("""
        SELECT id FROM reservations 
        WHERE salle_id = ? AND date = ? AND (
            (heure_debut <= ? AND heure_fin > ?) OR 
            (heure_debut < ? AND heure_fin >= ?)
        )
    """, (salle_id, date_obj, heure_debut, heure_debut, heure_fin, heure_fin))
    
    if cursor.fetchone():
        raise ValueError("Conflit de réservation : la salle est déjà réservée à cet horaire.")
    
    # Ajouter la réservation
    cursor.execute("""
        INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (salle_id, date_obj, heure_debut, heure_fin, nom, participants))
    
    reservation_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return reservation_id
```

---

### 2️⃣ **Modifier une réservation**
#### Étapes :
1. **Récupérer l’ancienne réservation**.
2. **Supprimer l’ancienne réservation** (pour éviter les conflits pendant la modification).
3. **Ajouter une nouvelle réservation** avec les nouvelles valeurs (en réutilisant la fonction `ajouter_reservation`).

#### Exemple en Python :
```python
def modifier_reservation(
    reservation_id: int,
    nouvelle_salle_id: int = None,
    nouvelle_date: date = None,
    nouvelle_heure_debut: time = None,
    nouvelle_heure_fin: time = None,
    nouveau_nom: str = None,
    nouveaux_participants: int = None
) -> int:
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    
    # Récupérer l'ancienne réservation
    cursor.execute("SELECT * FROM reservations WHERE id = ?", (reservation_id,))
    ancienne_reservation = cursor.fetchone()
    if not ancienne_reservation:
        raise ValueError(f"Réservation avec ID {reservation_id} introuvable.")
    
    # Supprimer l'ancienne réservation
    cursor.execute("DELETE FROM reservations WHERE id = ?", (reservation_id,))
    
    # Utiliser les anciennes valeurs si non spécifiées
    salle_id = nouvelle_salle_id if nouvelle_salle_id is not None else ancienne_reservation[1]
    date_obj = nouvelle_date if nouvelle_date is not None else ancienne_reservation[2]
    heure_debut = nouvelle_heure_debut if nouvelle_heure_debut is not None else ancienne_reservation[3]
    heure_fin = nouvelle_heure_fin if nouvelle_heure_fin is not None else ancienne_reservation[4]
    nom = nouveau_nom if nouveau_nom is not None else ancienne_reservation[5]
    participants = nouveaux_participants if nouveaux_participants is not None else ancienne_reservation[6]
    
    # Ajouter la nouvelle réservation (réutilise les validations)
    try:
        new_id = ajouter_reservation(salle_id, date_obj, heure_debut, heure_fin, nom, participants)
        conn.commit()
        conn.close()
        return new_id
    except Exception as e:
        # Restaurer l'ancienne réservation en cas d'erreur
        cursor.execute("""
            INSERT INTO reservations (id, salle_id, date, heure_debut, heure_fin, nom, participants)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ancienne_reservation)
        conn.commit()
        conn.close()
        raise e
```

---

### 3️⃣ **Supprimer une réservation**
#### Étapes :
1. Vérifier que la réservation existe.
2. Supprimer de la table `reservations`.

#### Requête SQL :
```sql
DELETE FROM reservations WHERE id = ?;
```

#### Exemple en Python :
```python
def supprimer_reservation(reservation_id: int):
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM reservations WHERE id = ?", (reservation_id,))
    if cursor.rowcount == 0:
        raise ValueError(f"Réservation avec ID {reservation_id} introuvable.")
    
    conn.commit()
    conn.close()
```

---

### 4️⃣ **Lister les réservations**
#### Requêtes SQL utiles :
- **Toutes les réservations** :
  ```sql
  SELECT * FROM reservations ORDER BY date, heure_debut;
  ```
- **Réservations pour une salle** :
  ```sql
  SELECT * FROM reservations WHERE salle_id = ? ORDER BY date, heure_debut;
  ```
- **Réservations pour une date** :
  ```sql
  SELECT * FROM reservations WHERE date = ? ORDER BY salle_id, heure_debut;
  ```
- **Réservations pour une salle et une date** :
  ```sql
  SELECT * FROM reservations WHERE salle_id = ? AND date = ? ORDER BY heure_debut;
  ```
- **Réservations en conflit avec une plage horaire** :
  ```sql
  SELECT * FROM reservations 
  WHERE salle_id = ? AND date = ? AND (
      (heure_debut <= ? AND heure_fin > ?) OR
      (heure_debut < ? AND heure_fin >= ?)
  );
  ```

---

## Vérification des conflits (détails techniques)
### Problème :
Deux réservations **chevauchent** si leurs plages horaires se superposent **même partiellement**. 

### Cas valides (pas de conflit) :
| Réservation 1 | Réservation 2 | Chevauchement ? |
|---------------|---------------|-----------------|
| 10h-11h | 11h-12h | ❌ Non |
| 10h-12h | 12h-14h | ❌ Non |
| 10h-11h | 11h30-12h | ❌ Non |

### Cas invalides (conflit) :
| Réservation 1 | Réservation 2 | Chevauchement ? |
|---------------|---------------|-----------------|
| 10h-11h | 10h30-12h | ✅ Oui |
| 10h-12h | 11h-13h | ✅ Oui |
| 10h-11h30 | 11h-12h | ✅ Oui |

### Requête SQL optimisée :
```sql
-- Pour vérifier si une plage horaire [debut, fin] est libre pour une salle à une date
SELECT COUNT(*) FROM reservations 
WHERE salle_id = ? AND date = ? AND heure_debut < ? AND heure_fin > ?;
```
*Explication* :
- `heure_debut < nouvelle_fin` : La réservation existante commence avant la fin de la nouvelle.
- `heure_fin > nouveau_debut` : La réservation existante finit après le début de la nouvelle.
→ Si `COUNT(*) > 0`, il y a un conflit.

---

## Outils recommandés
| Outil | Utilisation |
|-------|-------------|
| `bash` | Exécuter des requêtes SQL directes (`sqlite3 data.db`). |
| `read_file` | Lire `base.sql` ou `app.py`. |
| `edit` | Modifier `app.py` pour ajouter des fonctions. |
| `run_typescript` | Manipuler des données via des outils. |
| `pytest` | Lancer les tests pour valider les règles. |

---

## Exemples de commandes SQLite3
```bash
# Lister toutes les réservations
sqlite3 data.db "SELECT * FROM reservations;"

# Vérifier les conflits pour la salle 1 le 15/01/2025 entre 10h et 11h30
sqlite3 data.db "SELECT * FROM reservations WHERE salle_id = 1 AND date = '2025-01-15' AND (heure_debut < '11:30' AND heure_fin > '10:00');"

# Supprimer une réservation
sqlite3 data.db "DELETE FROM reservations WHERE id = 5;"
```

---

## Intégration avec Flask/Streamlit
### Flask (exemple d’API) :
```python
from flask import Flask, request, jsonify
from datetime import datetime, time, date

app = Flask(__name__)

@app.route('/reservations', methods=['POST'])
def ajouter_reservation_flask():
    data = request.json
    try:
        salle_id = data['salle_id']
        date_str = data['date']
        heure_debut_str = data['heure_debut']
        heure_fin_str = data['heure_fin']
        nom = data['nom']
        participants = data['participants']
        
        # Convertir les strings en objets datetime
        date_obj = date.fromisoformat(date_str)
        heure_debut = datetime.strptime(heure_debut_str, "%H:%M").time()
        heure_fin = datetime.strptime(heure_fin_str, "%H:%M").time()
        
        reservation_id = ajouter_reservation(salle_id, date_obj, heure_debut, heure_fin, nom, participants)
        return jsonify({"id": reservation_id}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

@app.route('/reservations/<int:reservation_id>', methods=['DELETE'])
def supprimer_reservation_flask(reservation_id):
    try:
        supprimer_reservation(reservation_id)
        return jsonify({"message": f"Réservation {reservation_id} supprimée."}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
```

### Streamlit (exemple d’interface) :
```python
import streamlit as st
from datetime import time, date
import sqlite3

st.title("Gestion des réservations")

# Formulaire pour ajouter une réservation
with st.form("ajouter_reservation"):
    salle_id = st.number_input("ID de la salle", min_value=1, step=1)
    date_reservation = st.date_input("Date")
    heure_debut = st.time_input("Heure de début", value=time(10, 0))
    heure_fin = st.time_input("Heure de fin", value=time(11, 0))
    nom = st.text_input("Nom de la réservation")
    participants = st.number_input("Nombre de participants", min_value=1, step=1)
    
    if st.form_submit_button("Réserver"):
        try:
            reservation_id = ajouter_reservation(
                salle_id, date_reservation, heure_debut, heure_fin, nom, participants
            )
            st.success(f"Réservation ajoutée avec ID {reservation_id} !")
        except ValueError as e:
            st.error(str(e))

# Lister les réservations
st.subheader("Réservations existantes")
conn = sqlite3.connect('data.db')
cursor = conn.cursor()
cursor.execute("SELECT * FROM reservations ORDER BY date, heure_debut")
reservations = cursor.fetchall()

for res in reservations:
    st.write(
        f"ID: {res[0]} | Salle: {res[1]} | Date: {res[2]} | "
        f"Heure: {res[3]}-{res[4]} | Nom: {res[5]} | Participants: {res[6]}"
    )
conn.close()
```

---

## Erreurs courantes à éviter
❌ **Oublier de vérifier les conflits** : Toujours exécuter la requête de conflit avant d’ajouter une réservation.
❌ **Mauvaise gestion des horaires** : Utiliser des objets `time` et `date` (pas des strings) pour les comparaisons.
❌ **Ne pas valider la durée** : Vérifier que `0.5 <= durée <= 4`.
❌ **Ne pas vérifier la capacité** : Toujours comparer `participants <= capacite` de la salle.
❌ **Modifier sans supprimer l’ancienne réservation** : Risque de conflits si on met à jour directement.

---

## Astuces pour les tests
- **Créer un fixture pytest** pour initialiser la base de données avant chaque test.
- **Tester les cas limites** :
  - Réservations à 8h00 et 20h00.
  - Réservations de 30 min et 4h.
  - Chevauchements exacts (ex: 10h-11h et 11h-12h).
- **Tester les erreurs** :
  - Chevauchement.
  - Capacité insuffisante.
  - Horaires invalides.

*Exemple de test :*
```python
# test_reservations.py
def test_ajouter_reservation_cheauchement(setup_db):
    # Ajouter une salle
    cursor = setup_db.cursor()
    cursor.execute("INSERT INTO salles (nom, capacite) VALUES ('Salle A', 20)")
    salle_id = cursor.lastrowid
    
    # Ajouter une première réservation (10h-11h)
    ajouter_reservation(salle_id, date(2025, 1, 15), time(10, 0), time(11, 0), "Réunion 1", 10)
    
    # Essayer d'ajouter une réservation en conflit (10h30-11h30)
    with pytest.raises(ValueError, match="Conflit de réservation"):
        ajouter_reservation(salle_id, date(2025, 1, 15), time(10, 30), time(11, 30), "Réunion 2", 10)
```
