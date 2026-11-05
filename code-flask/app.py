"""
Application Flask pour la gestion des réservations de salles.
Projet : Réservation de salles pour un bâtiment universitaire.
"""

from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
import sqlite3
import os
from datetime import datetime, time, date, timedelta

# Initialisation de l'application Flask
app = Flask(__name__)
app.secret_key = 'ta_cle_secrete_ici_change_la_en_production'  # À changer en production

# Ajouter le filtre date pour Jinja2
@app.template_filter('date')
def date_filter(value, format='%Y-%m-%d'):
    """Filtre Jinja2 pour formater les dates."""
    if value is None:
        return ''
    return value.strftime(format)

# Configuration de la base de données
DATABASE = os.path.join(os.path.dirname(__file__), 'data.db')


def get_db():
    """Ouvre une connexion à la base de données."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Permet d'accéder aux colonnes par nom
    conn.execute("PRAGMA foreign_keys = ON")  # Active les clés étrangères
    
    # Vérifier que les tables existent, sinon les créer
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='salles'")
    if not cursor.fetchone():
        # Tables manquantes, les créer
        base_sql_path = os.path.join(os.path.dirname(__file__), 'base.sql')
        with open(base_sql_path, 'r', encoding='utf-8') as f:
            schema = f.read()
        cursor.executescript(schema)
        conn.commit()
    
    return conn


def init_db():
    """Initialise la base de données à partir de base.sql."""
    conn = get_db()
    cursor = conn.cursor()
    
    # Toujours recréer les tables depuis base.sql pour éviter tout problème
    # Vérifier d'abord si les tables existent
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='salles'")
    salles_exists = cursor.fetchone()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='reservations'")
    reservations_exists = cursor.fetchone()
    
    if not salles_exists or not reservations_exists:
        # Lire et exécuter le schéma de base.sql
        base_sql_path = os.path.join(os.path.dirname(__file__), 'base.sql')
        with open(base_sql_path, 'r', encoding='utf-8') as f:
            schema = f.read()
        # Exécuter le schéma
        cursor.executescript(schema)
        conn.commit()
    
    conn.close()


def close_db(conn):
    """Ferme la connexion à la base de données."""
    if conn:
        conn.close()


# Initialiser la base au démarrage
with app.app_context():
    init_db()


# ============================================================================
# FONCTIONS UTILITAIRES POUR LES RÈGLES MÉTIER
# ============================================================================

def valider_horaires(heure_debut, heure_fin):
    """Vérifie que les horaires sont valides (8h-20h, durée 30min-4h)."""
    if not (time(8, 0) <= heure_debut <= time(20, 0) and time(8, 0) <= heure_fin <= time(20, 0)):
        return False, "Les réservations doivent être entre 8h00 et 20h00."
    
    duree_heures = (heure_fin.hour - heure_debut.hour) + (heure_fin.minute - heure_debut.minute) / 60
    if not (0.5 <= duree_heures <= 4):
        return False, "La durée doit être entre 30 minutes et 4 heures."
    
    if heure_fin <= heure_debut:
        return False, "L'heure de fin doit être après l'heure de début."
    
    return True, ""


def a_conflit(salle_id, date_obj, heure_debut, heure_fin, reservation_id_exclure=None):
    """
    Vérifie s'il y a un conflit pour une réservation.
    Si reservation_id_exclure est fourni, on l'exclut de la vérification (utile pour les modifications).
    """
    conn = get_db()
    cursor = conn.cursor()
    
    # Convertir date_obj et time en chaînes ISO pour SQLite
    date_iso = date_obj.isoformat()
    heure_debut_str = heure_debut.isoformat() if isinstance(heure_debut, time) else str(heure_debut)
    heure_fin_str = heure_fin.isoformat() if isinstance(heure_fin, time) else str(heure_fin)
    
    if reservation_id_exclure:
        cursor.execute("""
            SELECT id FROM reservations 
            WHERE salle_id = ? AND date = ? AND id != ? AND (
                (heure_debut <= ? AND heure_fin > ?) OR 
                (heure_debut < ? AND heure_fin >= ?)
            )
        """, (salle_id, date_iso, reservation_id_exclure, heure_debut_str, heure_debut_str, heure_fin_str, heure_fin_str))
    else:
        cursor.execute("""
            SELECT id FROM reservations 
            WHERE salle_id = ? AND date = ? AND (
                (heure_debut <= ? AND heure_fin > ?) OR 
                (heure_debut < ? AND heure_fin >= ?)
            )
        """, (salle_id, date_iso, heure_debut_str, heure_debut_str, heure_fin_str, heure_fin_str))
    
    conflit = cursor.fetchone() is not None
    close_db(conn)
    return conflit


# ============================================================================
# ROUTES POUR LES SALLES
# ============================================================================

@app.route('/salles')
def liste_salles():
    """Affiche la liste de toutes les salles."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM salles ORDER BY nom")
    salles = cursor.fetchall()
    close_db(conn)
    return render_template('salles.html', salles=salles)


@app.route('/salles/ajouter', methods=['GET'])
def formulaire_ajouter_salle():
    """Affiche le formulaire pour ajouter une salle."""
    return render_template('ajouter_salle.html')


@app.route('/salles', methods=['POST'])
def ajouter_salle():
    """Ajoute une nouvelle salle."""
    nom = request.form.get('nom', '').strip()
    capacite = request.form.get('capacite')
    
    # Validation
    if not nom:
        flash("Le nom de la salle est obligatoire.", 'erreur')
        return redirect(url_for('formulaire_ajouter_salle'))
    
    try:
        capacite = int(capacite)
        if capacite <= 0:
            flash("La capacité doit être supérieure à 0.", 'erreur')
            return redirect(url_for('formulaire_ajouter_salle'))
    except (ValueError, TypeError):
        flash("La capacité doit être un nombre entier.", 'erreur')
        return redirect(url_for('formulaire_ajouter_salle'))
    
    # Vérifier si le nom existe déjà
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM salles WHERE nom = ?", (nom,))
    if cursor.fetchone():
        flash(f"Une salle nommé '{nom}' existe déjà.", 'erreur')
        close_db(conn)
        return redirect(url_for('formulaire_ajouter_salle'))
    
    # Ajouter la salle
    try:
        cursor.execute("INSERT INTO salles (nom, capacite) VALUES (?, ?)", (nom, capacite))
        conn.commit()
        flash(f"Salle '{nom}' ajoutée avec succès !", 'succes')
    except Exception as e:
        flash(f"Erreur : {e}", 'erreur')
    finally:
        close_db(conn)
    
    return redirect(url_for('liste_salles'))


@app.route('/salles/<int:salle_id>/supprimer', methods=['POST'])
def supprimer_salle(salle_id):
    """Supprime une salle et toutes ses réservations (cascade)."""
    conn = get_db()
    cursor = conn.cursor()
    
    # Vérifier que la salle existe
    cursor.execute("SELECT nom FROM salles WHERE id = ?", (salle_id,))
    salle = cursor.fetchone()
    if not salle:
        flash("Salle introuvable.", 'erreur')
        close_db(conn)
        return redirect(url_for('liste_salles'))
    
    # Supprimer la salle (les réservations seront supprimées automatiquement via ON DELETE CASCADE)
    try:
        cursor.execute("DELETE FROM salles WHERE id = ?", (salle_id,))
        conn.commit()
        flash(f"Salle '{salle['nom']}' et toutes ses réservations ont été supprimées.", 'succes')
    except Exception as e:
        flash(f"Erreur : {e}", 'erreur')
    finally:
        close_db(conn)
    
    return redirect(url_for('liste_salles'))


@app.route('/salles/<int:salle_id>/modifier', methods=['GET', 'POST'])
def modifier_salle(salle_id):
    """Modifie une salle existante."""
    conn = get_db()
    cursor = conn.cursor()
    
    # Vérifier que la salle existe
    cursor.execute("SELECT * FROM salles WHERE id = ?", (salle_id,))
    salle = cursor.fetchone()
    if not salle:
        flash("Salle introuvable.", 'erreur')
        close_db(conn)
        return redirect(url_for('liste_salles'))
    
    if request.method == 'POST':
        # Récupérer les nouvelles valeurs
        nom = request.form.get('nom', salle['nom']).strip()
        capacite = request.form.get('capacite', salle['capacite'])
        
        # Validation
        if not nom:
            flash("Le nom de la salle est obligatoire.", 'erreur')
            return render_template('modifier_salle.html', salle=salle)
        
        try:
            capacite = int(capacite)
            if capacite <= 0:
                flash("La capacité doit être supérieure à 0.", 'erreur')
                return render_template('modifier_salle.html', salle=salle)
        except (ValueError, TypeError):
            flash("La capacité doit être un nombre entier.", 'erreur')
            return render_template('modifier_salle.html', salle=salle)
        
        # Vérifier si le nouveau nom existe déjà (sauf pour la salle actuelle)
        cursor.execute("SELECT id FROM salles WHERE nom = ? AND id != ?", (nom, salle_id))
        if cursor.fetchone():
            flash(f"Une salle nommé '{nom}' existe déjà.", 'erreur')
            return render_template('modifier_salle.html', salle=salle)
        
        # Modifier la salle
        try:
            cursor.execute("UPDATE salles SET nom = ?, capacite = ? WHERE id = ?", 
                          (nom, capacite, salle_id))
            conn.commit()
            flash(f"Salle '{salle['nom']}' modifiée avec succès !", 'succes')
            close_db(conn)
            return redirect(url_for('liste_salles'))
        except Exception as e:
            flash(f"Erreur : {e}", 'erreur')
    
    close_db(conn)
    return render_template('modifier_salle.html', salle=salle)


# ============================================================================
# ROUTES POUR LES RÉSERVATIONS
# ============================================================================

@app.route('/reservations')
def liste_reservations():
    """Affiche la liste de toutes les réservations."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.*, s.nom as salle_nom, s.capacite as salle_capacite
        FROM reservations r
        JOIN salles s ON r.salle_id = s.id
        ORDER BY r.date, r.heure_debut
    """)
    reservations = cursor.fetchall()
    close_db(conn)
    return render_template('reservations.html', reservations=reservations)


@app.route('/reservations/ajouter', methods=['GET'])
def formulaire_ajouter_reservation():
    """Affiche le formulaire pour ajouter une réservation."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM salles ORDER BY nom")
    salles = cursor.fetchall()
    close_db(conn)
    return render_template('ajouter_reservation.html', salles=salles, today=date.today())


@app.route('/reservations', methods=['POST'])
def ajouter_reservation():
    """Ajoute une nouvelle réservation."""
    salle_id = request.form.get('salle_id')
    date_str = request.form.get('date')
    heure_debut_str = request.form.get('heure_debut')
    heure_fin_str = request.form.get('heure_fin')
    nom = request.form.get('nom', '').strip()
    participants_str = request.form.get('participants')
    
    # Validation des champs obligatoires
    if not salle_id:
        flash("La salle est obligatoire.", 'erreur')
        return redirect(url_for('formulaire_ajouter_reservation'))
    
    if not date_str:
        flash("La date est obligatoire.", 'erreur')
        return redirect(url_for('formulaire_ajouter_reservation'))
    
    if not heure_debut_str or not heure_fin_str:
        flash("Les horaires sont obligatoires.", 'erreur')
        return redirect(url_for('formulaire_ajouter_reservation'))
    
    if not nom:
        flash("Le nom de la réservation est obligatoire.", 'erreur')
        return redirect(url_for('formulaire_ajouter_reservation'))
    
    if not participants_str:
        flash("Le nombre de participants est obligatoire.", 'erreur')
        return redirect(url_for('formulaire_ajouter_reservation'))
    
    # Convertir les types
    try:
        salle_id = int(salle_id)
        participants = int(participants_str)
        date_obj = date.fromisoformat(date_str)
        heure_debut = datetime.strptime(heure_debut_str, "%H:%M").time()
        heure_fin = datetime.strptime(heure_fin_str, "%H:%M").time()
    except (ValueError, TypeError) as e:
        flash(f"Format de données invalide : {e}", 'erreur')
        return redirect(url_for('formulaire_ajouter_reservation'))
    
    # Vérifier les règles métier
    # 1. Vérifier les horaires
    valide, message = valider_horaires(heure_debut, heure_fin)
    if not valide:
        flash(message, 'erreur')
        return redirect(url_for('formulaire_ajouter_reservation'))
    
    # 2. Vérifier que la salle existe et que la capacité est suffisante
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT capacite FROM salles WHERE id = ?", (salle_id,))
    salle = cursor.fetchone()
    if not salle:
        flash("Salle introuvable.", 'erreur')
        close_db(conn)
        return redirect(url_for('formulaire_ajouter_reservation'))
    
    if salle[0] < participants:
        flash(f"Capacité de la salle insuffisante (max: {salle[0]} participants).", 'erreur')
        close_db(conn)
        return redirect(url_for('formulaire_ajouter_reservation'))
    
    # 3. Vérifier les conflits
    if a_conflit(salle_id, date_obj, heure_debut, heure_fin):
        flash("La salle est déjà réservée à cet horaire.", 'erreur')
        close_db(conn)
        return redirect(url_for('formulaire_ajouter_reservation'))
    
    # 4. Ajouter la réservation
    try:
        # Convertir date_obj et time en chaînes ISO pour SQLite
        date_iso = date_obj.isoformat()
        heure_debut_str = heure_debut.isoformat()
        heure_fin_str = heure_fin.isoformat()
        cursor.execute("""
            INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (salle_id, date_iso, heure_debut_str, heure_fin_str, nom, participants))
        conn.commit()
        flash("Réservation ajoutée avec succès !", 'succes')
    except Exception as e:
        flash(f"Erreur : {e}", 'erreur')
    finally:
        close_db(conn)
    
    return redirect(url_for('liste_reservations'))


@app.route('/reservations/<int:reservation_id>/supprimer', methods=['POST'])
def supprimer_reservation(reservation_id):
    """Supprime une réservation."""
    conn = get_db()
    cursor = conn.cursor()
    
    # Vérifier que la réservation existe
    cursor.execute("SELECT nom FROM reservations WHERE id = ?", (reservation_id,))
    reservation = cursor.fetchone()
    if not reservation:
        flash("Réservation introuvable.", 'erreur')
        close_db(conn)
        return redirect(url_for('liste_reservations'))
    
    # Supprimer la réservation
    try:
        cursor.execute("DELETE FROM reservations WHERE id = ?", (reservation_id,))
        conn.commit()
        flash(f"Réservation '{reservation['nom']}' supprimée avec succès !", 'succes')
    except Exception as e:
        flash(f"Erreur : {e}", 'erreur')
    finally:
        close_db(conn)
    
    return redirect(url_for('liste_reservations'))


@app.route('/reservations/<int:reservation_id>/modifier', methods=['GET', 'POST'])
def modifier_reservation(reservation_id):
    """Modifie une réservation existante."""
    conn = get_db()
    cursor = conn.cursor()
    
    # Vérifier que la réservation existe
    cursor.execute("SELECT * FROM reservations WHERE id = ?", (reservation_id,))
    reservation = cursor.fetchone()
    if not reservation:
        flash("Réservation introuvable.", 'erreur')
        close_db(conn)
        return redirect(url_for('liste_reservations'))
    
    # Récupérer toutes les salles pour le formulaire
    cursor.execute("SELECT * FROM salles ORDER BY nom")
    salles = cursor.fetchall()
    
    if request.method == 'POST':
        # Récupérer les nouvelles valeurs
        nouvelle_salle_id = request.form.get('salle_id', reservation['salle_id'])
        nouvelle_date_str = request.form.get('date', reservation['date'].isoformat())
        nouvelle_heure_debut_str = request.form.get('heure_debut', reservation['heure_debut'])
        nouvelle_heure_fin_str = request.form.get('heure_fin', reservation['heure_fin'])
        nouveau_nom = request.form.get('nom', reservation['nom']).strip()
        nouveaux_participants_str = request.form.get('participants', reservation['participants'])
        
        # Validation
        if not nouvelle_salle_id:
            flash("La salle est obligatoire.", 'erreur')
            return render_template('modifier_reservation.html', 
                                   reservation=reservation, salles=salles)
        
        if not nouvelle_date_str:
            flash("La date est obligatoire.", 'erreur')
            return render_template('modifier_reservation.html', 
                                   reservation=reservation, salles=salles)
        
        if not nouvelle_heure_debut_str or not nouvelle_heure_fin_str:
            flash("Les horaires sont obligatoires.", 'erreur')
            return render_template('modifier_reservation.html', 
                                   reservation=reservation, salles=salles)
        
        if not nouveau_nom:
            flash("Le nom de la réservation est obligatoire.", 'erreur')
            return render_template('modifier_reservation.html', 
                                   reservation=reservation, salles=salles)
        
        if not nouveaux_participants_str:
            flash("Le nombre de participants est obligatoire.", 'erreur')
            return render_template('modifier_reservation.html', 
                                   reservation=reservation, salles=salles)
        
        # Convertir les types
        try:
            nouvelle_salle_id = int(nouvelle_salle_id)
            nouveaux_participants = int(nouveaux_participants_str)
            nouvelle_date_obj = date.fromisoformat(nouvelle_date_str)
            nouvelle_heure_debut = datetime.strptime(nouvelle_heure_debut_str, "%H:%M").time()
            nouvelle_heure_fin = datetime.strptime(nouvelle_heure_fin_str, "%H:%M").time()
        except (ValueError, TypeError) as e:
            flash(f"Format de données invalide : {e}", 'erreur')
            return render_template('modifier_reservation.html', 
                                   reservation=reservation, salles=salles)
        
        # Vérifier les règles métier
        # 1. Vérifier les horaires
        valide, message = valider_horaires(nouvelle_heure_debut, nouvelle_heure_fin)
        if not valide:
            flash(message, 'erreur')
            return render_template('modifier_reservation.html', 
                                   reservation=reservation, salles=salles)
        
        # 2. Vérifier que la salle existe et que la capacité est suffisante
        cursor.execute("SELECT capacite FROM salles WHERE id = ?", (nouvelle_salle_id,))
        salle = cursor.fetchone()
        if not salle:
            flash("Salle introuvable.", 'erreur')
            return render_template('modifier_reservation.html', 
                                   reservation=reservation, salles=salles)
        
        if salle[0] < nouveaux_participants:
            flash(f"Capacité de la salle insuffisante (max: {salle[0]} participants).", 'erreur')
            return render_template('modifier_reservation.html', 
                                   reservation=reservation, salles=salles)
        
        # 3. Vérifier les conflits (en excluant la réservation actuelle)
        if a_conflit(nouvelle_salle_id, nouvelle_date_obj, 
                    nouvelle_heure_debut, nouvelle_heure_fin, reservation_id):
            flash("La salle est déjà réservée à cet horaire.", 'erreur')
            return render_template('modifier_reservation.html', 
                                   reservation=reservation, salles=salles)
        
        # 4. Modifier la réservation
        try:
            # Convertir date_obj et time en chaînes ISO pour SQLite
            nouvelle_date_iso = nouvelle_date_obj.isoformat()
            nouvelle_heure_debut_str = nouvelle_heure_debut.isoformat()
            nouvelle_heure_fin_str = nouvelle_heure_fin.isoformat()
            cursor.execute("""
                UPDATE reservations 
                SET salle_id = ?, date = ?, heure_debut = ?, heure_fin = ?, nom = ?, participants = ?
                WHERE id = ?
            """, (nouvelle_salle_id, nouvelle_date_iso, nouvelle_heure_debut_str, 
                  nouvelle_heure_fin_str, nouveau_nom, nouveaux_participants, reservation_id))
            conn.commit()
            flash("Réservation modifiée avec succès !", 'succes')
            close_db(conn)
            return redirect(url_for('liste_reservations'))
        except Exception as e:
            flash(f"Erreur : {e}", 'erreur')
    
    close_db(conn)
    return render_template('modifier_reservation.html', reservation=reservation, salles=salles)


# ============================================================================
# ROUTE PRINCIPALE
# ============================================================================

@app.route('/')
def index():
    """Page d'accueil avec statistiques."""
    conn = get_db()
    cursor = conn.cursor()
    
    # Compter les salles
    cursor.execute("SELECT COUNT(*) FROM salles")
    nb_salles = cursor.fetchone()[0]
    
    # Compter les réservations
    cursor.execute("SELECT COUNT(*) FROM reservations")
    nb_reservations = cursor.fetchone()[0]
    
    # Compter les réservations pour aujourd'hui
    today = date.today()
    cursor.execute("SELECT COUNT(*) FROM reservations WHERE date = ?", (today,))
    nb_reservations_aujourdhui = cursor.fetchone()[0]
    
    # Récupérer les prochaines réservations (dans les 7 jours)
    dans_7_jours = today + timedelta(days=7)
    cursor.execute("""
        SELECT r.*, s.nom as salle_nom
        FROM reservations r
        JOIN salles s ON r.salle_id = s.id
        WHERE r.date BETWEEN ? AND ?
        ORDER BY r.date, r.heure_debut
        LIMIT 5
    """, (today, dans_7_jours))
    prochaines_reservations = cursor.fetchall()
    
    close_db(conn)
    
    return render_template('index.html', 
                          nb_salles=nb_salles,
                          nb_reservations=nb_reservations,
                          nb_reservations_aujourdhui=nb_reservations_aujourdhui,
                          prochaines_reservations=prochaines_reservations)


# ============================================================================
# ROUTES API (pour une utilisation avec un frontend séparé)
# ============================================================================

@app.route('/api/salles', methods=['GET'])
def api_liste_salles():
    """API : Liste toutes les salles."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM salles ORDER BY nom")
    salles = [dict(row) for row in cursor.fetchall()]
    close_db(conn)
    return jsonify(salles)


@app.route('/api/reservations', methods=['GET'])
def api_liste_reservations():
    """API : Liste toutes les réservations."""
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
        reservation['date'] = reservation['date'].isoformat()
        reservation['heure_debut'] = reservation['heure_debut'].isoformat()
        reservation['heure_fin'] = reservation['heure_fin'].isoformat()
        reservations.append(reservation)
    close_db(conn)
    return jsonify(reservations)


@app.route('/api/reservations', methods=['POST'])
def api_ajouter_reservation():
    """API : Ajoute une réservation."""
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
        heure_debut = datetime.strptime(data['heure_debut'], "%H:%M").time()
        heure_fin = datetime.strptime(data['heure_fin'], "%H:%M").time()
        nom = data['nom']
        participants = data['participants']
    except (ValueError, KeyError) as e:
        return jsonify({"error": f"Format de données invalide : {e}"}), 400
    
    # Vérifier les règles métier
    valide, message = valider_horaires(heure_debut, heure_fin)
    if not valide:
        return jsonify({"error": message}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT capacite FROM salles WHERE id = ?", (salle_id,))
        salle = cursor.fetchone()
        if not salle:
            return jsonify({"error": "Salle introuvable"}), 404
        if salle[0] < participants:
            return jsonify({"error": f"Capacité de la salle insuffisante (max: {salle[0]})"}), 400
        
        if a_conflit(salle_id, date_obj, heure_debut, heure_fin):
            return jsonify({"error": "La salle est déjà réservée à cet horaire"}), 409
        
        # Convertir date_obj et time en chaînes ISO pour SQLite
        date_iso = date_obj.isoformat()
        heure_debut_str = heure_debut.isoformat()
        heure_fin_str = heure_fin.isoformat()
        cursor.execute("""
            INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (salle_id, date_iso, heure_debut_str, heure_fin_str, nom, participants))
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


# ============================================================================
# EXÉCUTION DE L'APPLICATION
# ============================================================================

if __name__ == '__main__':
    app.run(debug=True)
