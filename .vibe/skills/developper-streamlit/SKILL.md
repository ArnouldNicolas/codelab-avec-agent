---
name: developper-streamlit
description: Charger cette skill quand l'utilisateur veut développer, modifier ou déboguer l'application Streamlit du projet de réservation universitaire.
user-invocable: true
---

# Développement avec Streamlit pour la Réservation de Salles

## Quand l'utiliser ?
- **Créer une nouvelle application Streamlit** pour le projet.
- **Ajouter des composants** (ex: sélecteurs de date, formulaires, tableaux).
- **Intégrer la base de données** (SQLite) avec Streamlit.
- **Afficher des données** sous forme de tableaux ou de graphiques.
- **Gérer les interactions utilisateur** (boutons, formulaires, filtres).
- **Déboguer l'application** Streamlit.

---

## Structure du projet Streamlit
```
code-streamlit/
├── app.py              # Point d'entrée de l'application
├── base.sql            # Schéma de la base de données
├── data.db             # Base de données SQLite (générée)
├── requirements.txt    # Dépendances Python
└── .streamlit/         # Configuration Streamlit (optionnel)
    └── config.toml
```

---

## Configuration de base

### 1️⃣ **Fichier `requirements.txt`**
```
streamlit>=1.0.0
pytest>=7.0.0
python-dotenv>=0.19.0  # Optionnel
```

### 2️⃣ **Installer les dépendances**
```bash
pip install -r requirements.txt
```

### 3️⃣ **Structure minimale de `app.py`**
```python
import streamlit as st
import sqlite3
import os
from datetime import datetime, time, date

# Configuration de la page
st.set_page_config(
    page_title="Réservation de Salles",
    page_icon="🏢",
    layout="wide"
)

# Initialisation de la base de données
DATABASE = 'data.db'

def init_db():
    """Initialise la base de données à partir de base.sql."""
    if not os.path.exists(DATABASE):
        conn = sqlite3.connect(DATABASE)
        with open('base.sql', 'r') as f:
            conn.executescript(f.read())
        conn.close()


def get_db():
    """Ouvre une connexion à la base de données."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# Initialiser la base au démarrage
init_db()
```

---

## Composants Streamlit par fonctionnalité

---

## 1️⃣ **Page d’accueil (Liste des options)**
```python
import streamlit as st

def main():
    st.title("🏢 Réservation de Salles")
    st.markdown("""
    Bienvenue dans l'application de réservation de salles.
    Utilisez le menu latéral pour naviguer.
    """)

    # Menu latéral
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Aller à :",
        ["Accueil", "Gérer les Salles", "Gérer les Réservations", "Calendrier"]
    )
    
    if page == "Accueil":
        main()
    elif page == "Gérer les Salles":
        gerer_salles()
    elif page == "Gérer les Réservations":
        gerer_reservations()
    elif page == "Calendrier":
        calendrier()


if __name__ == "__main__":
    main()
```

---

## 2️⃣ **Gestion des salles**

### **Lister les salles**
```python
def liste_salles():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM salles ORDER BY nom")
    salles = cursor.fetchall()
    conn.close()
    
    st.subheader("📋 Liste des Salles")
    
    if not salles:
        st.warning("Aucune salle trouvée. Ajoutez-en une !")
        return
    
    # Afficher sous forme de tableau
    st.dataframe(salles, use_container_width=True)
    
    # Ou sous forme de cartes
    for salle in salles:
        with st.expander(f"{salle['nom']} (Capacité: {salle['capacite']})"):
            st.write(f"ID: {salle['id']}")
            if st.button(f"Supprimer {salle['nom']}", key=f"supprimer_salle_{salle['id']}"):
                supprimer_salle(salle['id'])
                st.rerun()  # Rafraîchir la page


### **Ajouter une salle**
```python
def formulaire_ajouter_salle():
    st.subheader("➕ Ajouter une Salle")
    
    with st.form("ajouter_salle"):
        nom = st.text_input("Nom de la salle", placeholder="Ex: Amphi A")
        capacite = st.number_input("Capacité", min_value=1, step=1, value=20)
        
        if st.form_submit_button("Ajouter"):
            if not nom:
                st.error("Le nom est obligatoire !")
                return
            
            try:
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute("INSERT INTO salles (nom, capacite) VALUES (?, ?)", (nom, capacite))
                conn.commit()
                conn.close()
                st.success(f"Salle '{nom}' ajoutée avec succès !")
                st.rerun()
            except Exception as e:
                st.error(f"Erreur : {e}")


### **Supprimer une salle**
```python
def supprimer_salle(salle_id):
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Vérifier que la salle existe
        cursor.execute("SELECT nom FROM salles WHERE id = ?", (salle_id,))
        salle = cursor.fetchone()
        if not salle:
            st.error(f"Salle avec ID {salle_id} introuvable.")
            return
        
        # Supprimer la salle (et ses réservations via ON DELETE CASCADE)
        cursor.execute("DELETE FROM salles WHERE id = ?", (salle_id,))
        conn.commit()
        st.success(f"Salle '{salle['nom']}' supprimée avec succès !")
    except Exception as e:
        st.error(f"Erreur lors de la suppression : {e}")
    finally:
        conn.close()


### **Page complète pour gérer les salles**
```python
def gerer_salles():
    st.title("🏫 Gestion des Salles")
    
    # Onglets pour les actions
    tab1, tab2 = st.tabs(["Liste des Salles", "Ajouter une Salle"])
    
    with tab1:
        liste_salles()
    
    with tab2:
        formulaire_ajouter_salle()
```

---

## 3️⃣ **Gestion des réservations**

### **Lister les réservations**
```python
def liste_reservations():
    conn = get_db()
    cursor = conn.cursor()
    
    # Récupérer les réservations avec le nom de la salle
    cursor.execute("""
        SELECT r.*, s.nom as salle_nom, s.capacite as salle_capacite
        FROM reservations r
        JOIN salles s ON r.salle_id = s.id
        ORDER BY r.date, r.heure_debut
    """)
    reservations = cursor.fetchall()
    conn.close()
    
    st.subheader("📅 Liste des Réservations")
    
    if not reservations:
        st.warning("Aucune réservation trouvée.")
        return
    
    # Filtres
    col1, col2 = st.columns(2)
    with col1:
        salle_filtre = st.selectbox(
            "Filtrer par salle",
            ["Toutes"] + [salle['nom'] for salle in get_all_salles()],
            index=0
        )
    with col2:
        date_filtre = st.date_input("Filtrer par date", value=None)
    
    # Appliquer les filtres
    reservations_filtrees = []
    for res in reservations:
        if salle_filtre != "Toutes" and res['salle_nom'] != salle_filtre:
            continue
        if date_filtre and res['date'] != date_filtre:
            continue
        reservations_filtrees.append(res)
    
    # Afficher les réservations
    if reservations_filtrees:
        # Convertir en DataFrame pour un affichage propre
        import pandas as pd
        df = pd.DataFrame([dict(res) for res in reservations_filtrees])
        df['date'] = df['date'].dt.date  # Afficher seulement la date
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("Aucune réservation ne correspond aux filtres.")


### **Ajouter une réservation**
```python
def formulaire_ajouter_reservation():
    st.subheader("➕ Ajouter une Réservation")
    
    salles = get_all_salles()
    if not salles:
        st.warning("Aucune salle disponible. Ajoutez d'abord une salle !")
        return
    
    with st.form("ajouter_reservation"):
        salle_id = st.selectbox(
            "Salle",
            options=[(salle['id'], salle['nom']) for salle in salles],
            format_func=lambda x: f"{x[1]} (Capacité: {x[0]})"
        )[0]
        
        date_reservation = st.date_input("Date", min_value=date.today())
        
        col1, col2 = st.columns(2)
        with col1:
            heure_debut = st.time_input("Heure de début", value=time(10, 0), minute_step=30)
        with col2:
            heure_fin = st.time_input("Heure de fin", value=time(11, 0), minute_step=30)
        
        nom = st.text_input("Nom de la réservation", placeholder="Ex: Réunion équipe")
        participants = st.number_input("Nombre de participants", min_value=1, value=10)
        
        if st.form_submit_button("Réserver"):
            # Vérifier les règles métier
            erreurs = []
            
            # 1. Vérifier les horaires
            if not (time(8, 0) <= heure_debut <= time(20, 0) and time(8, 0) <= heure_fin <= time(20, 0)):
                erreurs.append("Les réservations doivent être entre 8h et 20h.")
            
            # 2. Vérifier la durée
            duree_heures = (heure_fin.hour - heure_debut.hour) + (heure_fin.minute - heure_debut.minute) / 60
            if not (0.5 <= duree_heures <= 4):
                erreurs.append("La durée doit être entre 30 minutes et 4 heures.")
            
            # 3. Vérifier que l'heure de fin est après l'heure de début
            if heure_fin <= heure_debut:
                erreurs.append("L'heure de fin doit être après l'heure de début.")
            
            # 4. Vérifier que le nom n'est pas vide
            if not nom:
                erreurs.append("Le nom est obligatoire.")
            
            if erreurs:
                for erreur in erreurs:
                    st.error(erreur)
                return
            
            # Vérifier la capacité de la salle
            salle = next((s for s in salles if s['id'] == salle_id), None)
            if salle['capacite'] < participants:
                st.error(f"Capacité de la salle insuffisante (max: {salle['capacite']}).")
                return
            
            # Vérifier les conflits
            if a_conflit(salle_id, date_reservation, heure_debut, heure_fin):
                st.error("La salle est déjà réservée à cet horaire.")
                return
            
            # Ajouter la réservation
            try:
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (salle_id, date_reservation, heure_debut, heure_fin, nom, participants))
                conn.commit()
                conn.close()
                st.success("Réservation ajoutée avec succès !")
                st.rerun()
            except Exception as e:
                st.error(f"Erreur : {e}")


def a_conflit(salle_id, date_obj, heure_debut, heure_fin):
    """Vérifie s'il y a un conflit pour une réservation."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id FROM reservations 
        WHERE salle_id = ? AND date = ? AND (
            (heure_debut <= ? AND heure_fin > ?) OR 
            (heure_debut < ? AND heure_fin >= ?)
        )
    """, (salle_id, date_obj, heure_debut, heure_debut, heure_fin, heure_fin))
    conflit = cursor.fetchone() is not None
    conn.close()
    return conflit


def get_all_salles():
    """Récupère toutes les salles."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM salles ORDER BY nom")
    salles = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return salles


### **Supprimer une réservation**
```python
def supprimer_reservation(reservation_id):
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Récupérer le nom pour l'affichage
        cursor.execute("SELECT nom FROM reservations WHERE id = ?", (reservation_id,))
        reservation = cursor.fetchone()
        if not reservation:
            st.error(f"Réservation avec ID {reservation_id} introuvable.")
            return
        
        # Supprimer la réservation
        cursor.execute("DELETE FROM reservations WHERE id = ?", (reservation_id,))
        conn.commit()
        st.success(f"Réservation '{reservation['nom']}' supprimée avec succès !")
    except Exception as e:
        st.error(f"Erreur lors de la suppression : {e}")
    finally:
        conn.close()


### **Page complète pour gérer les réservations**
```python
def gerer_reservations():
    st.title("📅 Gestion des Réservations")
    
    # Onglets pour les actions
    tab1, tab2 = st.tabs(["Liste des Réservations", "Ajouter une Réservation"])
    
    with tab1:
        liste_reservations()
    
    with tab2:
        formulaire_ajouter_reservation()
```

---

## 4️⃣ **Calendrier visuel**

### **Afficher un calendrier par salle**
```python
def calendrier():
    st.title("📆 Calendrier des Réservations")
    
    salles = get_all_salles()
    if not salles:
        st.warning("Aucune salle disponible.")
        return
    
    # Sélectionner une salle
    salle_id = st.selectbox(
        "Sélectionnez une salle",
        options=[(salle['id'], salle['nom']) for salle in salles],
        format_func=lambda x: x[1]
    )[0]
    
    # Sélectionner une date
    today = date.today()
    date_debut = st.date_input("Date de début", value=today)
    jours = st.slider("Nombre de jours à afficher", 1, 14, 7)
    date_fin = date_debut + timedelta(days=jours)
    
    # Récupérer les réservations pour cette salle et cette période
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM reservations 
        WHERE salle_id = ? AND date BETWEEN ? AND ?
        ORDER BY date, heure_debut
    """, (salle_id, date_debut, date_fin))
    reservations = cursor.fetchall()
    conn.close()
    
    # Afficher le calendrier
    st.subheader(f"Calendrier pour {salles[0]['nom']} ({date_debut} au {date_fin})")
    
    # Créer un DataFrame pour afficher les réservations
    import pandas as pd
    if reservations:
        df = pd.DataFrame([dict(res) for res in reservations])
        df['date'] = pd.to_datetime(df['date']).dt.date
        df['heure_debut'] = df['heure_debut'].astype(str)
        df['heure_fin'] = df['heure_fin'].astype(str)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Aucune réservation pour cette période.")
    
    # Afficher sous forme de timeline (optionnel)
    if reservations:
        st.subheader("Timeline")
        for res in reservations:
            st.write(f"📅 {res['date']} | ⏰ {res['heure_debut']}-{res['heure_fin']} | {res['nom']} ({res['participants']} pers.)")
```

---

## 5️⃣ **Fonctions utilitaires**

### **Vérifier les conflits** (déjà implémentée ci-dessus)
```python
def a_conflit(salle_id, date_obj, heure_debut, heure_fin):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id FROM reservations 
        WHERE salle_id = ? AND date = ? AND (
            (heure_debut <= ? AND heure_fin > ?) OR 
            (heure_debut < ? AND heure_fin >= ?)
        )
    """, (salle_id, date_obj, heure_debut, heure_debut, heure_fin, heure_fin))
    conflit = cursor.fetchone() is not None
    conn.close()
    return conflit
```

### **Récupérer les réservations pour une salle et une date**
```python
def get_reservations_salle_date(salle_id, date_obj):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM reservations 
        WHERE salle_id = ? AND date = ?
        ORDER BY heure_debut
    """, (salle_id, date_obj))
    reservations = cursor.fetchall()
    conn.close()
    return reservations
```

### **Vérifier la disponibilité d’une salle**
```python
def salle_disponible(salle_id, date_obj, heure_debut, heure_fin):
    """Vérifie si une salle est disponible pour une plage horaire."""
    return not a_conflit(salle_id, date_obj, heure_debut, heure_fin)
```

---

## 6️⃣ **Exemple complet de `app.py`**
Voici un exemple complet avec toutes les fonctionnalités :

```python
import streamlit as st
import sqlite3
import os
from datetime import datetime, time, date, timedelta
import pandas as pd

# Configuration de la page
st.set_page_config(
    page_title="Réservation de Salles",
    page_icon="🏢",
    layout="wide"
)

# Initialisation de la base de données
DATABASE = 'data.db'

def init_db():
    if not os.path.exists(DATABASE):
        conn = sqlite3.connect(DATABASE)
        with open('base.sql', 'r') as f:
            conn.executescript(f.read())
        conn.close()


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# Initialiser la base au démarrage
init_db()


# ============ FONCTIONS UTILITAIRES ============

def get_all_salles():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM salles ORDER BY nom")
    salles = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return salles


def a_conflit(salle_id, date_obj, heure_debut, heure_fin):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id FROM reservations 
        WHERE salle_id = ? AND date = ? AND (
            (heure_debut <= ? AND heure_fin > ?) OR 
            (heure_debut < ? AND heure_fin >= ?)
        )
    """, (salle_id, date_obj, heure_debut, heure_debut, heure_fin, heure_fin))
    conflit = cursor.fetchone() is not None
    conn.close()
    return conflit


def supprimer_salle(salle_id):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT nom FROM salles WHERE id = ?", (salle_id,))
        salle = cursor.fetchone()
        if salle:
            cursor.execute("DELETE FROM salles WHERE id = ?", (salle_id,))
            conn.commit()
            st.success(f"Salle '{salle['nom']}' supprimée avec succès !")
    except Exception as e:
        st.error(f"Erreur : {e}")
    finally:
        conn.close()


def supprimer_reservation(reservation_id):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT nom FROM reservations WHERE id = ?", (reservation_id,))
        reservation = cursor.fetchone()
        if reservation:
            cursor.execute("DELETE FROM reservations WHERE id = ?", (reservation_id,))
            conn.commit()
            st.success(f"Réservation '{reservation['nom']}' supprimée avec succès !")
    except Exception as e:
        st.error(f"Erreur : {e}")
    finally:
        conn.close()


# ============ PAGES ============

def main():
    st.title("🏢 Réservation de Salles")
    st.markdown("""
    Bienvenue dans l'application de réservation de salles.
    Utilisez le menu latéral pour naviguer.
    """)


def gerer_salles():
    st.title("🏫 Gestion des Salles")
    
    tab1, tab2 = st.tabs(["Liste des Salles", "Ajouter une Salle"])
    
    with tab1:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM salles ORDER BY nom")
        salles = cursor.fetchall()
        conn.close()
        
        if not salles:
            st.warning("Aucune salle trouvée.")
        else:
            st.dataframe(salles, use_container_width=True)
            
            st.subheader("Supprimer une salle")
            salle_id = st.selectbox(
                "Sélectionnez une salle à supprimer",
                options=[salle['id'] for salle in salles],
                format_func=lambda x: next(s['nom'] for s in salles if s['id'] == x)
            )
            if st.button("Supprimer", key="supprimer_salle"):
                supprimer_salle(salle_id)
                st.rerun()
    
    with tab2:
        st.subheader("➕ Ajouter une Salle")
        with st.form("ajouter_salle"):
            nom = st.text_input("Nom de la salle", placeholder="Ex: Amphi A")
            capacite = st.number_input("Capacité", min_value=1, value=20)
            
            if st.form_submit_button("Ajouter"):
                if not nom:
                    st.error("Le nom est obligatoire !")
                    return
                
                try:
                    conn = get_db()
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO salles (nom, capacite) VALUES (?, ?)", (nom, capacite))
                    conn.commit()
                    conn.close()
                    st.success(f"Salle '{nom}' ajoutée avec succès !")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur : {e}")


def gerer_reservations():
    st.title("📅 Gestion des Réservations")
    
    tab1, tab2 = st.tabs(["Liste des Réservations", "Ajouter une Réservation"])
    
    with tab1:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.*, s.nom as salle_nom, s.capacite as salle_capacite
            FROM reservations r
            JOIN salles s ON r.salle_id = s.id
            ORDER BY r.date, r.heure_debut
        """)
        reservations = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        if not reservations:
            st.warning("Aucune réservation trouvée.")
        else:
            df = pd.DataFrame(reservations)
            df['date'] = df['date'].dt.date
            st.dataframe(df, use_container_width=True)
            
            st.subheader("Supprimer une réservation")
            reservation_id = st.selectbox(
                "Sélectionnez une réservation à supprimer",
                options=[res['id'] for res in reservations],
                format_func=lambda x: next(f"{res['nom']} ({res['date']})" for res in reservations if res['id'] == x)
            )
            if st.button("Supprimer", key="supprimer_reservation"):
                supprimer_reservation(reservation_id)
                st.rerun()
    
    with tab2:
        st.subheader("➕ Ajouter une Réservation")
        salles = get_all_salles()
        if not salles:
            st.warning("Aucune salle disponible. Ajoutez d'abord une salle !")
            return
        
        with st.form("ajouter_reservation"):
            salle_id = st.selectbox(
                "Salle",
                options=[(salle['id'], salle['nom']) for salle in salles],
                format_func=lambda x: f"{x[1]} (Capacité: {x[0]})"
            )[0]
            
            date_reservation = st.date_input("Date", min_value=date.today())
            
            col1, col2 = st.columns(2)
            with col1:
                heure_debut = st.time_input("Heure de début", value=time(10, 0), minute_step=30)
            with col2:
                heure_fin = st.time_input("Heure de fin", value=time(11, 0), minute_step=30)
            
            nom = st.text_input("Nom de la réservation", placeholder="Ex: Réunion équipe")
            participants = st.number_input("Nombre de participants", min_value=1, value=10)
            
            if st.form_submit_button("Réserver"):
                erreurs = []
                
                if not (time(8, 0) <= heure_debut <= time(20, 0) and time(8, 0) <= heure_fin <= time(20, 0)):
                    erreurs.append("Les réservations doivent être entre 8h et 20h.")
                
                duree_heures = (heure_fin.hour - heure_debut.hour) + (heure_fin.minute - heure_debut.minute) / 60
                if not (0.5 <= duree_heures <= 4):
                    erreurs.append("La durée doit être entre 30 minutes et 4 heures.")
                
                if heure_fin <= heure_debut:
                    erreurs.append("L'heure de fin doit être après l'heure de début.")
                
                if not nom:
                    erreurs.append("Le nom est obligatoire.")
                
                if erreurs:
                    for erreur in erreurs:
                        st.error(erreur)
                    return
                
                salle = next((s for s in salles if s['id'] == salle_id), None)
                if salle['capacite'] < participants:
                    st.error(f"Capacité de la salle insuffisante (max: {salle['capacite']}).")
                    return
                
                if a_conflit(salle_id, date_reservation, heure_debut, heure_fin):
                    st.error("La salle est déjà réservée à cet horaire.")
                    return
                
                try:
                    conn = get_db()
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (salle_id, date_reservation, heure_debut, heure_fin, nom, participants))
                    conn.commit()
                    conn.close()
                    st.success("Réservation ajoutée avec succès !")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur : {e}")


def calendrier():
    st.title("📆 Calendrier des Réservations")
    
    salles = get_all_salles()
    if not salles:
        st.warning("Aucune salle disponible.")
        return
    
    salle_id = st.selectbox(
        "Sélectionnez une salle",
        options=[(salle['id'], salle['nom']) for salle in salles],
        format_func=lambda x: x[1]
    )[0]
    
    today = date.today()
    date_debut = st.date_input("Date de début", value=today)
    jours = st.slider("Nombre de jours à afficher", 1, 14, 7)
    date_fin = date_debut + timedelta(days=jours)
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM reservations 
        WHERE salle_id = ? AND date BETWEEN ? AND ?
        ORDER BY date, heure_debut
    """, (salle_id, date_debut, date_fin))
    reservations = cursor.fetchall()
    conn.close()
    
    if reservations:
        df = pd.DataFrame([dict(res) for res in reservations])
        df['date'] = pd.to_datetime(df['date']).dt.date
        df['heure_debut'] = df['heure_debut'].astype(str)
        df['heure_fin'] = df['heure_fin'].astype(str)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Aucune réservation pour cette période.")


# ============ MENU PRINCIPAL ============
def menu():
    st.sidebar.title("🏢 Navigation")
    page = st.sidebar.radio(
        "Aller à :",
        ["Accueil", "Gérer les Salles", "Gérer les Réservations", "Calendrier"]
    )
    
    if page == "Accueil":
        main()
    elif page == "Gérer les Salles":
        gerer_salles()
    elif page == "Gérer les Réservations":
        gerer_reservations()
    elif page == "Calendrier":
        calendrier()


if __name__ == "__main__":
    menu()
```

---

## Lancer l’application Streamlit

### En mode développement :
```bash
streamlit run app.py
```

### Options de lancement :
```bash
# Sur un port spécifique
streamlit run app.py --server.port 8502

# En mode production (pas de rechargement automatique)
streamlit run app.py --server.enableXsrfProtection false --server.enableCORS false

# Avec un thème personnalisé
streamlit run app.py --theme.base light --theme.primaryColor #4CAF50
```

---

## Déboguer l’application Streamlit

### 1️⃣ **Afficher les logs** :
```bash
streamlit run app.py --logger.level debug
```

### 2️⃣ **Utiliser `st.write` pour déboguer** :
```python
st.write("Debug : valeur de salle_id =", salle_id)
```

### 3️⃣ **Vérifier les types des données** :
Streamlit convertit automatiquement les types (ex: `date` → `datetime.date`).
Pour éviter les erreurs :
```python
st.write(type(date_reservation))  # Vérifier le type
```

### 4️⃣ **Gérer les erreurs** :
Utiliser `try/except` pour capturer et afficher les erreurs :
```python
try:
    # Code qui peut échouer
    cursor.execute("SELECT * FROM salles")
except Exception as e:
    st.error(f"Erreur : {e}")
```

---

## Bonnes pratiques Streamlit
✅ **Utiliser des `st.form`** :
   - Regroupe les champs de formulaire et évite le rechargement à chaque modification.

✅ **Éviter les rechargements inutiles** :
   - Utiliser `st.rerun()` uniquement quand nécessaire.
   - Éviter de recharger après chaque interaction.

✅ **Optimiser les requêtes SQLite** :
   - Fermer les connexions après utilisation.
   - Éviter de charger toute la base en mémoire.

✅ **Utiliser des `st.session_state`** :
   - Pour conserver l’état entre les rechargements (ex: données temporaires).
   ```python
   if 'comptage' not in st.session_state:
       st.session_state.comptage = 0
   st.session_state.comptage += 1
   st.write(f"Comptage : {st.session_state.comptage}")
   ```

✅ **Utiliser des `st.cache_data`** :
   - Pour mettre en cache les données qui ne changent pas souvent.
   ```python
   @st.cache_data
def get_all_salles_cached():
       conn = get_db()
       cursor = conn.cursor()
       cursor.execute("SELECT * FROM salles")
       salles = cursor.fetchall()
       conn.close()
       return salles
   ```

✅ **Valider les entrées utilisateur** :
   - Toujours vérifier les données avant de les utiliser (ex: `salle_id > 0`).

✅ **Afficher des messages clairs** :
   - Utiliser `st.success`, `st.error`, `st.warning`, `st.info` pour guider l’utilisateur.

---

## Erreurs courantes à éviter
❌ **Ne pas fermer les connexions SQLite** → **Fuites de mémoire** et erreurs "database is locked".

❌ **Oublier `conn.row_factory = sqlite3.Row`** → Les résultats ne sont pas accessibles par nom de colonne.

❌ **Utiliser des variables globales** → Streamlit réexécute le script à chaque interaction.
   - ❌ `salles = get_all_salles()` en dehors d’une fonction.
   - ✅ Utiliser `st.session_state` ou `st.cache_data`.

❌ **Ne pas valider les entrées** → Risques d’erreurs SQL ou de données invalides.

❌ **Oublier `PRAGMA foreign_keys = ON`** → Les contraintes de clé étrangère ne sont pas vérifiées.

❌ **Ne pas gérer les exceptions** → L’application plante avec un message d’erreur peu clair.

---

## Configuration avancée

### 1️⃣ **Fichier `.streamlit/config.toml`**
```toml
[theme]
base = "light"
primaryColor = "#4CAF50"
backgroundColor = "#f4f4f4"
secondaryBackgroundColor = "#ffffff"
textColor = "#333333"

[server]
port = 8501
enableXsrfProtection = true
enableCORS = false
```

### 2️⃣ **Personnaliser le style** :
Utiliser `st.markdown` avec du CSS personnalisé :
```python
st.markdown("""
<style>
    .stButton>button {
        background-color: #4CAF50;
        color: white;
        padding: 10px 20px;
        border: none;
        border-radius: 4px;
    }
    .erreur {
        color: red;
    }
</style>
""", unsafe_allow_html=True)
```

---

## Outils recommandés
| Outil | Utilisation |
|-------|-------------|
| `streamlit` | Framework principal. |
| `sqlite3` | Gestion de la base de données. |
| `pandas` | Manipulation des données (affichage en tableau). |
| `pytest` | Tests unitaires. |
| `Streamlit Docs` | [Documentation officielle](https://docs.streamlit.io/). |

---

## Ressources utiles
- [Documentation Streamlit](https://docs.streamlit.io/) (officielle)
- [Streamlit Cheat Sheet](https://docs.streamlit.io/library/cheatsheet)
- [Streamlit Components](https://streamlit.io/components) (composants personnalisés)
- [SQLite et Streamlit](https://docs.streamlit.io/knowledge-base/tutorials/databases/sqlite)
- [Exemples Streamlit](https://streamlit.io/gallery)
