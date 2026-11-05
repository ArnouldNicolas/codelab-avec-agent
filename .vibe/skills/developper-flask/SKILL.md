---
name: developper-flask
description: Charger cette skill quand l'utilisateur veut développer, modifier ou déboguer l'application Flask du projet de réservation universitaire.
user-invocable: true
---

# Développement avec Flask pour la Réservation de Salles

## Quand l'utiliser ?
- **Créer une nouvelle application Flask** pour le projet.
- **Ajouter des routes** (ex: `/salles`, `/reservations`).
- **Intégrer la base de données** (SQLite) avec Flask.
- **Gérer les requêtes** (GET, POST, PUT, DELETE).
- **Afficher des pages HTML** (avec Jinja2).
- **Déboguer l'application** Flask.

---

## Structure du projet Flask
```
code-flask/
├── app.py              # Point d'entrée de l'application
├── base.sql            # Schéma de la base de données
├── data.db             # Base de données SQLite (générée)
├── templates/          # Fichiers HTML (Jinja2)
│   ├── index.html
│   ├── salles.html
│   └── reservations.html
├── static/             # Fichiers statiques (CSS, JS, images)
│   ├── style.css
│   └── script.js
└── requirements.txt    # Dépendances Python
```

---

## Configuration de base

### 1️⃣ **Fichier `requirements.txt`**
```
Flask>=2.0.0
pytest>=7.0.0
python-dotenv>=0.19.0  # Optionnel, pour gérer les variables d'environnement
```

### 2️⃣ **Installer les dépendances**
```bash
pip install -r requirements.txt
```

### 3️⃣ **Structure minimale de `app.py`**
```python
from flask import Flask, render_template, request, redirect, url_for, jsonify
import sqlite3
import os
from datetime import datetime, time, date

app = Flask(__name__)

# Configuration
DATABASE = 'data.db'


def get_db():
    """Ouvre une connexion à la base de données."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Permet d'accéder aux colonnes par nom
    conn.execute("PRAGMA foreign_keys = ON")  # Active les clés étrangères
    return conn


def init_db():
    """Initialise la base de données à partir de base.sql."""
    if not os.path.exists(DATABASE):
        conn = get_db()
        with open('base.sql', 'r') as f:
            conn.executescript(f.read())
        conn.close()


def close_db(conn):
    """Ferme la connexion à la base de données."""
    conn.close()


# Initialiser la base au démarrage
with app.app_context():
    init_db()


if __name__ == '__main__':
    app.run(debug=True)
```

---

## Routes Flask par fonctionnalité

### 1️⃣ **Routes pour les salles**

#### **Lister les salles (GET `/salles`)**
```python
@app.route('/salles')
def liste_salles():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM salles ORDER BY nom")
    salles = cursor.fetchall()
    close_db(conn)
    return render_template('salles.html', salles=salles)
```

#### **Formulaire pour ajouter une salle (GET `/salles/ajouter`)**
```python
@app.route('/salles/ajouter', methods=['GET'])
def formulaire_ajouter_salle():
    return render_template('ajouter_salle.html')
```

#### **Ajouter une salle (POST `/salles`)**
```python
@app.route('/salles', methods=['POST'])
def ajouter_salle():
    nom = request.form.get('nom')
    capacite = int(request.form.get('capacite'))
    
    if not nom or capacite <= 0:
        return render_template('ajouter_salle.html', erreur="Nom et capacité (positive) requis"), 400
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO salles (nom, capacite) VALUES (?, ?)", (nom, capacite))
        conn.commit()
        return redirect(url_for('liste_salles'))
    except sqlite3.IntegrityError as e:
        return render_template('ajouter_salle.html', erreur=f"Erreur : {e}"), 400
    finally:
        close_db(conn)
```

#### **Supprimer une salle (POST `/salles/<int:salle_id>/supprimer`)**
```python
@app.route('/salles/<int:salle_id>/supprimer', methods=['POST'])
def supprimer_salle(salle_id):
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Vérifier que la salle existe
        cursor.execute("SELECT * FROM salles WHERE id = ?", (salle_id,))
        if not cursor.fetchone():
            return jsonify({"error": "Salle introuvable"}), 404
        
        # Supprimer la salle (et ses réservations via ON DELETE CASCADE)
        cursor.execute("DELETE FROM salles WHERE id = ?", (salle_id,))
        conn.commit()
        return redirect(url_for('liste_salles'))
    finally:
        close_db(conn)
```

---

### 2️⃣ **Routes pour les réservations**

#### **Lister les réservations (GET `/reservations`)**
```python
@app.route('/reservations')
def liste_reservations():
    conn = get_db()
    cursor = conn.cursor()
    
    # Récupérer toutes les réservations avec le nom de la salle
    cursor.execute("""
        SELECT r.*, s.nom as salle_nom, s.capacite as salle_capacite
        FROM reservations r
        JOIN salles s ON r.salle_id = s.id
        ORDER BY r.date, r.heure_debut
    """)
    reservations = cursor.fetchall()
    close_db(conn)
    return render_template('reservations.html', reservations=reservations)
```

#### **Formulaire pour ajouter une réservation (GET `/reservations/ajouter`)**
```python
@app.route('/reservations/ajouter', methods=['GET'])
def formulaire_ajouter_reservation():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM salles ORDER BY nom")
    salles = cursor.fetchall()
    close_db(conn)
    return render_template('ajouter_reservation.html', salles=salles)
```

#### **Ajouter une réservation (POST `/reservations`)**
```python
from datetime import time as dt_time

@app.route('/reservations', methods=['POST'])
def ajouter_reservation():
    salle_id = int(request.form.get('salle_id'))
    date_str = request.form.get('date')
    heure_debut_str = request.form.get('heure_debut')
    heure_fin_str = request.form.get('heure_fin')
    nom = request.form.get('nom')
    participants = int(request.form.get('participants'))
    
    # Convertir les strings en objets Python
    try:
        date_obj = date.fromisoformat(date_str)
        heure_debut = dt_time.fromisoformat(heure_debut_str)
        heure_fin = dt_time.fromisoformat(heure_fin_str)
    except ValueError:
        return render_template('ajouter_reservation.html', 
                               salles=get_salles(), 
                               erreur="Format de date ou d'heure invalide"), 400
    
    # Vérifier les règles métier
    if not (dt_time(8, 0) <= heure_debut <= dt_time(20, 0) and 
            dt_time(8, 0) <= heure_fin <= dt_time(20, 0)):
        return render_template('ajouter_reservation.html', 
                               salles=get_salles(), 
                               erreur="Les réservations doivent être entre 8h et 20h"), 400
    
    duree_heures = (heure_fin.hour - heure_debut.hour) + (heure_fin.minute - heure_debut.minute) / 60
    if not (0.5 <= duree_heures <= 4):
        return render_template('ajouter_reservation.html', 
                               salles=get_salles(), 
                               erreur="La durée doit être entre 30 min et 4h"), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Vérifier que la salle existe et que la capacité est suffisante
        cursor.execute("SELECT capacite FROM salles WHERE id = ?", (salle_id,))
        salle = cursor.fetchone()
        if not salle:
            return render_template('ajouter_reservation.html', 
                                   salles=get_salles(), 
                                   erreur="Salle introuvable"), 400
        if salle[0] < participants:
            return render_template('ajouter_reservation.html', 
                                   salles=get_salles(), 
                                   erreur=f"Capacité de la salle insuffisante (max: {salle[0]})"), 400
        
        # Vérifier les conflits
        cursor.execute("""
            SELECT id FROM reservations 
            WHERE salle_id = ? AND date = ? AND (
                (heure_debut <= ? AND heure_fin > ?) OR 
                (heure_debut < ? AND heure_fin >= ?)
            )
        """, (salle_id, date_obj, heure_debut, heure_debut, heure_fin, heure_fin))
        
        if cursor.fetchone():
            return render_template('ajouter_reservation.html', 
                                   salles=get_salles(), 
                                   erreur="La salle est déjà réservée à cet horaire"), 400
        
        # Ajouter la réservation
        cursor.execute("""
            INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (salle_id, date_obj, heure_debut, heure_fin, nom, participants))
        conn.commit()
        return redirect(url_for('liste_reservations'))
    except Exception as e:
        return render_template('ajouter_reservation.html', 
                               salles=get_salles(), 
                               erreur=f"Erreur : {e}"), 400
    finally:
        close_db(conn)


def get_salles():
    """Helper pour récupérer la liste des salles."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM salles ORDER BY nom")
    salles = cursor.fetchall()
    close_db(conn)
    return salles
```

#### **Supprimer une réservation (POST `/reservations/<int:reservation_id>/supprimer`)**
```python
@app.route('/reservations/<int:reservation_id>/supprimer', methods=['POST'])
def supprimer_reservation(reservation_id):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM reservations WHERE id = ?", (reservation_id,))
        if cursor.rowcount == 0:
            return jsonify({"error": "Réservation introuvable"}), 404
        conn.commit()
        return redirect(url_for('liste_reservations'))
    finally:
        close_db(conn)
```

---

### 3️⃣ **Routes API (pour une application frontend séparée)**

#### **API : Lister les salles (GET `/api/salles`)**
```python
@app.route('/api/salles', methods=['GET'])
def api_liste_salles():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM salles ORDER BY nom")
    salles = [dict(row) for row in cursor.fetchall()]
    close_db(conn)
    return jsonify(salles)
```

#### **API : Ajouter une salle (POST `/api/salles`)**
```python
@app.route('/api/salles', methods=['POST'])
def api_ajouter_salle():
    data = request.get_json()
    if not data or 'nom' not in data or 'capacite' not in data:
        return jsonify({"error": "Nom et capacité requis"}), 400
    
    nom = data['nom']
    capacite = data['capacite']
    
    if capacite <= 0:
        return jsonify({"error": "La capacité doit être positive"}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO salles (nom, capacite) VALUES (?, ?)", (nom, capacite))
        salle_id = cursor.lastrowid
        conn.commit()
        return jsonify({"id": salle_id, "nom": nom, "capacite": capacite}), 201
    except sqlite3.IntegrityError as e:
        return jsonify({"error": str(e)}), 400
    finally:
        close_db(conn)
```

#### **API : Lister les réservations (GET `/api/reservations`)**
```python
@app.route('/api/reservations', methods=['GET'])
def api_liste_reservations():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.*, s.nom as salle_nom, s.capacite as salle_capacite
        FROM reservations r
        JOIN salles s ON r.salle_id = s.id
        ORDER BY r.date, r.heure_debut
    """)
    reservations = []
    for row in cursor.fetchall():
        reservation = dict(row)
        # Convertir les objets date/time en strings pour JSON
        reservation['date'] = reservation['date'].isoformat()
        reservation['heure_debut'] = reservation['heure_debut'].isoformat()
        reservation['heure_fin'] = reservation['heure_fin'].isoformat()
        reservations.append(reservation)
    close_db(conn)
    return jsonify(reservations)
```

#### **API : Ajouter une réservation (POST `/api/reservations`)**
```python
from datetime import time as dt_time

@app.route('/api/reservations', methods=['POST'])
def api_ajouter_reservation():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Données manquantes"}), 400
    
    required_fields = ['salle_id', 'date', 'heure_debut', 'heure_fin', 'nom', 'participants']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Champ {field} manquant"}), 400
    
    try:
        salle_id = data['salle_id']
        date_obj = date.fromisoformat(data['date'])
        heure_debut = dt_time.fromisoformat(data['heure_debut'])
        heure_fin = dt_time.fromisoformat(data['heure_fin'])
        nom = data['nom']
        participants = data['participants']
    except (ValueError, KeyError) as e:
        return jsonify({"error": f"Format de données invalide : {e}"}), 400
    
    # Vérifier les règles métier
    if not (dt_time(8, 0) <= heure_debut <= dt_time(20, 0) and 
            dt_time(8, 0) <= heure_fin <= dt_time(20, 0)):
        return jsonify({"error": "Les réservations doivent être entre 8h et 20h"}), 400
    
    duree_heures = (heure_fin.hour - heure_debut.hour) + (heure_fin.minute - heure_debut.minute) / 60
    if not (0.5 <= duree_heures <= 4):
        return jsonify({"error": "La durée doit être entre 30 min et 4h"}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Vérifier que la salle existe
        cursor.execute("SELECT capacite FROM salles WHERE id = ?", (salle_id,))
        salle = cursor.fetchone()
        if not salle:
            return jsonify({"error": "Salle introuvable"}), 404
        if salle[0] < participants:
            return jsonify({"error": f"Capacité de la salle insuffisante (max: {salle[0]})"}), 400
        
        # Vérifier les conflits
        cursor.execute("""
            SELECT id FROM reservations 
            WHERE salle_id = ? AND date = ? AND (
                (heure_debut <= ? AND heure_fin > ?) OR 
                (heure_debut < ? AND heure_fin >= ?)
            )
        """, (salle_id, date_obj, heure_debut, heure_debut, heure_fin, heure_fin))
        
        if cursor.fetchone():
            return jsonify({"error": "La salle est déjà réservée à cet horaire"}), 409
        
        # Ajouter la réservation
        cursor.execute("""
            INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (salle_id, date_obj, heure_debut, heure_fin, nom, participants))
        reservation_id = cursor.lastrowid
        conn.commit()
        
        return jsonify({
            "id": reservation_id,
            "salle_id": salle_id,
            "date": date_obj.isoformat(),
            "heure_debut": heure_debut.isoformat(),
            "heure_fin": heure_fin.isoformat(),
            "nom": nom,
            "participants": participants
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        close_db(conn)
```

---

## Templates Jinja2

### 1️⃣ **`templates/base.html` (Template de base)**
```html
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Réservation de Salles{% endblock %}</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
    <header>
        <h1>Réservation de Salles</h1>
        <nav>
            <a href="{{ url_for('liste_salles') }}">Salles</a> |
            <a href="{{ url_for('liste_reservations') }}">Réservations</a> |
            <a href="{{ url_for('formulaire_ajouter_reservation') }}">Nouvelle Réservation</a>
        </nav>
    </header>
    <main>
        {% block content %}{% endblock %}
    </main>
    <footer>
        <p>© 2025 - Université</p>
    </footer>
</body>
</html>
```

### 2️⃣ **`templates/salles.html` (Liste des salles)**
```html
{% extends "base.html" %}

{% block title %}Liste des Salles{% endblock %}

{% block content %}
<h2>Liste des Salles</h2>
{% if erreur %}
    <div class="erreur">{{ erreur }}</div>
{% endif %}

<a href="{{ url_for('formulaire_ajouter_salle') }}" class="bouton">Ajouter une salle</a>

<table>
    <thead>
        <tr>
            <th>ID</th>
            <th>Nom</th>
            <th>Capacité</th>
            <th>Actions</th>
        </tr>
    </thead>
    <tbody>
        {% for salle in salles %}
        <tr>
            <td>{{ salle.id }}</td>
            <td>{{ salle.nom }}</td>
            <td>{{ salle.capacite }}</td>
            <td>
                <form action="{{ url_for('supprimer_salle', salle_id=salle.id) }}" method="POST" 
                      onsubmit="return confirm('Êtes-vous sûr de vouloir supprimer cette salle et toutes ses réservations ?');">
                    <button type="submit" class="bouton-supprimer">Supprimer</button>
                </form>
            </td>
        </tr>
        {% endfor %}
    </tbody>
</table>
{% endblock %}
```

### 3️⃣ **`templates/ajouter_salle.html` (Formulaire d’ajout de salle)**
```html
{% extends "base.html" %}

{% block title %}Ajouter une Salle{% endblock %}

{% block content %}
<h2>Ajouter une Salle</h2>
{% if erreur %}
    <div class="erreur">{{ erreur }}</div>
{% endif %}

<form method="POST" action="{{ url_for('ajouter_salle') }}">
    <label for="nom">Nom :</label>
    <input type="text" id="nom" name="nom" required>
    
    <label for="capacite">Capacité :</label>
    <input type="number" id="capacite" name="capacite" min="1" required>
    
    <button type="submit" class="bouton">Ajouter</button>
    <a href="{{ url_for('liste_salles') }}" class="bouton-annuler">Annuler</a>
</form>
{% endblock %}
```

### 4️⃣ **`templates/reservations.html` (Liste des réservations)**
```html
{% extends "base.html" %}

{% block title %}Liste des Réservations{% endblock %}

{% block content %}
<h2>Liste des Réservations</h2>
{% if erreur %}
    <div class="erreur">{{ erreur }}</div>
{% endif %}

<a href="{{ url_for('formulaire_ajouter_reservation') }}" class="bouton">Nouvelle Réservation</a>

<table>
    <thead>
        <tr>
            <th>ID</th>
            <th>Salle</th>
            <th>Date</th>
            <th>Heure</th>
            <th>Nom</th>
            <th>Participants</th>
            <th>Actions</th>
        </tr>
    </thead>
    <tbody>
        {% for reservation in reservations %}
        <tr>
            <td>{{ reservation.id }}</td>
            <td>{{ reservation.salle_nom }} ({{ reservation.salle_capacite }})</td>
            <td>{{ reservation.date }}</td>
            <td>{{ reservation.heure_debut }} - {{ reservation.heure_fin }}</td>
            <td>{{ reservation.nom }}</td>
            <td>{{ reservation.participants }}</td>
            <td>
                <form action="{{ url_for('supprimer_reservation', reservation_id=reservation.id) }}" method="POST" 
                      onsubmit="return confirm('Êtes-vous sûr de vouloir supprimer cette réservation ?');">
                    <button type="submit" class="bouton-supprimer">Supprimer</button>
                </form>
            </td>
        </tr>
        {% endfor %}
    </tbody>
</table>
{% endblock %}
```

### 5️⃣ **`templates/ajouter_reservation.html` (Formulaire d’ajout de réservation)**
```html
{% extends "base.html" %}

{% block title %}Ajouter une Réservation{% endblock %}

{% block content %}
<h2>Ajouter une Réservation</h2>
{% if erreur %}
    <div class="erreur">{{ erreur }}</div>
{% endif %}

<form method="POST" action="{{ url_for('ajouter_reservation') }}">
    <label for="salle_id">Salle :</label>
    <select id="salle_id" name="salle_id" required>
        <option value="">-- Sélectionnez une salle --</option>
        {% for salle in salles %}
        <option value="{{ salle.id }}">{{ salle.nom }} (Capacité: {{ salle.capacite }})</option>
        {% endfor %}
    </select>
    
    <label for="date">Date :</label>
    <input type="date" id="date" name="date" required>
    
    <label for="heure_debut">Heure de début :</label>
    <input type="time" id="heure_debut" name="heure_debut" min="08:00" max="19:30" required>
    
    <label for="heure_fin">Heure de fin :</label>
    <input type="time" id="heure_fin" name="heure_fin" min="08:30" max="20:00" required>
    
    <label for="nom">Nom :</label>
    <input type="text" id="nom" name="nom" required>
    
    <label for="participants">Participants :</label>
    <input type="number" id="participants" name="participants" min="1" required>
    
    <button type="submit" class="bouton">Réserver</button>
    <a href="{{ url_for('liste_reservations') }}" class="bouton-annuler">Annuler</a>
</form>

<script>
// Limiter l'heure de fin en fonction de l'heure de début (max 4h)
document.getElementById('heure_debut').addEventListener('change', function() {
    const debut = new Date(`1970-01-01T${this.value}`);
    const maxFin = new Date(debut.getTime() + 4 * 60 * 60 * 1000); // +4h
    const maxFinStr = maxFin.toISOString().substr(11, 5);
    document.getElementById('heure_fin').max = maxFinStr;
    
    // Si l'heure de fin est déjà définie et > maxFin, la réinitialiser
    if (document.getElementById('heure_fin').value > maxFinStr) {
        document.getElementById('heure_fin').value = maxFinStr;
    }
});

// Limiter l'heure de fin à 20:00
document.getElementById('heure_fin').addEventListener('change', function() {
    if (this.value > '20:00') {
        this.value = '20:00';
    }
});
</script>
{% endblock %}
```

---

## CSS de base (`static/style.css`)
```css
/* Réinitialisation */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: Arial, sans-serif;
    line-height: 1.6;
    color: #333;
    background-color: #f4f4f4;
    padding: 20px;
}

header {
    background-color: #4CAF50;
    color: white;
    padding: 10px 20px;
    margin-bottom: 20px;
    text-align: center;
}

header h1 {
    margin-bottom: 10px;
}

header nav a {
    color: white;
    margin: 0 10px;
    text-decoration: none;
}

header nav a:hover {
    text-decoration: underline;
}

main {
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
    background-color: white;
    box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
}

h2 {
    margin-bottom: 20px;
    color: #4CAF50;
}

/* Tableaux */
table {
    width: 100%;
    border-collapse: collapse;
    margin: 20px 0;
}

table, th, td {
    border: 1px solid #ddd;
}

th, td {
    padding: 10px;
    text-align: left;
}

th {
    background-color: #f2f2f2;
}

tr:nth-child(even) {
    background-color: #f9f9f9;
}

tr:hover {
    background-color: #f1f1f1;
}

/* Formulaires */
form {
    display: flex;
    flex-direction: column;
    max-width: 500px;
    margin: 20px 0;
}

form label {
    margin: 10px 0 5px;
    font-weight: bold;
}

form input,
form select {
    padding: 10px;
    border: 1px solid #ddd;
    border-radius: 4px;
    font-size: 16px;
}

form input[type="date"],
form input[type="time"] {
    width: auto;
}

.bouton {
    background-color: #4CAF50;
    color: white;
    padding: 10px 15px;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 16px;
    margin-top: 10px;
    width: auto;
}

.bouton:hover {
    background-color: #45a049;
}

.bouton-supprimer {
    background-color: #f44336;
    color: white;
    padding: 5px 10px;
    border: none;
    border-radius: 4px;
    cursor: pointer;
}

.bouton-supprimer:hover {
    background-color: #d32f2f;
}

.bouton-annuler {
    background-color: #f44336;
    color: white;
    padding: 10px 15px;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 16px;
    margin-top: 10px;
    text-decoration: none;
    display: inline-block;
    width: auto;
}

.bouton-annuler:hover {
    background-color: #d32f2f;
}

/* Messages d'erreur */
.erreur {
    color: #f44336;
    background-color: #ffebee;
    padding: 10px;
    border-radius: 4px;
    margin: 10px 0;
    border: 1px solid #f44336;
}

/* Footer */
footer {
    text-align: center;
    margin-top: 20px;
    padding: 10px;
    color: #666;
}
```

---

## Lancer l’application

### En mode développement (avec rechargement automatique) :
```bash
python app.py
```

### En mode production (avec Waitress ou Gunicorn) :
```bash
# Installer Waitress
pip install waitress

# Lancer avec Waitress
waitress-serve --port=5000 app:app
```

---

## Déboguer l’application Flask

### 1️⃣ **Mode debug** :
Active le rechargement automatique et affiche les erreurs dans le navigateur :
```python
if __name__ == '__main__':
    app.run(debug=True)  # Mode debug activé
```

### 2️⃣ **Logs** :
Pour afficher les logs des requêtes HTTP :
```python
import logging

logging.basicConfig(level=logging.DEBUG)
app.logger.setLevel(logging.DEBUG)
```

### 3️⃣ **Débogueur Python (pdb)** :
Ajouter un point d’arrêt dans le code :
```python
from pdb import set_trace

@app.route('/salles')
def liste_salles():
    set_trace()  # Point d'arrêt ici
    conn = get_db()
    # ...
```

### 4️⃣ **Vérifier les erreurs courantes** :
| Erreur | Cause | Solution |
|--------|-------|----------|
| `sqlite3.OperationalError: no such table` | La table n’existe pas dans `data.db`. | Vérifier que `base.sql` est correct et que `init_db()` a été appelé. |
| `404 Not Found` | Route inexistante. | Vérifier les `@app.route()` et les URLs. |
| `500 Internal Server Error` | Erreur dans le code Python. | Lire les logs pour voir le traceback. |
| `405 Method Not Allowed` | Méthode HTTP incorrecte (ex: POST au lieu de GET). | Vérifier les `methods` dans `@app.route()`. |

---

## Bonnes pratiques Flask
✅ **Utiliser `app_context`** :
   - Toujours utiliser `with app.app_context():` pour les opérations qui nécessitent le contexte Flask (ex: accès à `g.db`).

✅ **Fermer les connexions SQLite** :
   - Toujours fermer les connexions avec `close_db(conn)` pour éviter les fuites de mémoire.

✅ **Valider les entrées utilisateur** :
   - Toujours vérifier et valider les données du formulaire ou de l’API.

✅ **Utiliser des templates** :
   - Séparer la logique (Python) de la présentation (HTML) avec Jinja2.

✅ **Gérer les erreurs** :
   - Utiliser `try/except` pour capturer les erreurs SQLite et Flask.

✅ **Activer les `FOREIGN KEY`** :
   - Toujours exécuter `PRAGMA foreign_keys = ON` après la connexion.

✅ **Utiliser des transactions** :
   - Pour les opérations critiques (ex: ajouter une réservation), utiliser des transactions.

---

## Erreurs courantes à éviter
❌ **Ne pas fermer les connexions SQLite** → **Fuites de mémoire** et erreurs "database is locked".

❌ **Oublier `app_context`** → Erreur "Working outside of application context".

❌ **Ne pas valider les entrées** → Risques de sécurité (SQL injection) ou de données invalides.

❌ **Utiliser des requêtes SQL non paramétrées** → **Risque de SQL injection**.
   - ❌ `cursor.execute(f"SELECT * FROM salles WHERE nom = '{nom}'")`
   - ✅ `cursor.execute("SELECT * FROM salles WHERE nom = ?", (nom,))`

❌ **Ne pas gérer les erreurs** → L’application plante avec un `500 Internal Server Error`.

❌ **Oublier `PRAGMA foreign_keys = ON`** → Les contraintes de clé étrangère ne sont pas vérifiées.

---

## Exemple complet de `app.py`
Voici un exemple complet avec toutes les fonctionnalités :
[Lien vers un exemple complet](#) *(à créer si besoin)*

---

## Outils recommandés
| Outil | Utilisation |
|-------|-------------|
| `Flask` | Framework web principal. |
| `sqlite3` | Gestion de la base de données. |
| `Jinja2` | Moteur de templates (inclus avec Flask). |
| `pytest` | Tests unitaires. |
| `Waitress`/`Gunicorn` | Serveurs de production. |
| `Flask-DebugToolbar` | Barre d’outils de débogage (optionnel). |

---

## Ressources utiles
- [Documentation Flask](https://flask.palletsprojects.com/) (officielle)
- [SQLite et Flask](https://flask.palletsprojects.com/en/2.0.x/patterns/sqlite3/)
- [Jinja2 Template Designer Documentation](https://jinja.palletsprojects.com/en/3.0.x/templates/)
- [Bootstrap pour le CSS](https://getbootstrap.com/) (optionnel)
