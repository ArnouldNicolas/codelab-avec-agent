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
    # Si value est une chaîne (format ISO de SQLite), la convertir en objet date
    if isinstance(value, str):
        try:
            from datetime import date, datetime
            # Essayer de parser comme date ISO
            date_obj = date.fromisoformat(value)
            return date_obj.strftime(format)
        except (ValueError, AttributeError):
            # Si ce n'est pas une date ISO valide, retourner la chaîne telle quelle
            return value
    # Si c'est déjà un objet date ou datetime
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
        if heure_debut < time(8, 0):
            return False, "Réservation refusée : avant 8 h."
        else:
            return False, "Réservation refusée : après 20 h."
    
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
    
    # Convertir date_obj en objet date si c'est une chaîne
    if isinstance(date_obj, str):
        date_obj = date.fromisoformat(date_obj)
    
    # Convertir heure_debut et heure_fin en objets time si ce sont des chaînes
    if isinstance(heure_debut, str):
        heure_debut = datetime.strptime(heure_debut, "%H:%M").time()
    if isinstance(heure_fin, str):
        heure_fin = datetime.strptime(heure_fin, "%H:%M").time()
    
    # Convertir date_obj et time en chaînes ISO pour SQLite
    date_iso = date_obj.isoformat()
    heure_debut_str = heure_debut.isoformat()
    heure_fin_str = heure_fin.isoformat()
    
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


def a_conflit_avec_repetition(salle_id, date_debut, heure_debut, heure_fin, date_fin_repetition, reservation_id_exclure=None):
    """
    Vérifie s'il y a un conflit pour une série de réservations répétées.
    Vérifie toutes les dates entre date_debut et date_fin_repetition (inclus) avec un pas de 7 jours.
    """
    if date_fin_repetition is None or date_debut is None:
        return False, None
    
    # Convertir en objets date si ce sont des chaînes
    if isinstance(date_debut, str):
        date_debut = date.fromisoformat(date_debut)
    if isinstance(date_fin_repetition, str):
        date_fin_repetition = date.fromisoformat(date_fin_repetition)
    
    current_date = date_debut
    while current_date <= date_fin_repetition:
        if a_conflit(salle_id, current_date, heure_debut, heure_fin, reservation_id_exclure):
            return True, current_date
        current_date += timedelta(days=7)
    return False, None


def generer_occurrences_repetition(date_debut, date_fin_repetition):
    """
    Génère toutes les dates pour une répétition hebdomadaire.
    Retourne une liste de dates.
    """
    if date_fin_repetition is None:
        return []
    
    # Convertir en objets date si ce sont des chaînes
    if isinstance(date_debut, str):
        date_debut = date.fromisoformat(date_debut)
    if isinstance(date_fin_repetition, str):
        date_fin_repetition = date.fromisoformat(date_fin_repetition)
    
    occurrences = []
    current_date = date_debut
    while current_date <= date_fin_repetition:
        occurrences.append(current_date)
        current_date += timedelta(days=7)
    return occurrences


def supprimer_toutes_occurrences(reservation_id):
    """
    Supprime une réservation et toutes ses occurrences répétées (filles).
    """
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Trouver toutes les réservations filles (y compris la mère)
        cursor.execute("""
            WITH RECURSIVE reservation_tree AS (
                SELECT id FROM reservations WHERE id = ?
                UNION ALL
                SELECT r.id FROM reservations r
                JOIN reservation_tree rt ON r.reservation_mere_id = rt.id
            )
            SELECT id FROM reservation_tree
        """, (reservation_id,))
        
        all_ids = [row[0] for row in cursor.fetchall()]
        
        # Supprimer toutes les occurrences
        for rid in all_ids:
            cursor.execute("DELETE FROM reservations WHERE id = ?", (rid,))
        
        conn.commit()
        return len(all_ids)
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        close_db(conn)


def supprimer_occurrences_futures(reservation_id, date_aujourdhui=None):
    """
    Supprime toutes les occurrences futures d'une réservation répétée (y compris la réservation elle-même si elle est dans le futur).
    Conserve les occurrences passées.
    """
    if date_aujourdhui is None:
        date_aujourdhui = date.today()
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Trouver la réservation mère
        cursor.execute("SELECT reservation_mere_id FROM reservations WHERE id = ?", (reservation_id,))
        mere_id = cursor.fetchone()[0]
        if mere_id:
            reservation_id = mere_id
        
        # Trouver toutes les réservations filles (y compris la mère)
        cursor.execute("""
            WITH RECURSIVE reservation_tree AS (
                SELECT id, date FROM reservations WHERE id = ?
                UNION ALL
                SELECT r.id, r.date FROM reservations r
                JOIN reservation_tree rt ON r.reservation_mere_id = rt.id
            )
            SELECT id, date FROM reservation_tree
        """, (reservation_id,))
        
        reservations = cursor.fetchall()
        
        # Supprimer les occurrences futures
        deleted_count = 0
        for rid, res_date in reservations:
            # res_date peut être une chaîne (de SQLite) ou un objet date
            if isinstance(res_date, str):
                res_date_obj = date.fromisoformat(res_date)
            else:
                res_date_obj = res_date
            if res_date_obj >= date_aujourdhui:
                cursor.execute("DELETE FROM reservations WHERE id = ?", (rid,))
                deleted_count += 1
        
        conn.commit()
        return deleted_count
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        close_db(conn)


def get_reservation_mere_id(reservation_id):
    """
    Récupère l'ID de la réservation mère (ou None si c'est déjà une mère ou une réservation unique).
    """
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT reservation_mere_id FROM reservations WHERE id = ?", (reservation_id,))
        result = cursor.fetchone()
        if result and result[0]:
            return result[0]
        return None
    finally:
        close_db(conn)


def est_reservation_mere(reservation_id):
    """
    Vérifie si une réservation est une réservation mère (a des enfants).
    """
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT COUNT(*) FROM reservations WHERE reservation_mere_id = ?", (reservation_id,))
        count = cursor.fetchone()[0]
        return count > 0
    finally:
        close_db(conn)


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
    responsable = request.form.get('responsable', '').strip()
    type_de_local=request.form.get('type_de_local','').strip()

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
        cursor.execute("INSERT INTO salles (nom, capacite, responsable, type_de_local) VALUES (?, ?, ?, ?)", (nom, capacite, responsable if responsable else None, type_de_local if type_de_local else None))
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
        responsable = request.form.get('responsable', salle['responsable'] if salle['responsable'] else '').strip()
        type_de_local=request.form.get('type_de_local',salle['type_de_local']).strip()

        
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
            cursor.execute("UPDATE salles SET nom = ?, capacite = ?, responsable = ?, type_de_local = ? WHERE id = ?", 
                          (nom, capacite, responsable if responsable else None, type_de_local if type_de_local else None, salle_id))
            conn.commit()
            flash(f"Salle '{salle['nom']}' modifiée avec succès !", 'succes')
            close_db(conn)
            return redirect(url_for('liste_salles'))
        except Exception as e:
            flash(f"Erreur : {e}", 'erreur')
    
    close_db(conn)
    return render_template('modifier_salle.html', salle=salle)


@app.route('/salles/<int:salle_id>/planning')
def planning_salle(salle_id):
    """Affiche le planning d'une salle sur une semaine (du lundi au dimanche)."""
    conn = get_db()
    cursor = conn.cursor()
    
    # Vérifier que la salle existe
    cursor.execute("SELECT * FROM salles WHERE id = ?", (salle_id,))
    salle = cursor.fetchone()
    if not salle:
        flash("Salle introuvable.", 'erreur')
        close_db(conn)
        return redirect(url_for('liste_salles'))
    
    # Récupérer toutes les réservations pour cette salle
    cursor.execute("""
        SELECT r.* FROM reservations r
        WHERE r.salle_id = ?
        ORDER BY r.date, r.heure_debut
    """, (salle_id,))
    reservations = cursor.fetchall()
    
    # Organiser les réservations par jour de la semaine
    # Supposons que nous voulons afficher la semaine en cours ou une semaine spécifique
    # Pour simplifier, affichons toutes les réservations groupées par date
    planning_par_jour = {}
    for reservation in reservations:
        date_str = reservation['date']
        if date_str not in planning_par_jour:
            planning_par_jour[date_str] = []
        planning_par_jour[date_str].append(reservation)
    
    close_db(conn)
    return render_template('planning_salle.html', salle=salle, planning_par_jour=planning_par_jour)


# ============================================================================
# ROUTES POUR LES RÉSERVATIONS
# ============================================================================

@app.route('/reservations')
def liste_reservations():
    """Affiche la liste de toutes les réservations."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.id, r.salle_id, r.date, r.heure_debut, r.heure_fin, r.nom, r.participants, 
               r.repetition, r.date_fin_repetition, r.reservation_mere_id,
               s.nom as salle_nom, s.capacite as salle_capacite
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
    repetition = request.form.get('repetition') == 'on'
    date_fin_repetition_str = request.form.get('date_fin_repetition')
    
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
    
    # Si répétition est activée, date_fin_repetition est obligatoire
    if repetition and not date_fin_repetition_str:
        flash("La date de fin de répétition est obligatoire lorsque la répétition est activée.", 'erreur')
        return redirect(url_for('formulaire_ajouter_reservation'))
    
    # Convertir les types
    try:
        salle_id = int(salle_id)
        participants = int(participants_str)
        date_obj = date.fromisoformat(date_str)
        heure_debut = datetime.strptime(heure_debut_str, "%H:%M").time()
        heure_fin = datetime.strptime(heure_fin_str, "%H:%M").time()
        
        if repetition:
            date_fin_repetition = date.fromisoformat(date_fin_repetition_str)
            if date_fin_repetition < date_obj:
                flash("La date de fin de répétition doit être postérieure ou égale à la date de début.", 'erreur')
                return redirect(url_for('formulaire_ajouter_reservation'))
        else:
            date_fin_repetition = None
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
    if repetition:
        # Vérifier les conflits pour toutes les dates de la répétition
        a_conflit_flag, date_conflit = a_conflit_avec_repetition(
            salle_id, date_obj, heure_debut, heure_fin, date_fin_repetition
        )
        if a_conflit_flag:
            flash(f"La salle est déjà réservée à cet horaire le {date_conflit}.", 'erreur')
            close_db(conn)
            return redirect(url_for('formulaire_ajouter_reservation'))
    else:
        if a_conflit(salle_id, date_obj, heure_debut, heure_fin):
            flash("La salle est déjà réservée à cet horaire.", 'erreur')
            close_db(conn)
            return redirect(url_for('formulaire_ajouter_reservation'))
    
    # 4. Ajouter la/les réservation(s)
    try:
        # Convertir date_obj et time en chaînes ISO pour SQLite
        date_iso = date_obj.isoformat()
        heure_debut_str = heure_debut.isoformat()
        heure_fin_str = heure_fin.isoformat()
        
        if repetition:
            # Ajouter la réservation mère (première occurrence)
            cursor.execute("""
                INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants, repetition, date_fin_repetition, reservation_mere_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
            """, (salle_id, date_iso, heure_debut_str, heure_fin_str, nom, participants, True, date_fin_repetition.isoformat()))
            mere_id = cursor.lastrowid
            
            # Générer et ajouter toutes les occurrences suivantes
            occurrences = generer_occurrences_repetition(date_obj + timedelta(days=7), date_fin_repetition)
            for occ_date in occurrences:
                occ_date_iso = occ_date.isoformat()
                cursor.execute("""
                    INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants, repetition, date_fin_repetition, reservation_mere_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (salle_id, occ_date_iso, heure_debut_str, heure_fin_str, nom, participants, True, date_fin_repetition.isoformat(), mere_id))
            
            flash(f"Réservation répétée ajoutée avec succès ! {len(occurrences) + 1} occurrences créées.", 'succes')
        else:
            # Ajouter une réservation simple
            cursor.execute("""
                INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants, repetition, date_fin_repetition, reservation_mere_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL)
            """, (salle_id, date_iso, heure_debut_str, heure_fin_str, nom, participants, False, None, None))
            flash("Réservation ajoutée avec succès !", 'succes')
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        flash(f"Erreur : {e}", 'erreur')
    finally:
        close_db(conn)
    
    return redirect(url_for('liste_reservations'))


@app.route('/reservations/<int:reservation_id>/supprimer', methods=['POST'])
def supprimer_reservation(reservation_id):
    """Supprime une réservation."""
    # Vérifier si c'est une demande de suppression de toutes les occurrences
    supprimer_toutes = request.form.get('supprimer_toutes') == 'on'
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Vérifier que la réservation existe
    cursor.execute("SELECT nom, repetition, reservation_mere_id FROM reservations WHERE id = ?", (reservation_id,))
    reservation = cursor.fetchone()
    if not reservation:
        flash("Réservation introuvable.", 'erreur')
        close_db(conn)
        return redirect(url_for('liste_reservations'))
    
    nom = reservation['nom']
    is_repetition = reservation['repetition']
    mere_id = reservation['reservation_mere_id']
    
    # Supprimer la/les réservation(s)
    try:
        if is_repetition:
            if supprimer_toutes:
                # Supprimer toutes les occurrences (mère + filles)
                count = supprimer_toutes_occurrences(reservation_id)
                flash(f"Réservation '{nom}' et ses {count - 1} occurrences supprimées avec succès !", 'succes')
            else:
                # Supprimer uniquement cette occurrence
                cursor.execute("DELETE FROM reservations WHERE id = ?", (reservation_id,))
                conn.commit()
                flash(f"Occurrence de la réservation '{nom}' supprimée avec succès !", 'succes')
        else:
            # Supprimer une réservation simple
            cursor.execute("DELETE FROM reservations WHERE id = ?", (reservation_id,))
            conn.commit()
            flash(f"Réservation '{nom}' supprimée avec succès !", 'succes')
    except Exception as e:
        conn.rollback()
        flash(f"Erreur : {e}", 'erreur')
    finally:
        close_db(conn)
    
    return redirect(url_for('liste_reservations'))


@app.route('/reservations/<int:reservation_id>/supprimer-repetition', methods=['POST'])
def supprimer_repetition(reservation_id):
    """Supprime toutes les occurrences futures d'une réservation répétée."""
    conn = get_db()
    cursor = conn.cursor()
    
    # Vérifier que la réservation existe
    cursor.execute("SELECT nom, repetition, reservation_mere_id FROM reservations WHERE id = ?", (reservation_id,))
    reservation = cursor.fetchone()
    if not reservation:
        flash("Réservation introuvable.", 'erreur')
        close_db(conn)
        return redirect(url_for('liste_reservations'))
    
    nom = reservation['nom']
    is_repetition = reservation['repetition']
    mere_id = reservation['reservation_mere_id']
    
    if not is_repetition:
        flash("Cette réservation n'est pas une réservation répétée.", 'erreur')
        close_db(conn)
        return redirect(url_for('liste_reservations'))
    
    # Trouver la mère
    target_id = mere_id if mere_id else reservation_id
    
    try:
        # Supprimer toutes les occurrences futures
        count = supprimer_occurrences_futures(target_id)
        flash(f"{count} occurrence(s) future(s) de la réservation '{nom}' supprimée(s) avec succès !", 'succes')
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
    
    # Vérifier si c'est une occurrence d'une réservation répétée
    mere_id = reservation['reservation_mere_id']
    is_occurrence = mere_id is not None
    
    if request.method == 'POST':
        # Récupérer les nouvelles valeurs
        nouvelle_salle_id = request.form.get('salle_id', reservation['salle_id'])
        # Convertir reservation['date'] en string si ce n'est pas déjà une string
        date_default = reservation['date'].isoformat() if isinstance(reservation['date'], date) else str(reservation['date']) if reservation['date'] else ''
        nouvelle_date_str = request.form.get('date', date_default)
        nouvelle_heure_debut_str = request.form.get('heure_debut', reservation['heure_debut'])
        nouvelle_heure_fin_str = request.form.get('heure_fin', reservation['heure_fin'])
        nouveau_nom = request.form.get('nom', reservation['nom']).strip()
        nouveaux_participants_str = request.form.get('participants', reservation['participants'])
        nouvelle_repetition = request.form.get('repetition') == 'on'
        nouvelle_date_fin_repetition_str = request.form.get('date_fin_repetition')
        
        # Option pour modifier seulement cette occurrence ou toutes
        modifier_toutes = request.form.get('modifier_toutes') == 'on'
        
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
        
        # Si répétition est activée, date_fin_repetition est obligatoire
        if nouvelle_repetition and not nouvelle_date_fin_repetition_str:
            flash("La date de fin de répétition est obligatoire lorsque la répétition est activée.", 'erreur')
            return render_template('modifier_reservation.html', 
                                   reservation=reservation, salles=salles)
        
        # Convertir les types
        try:
            nouvelle_salle_id = int(nouvelle_salle_id)
            nouveaux_participants = int(nouveaux_participants_str)
            nouvelle_date_obj = date.fromisoformat(nouvelle_date_str)
            nouvelle_heure_debut = datetime.strptime(nouvelle_heure_debut_str, "%H:%M").time()
            nouvelle_heure_fin = datetime.strptime(nouvelle_heure_fin_str, "%H:%M").time()
            
            if nouvelle_repetition:
                nouvelle_date_fin_repetition = date.fromisoformat(nouvelle_date_fin_repetition_str)
                if nouvelle_date_fin_repetition < nouvelle_date_obj:
                    flash("La date de fin de répétition doit être postérieure ou égale à la date de début.", 'erreur')
                    return render_template('modifier_reservation.html', 
                                           reservation=reservation, salles=salles)
            else:
                nouvelle_date_fin_repetition = None
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
        
        # 3. Vérifier les conflits
        # Si c'est une occurrence d'une réservation répétée et qu'on ne modifie que cette occurrence
        if is_occurrence and not modifier_toutes:
            # On va transformer cette occurrence en une réservation indépendante
            # Vérifier seulement le conflit pour cette date
            if a_conflit(nouvelle_salle_id, nouvelle_date_obj, 
                        nouvelle_heure_debut, nouvelle_heure_fin, reservation_id):
                flash("La salle est déjà réservée à cet horaire.", 'erreur')
                return render_template('modifier_reservation.html', 
                                       reservation=reservation, salles=salles)
        elif nouvelle_repetition:
            # Vérifier les conflits pour toutes les dates de la répétition
            a_conflit_flag, date_conflit = a_conflit_avec_repetition(
                nouvelle_salle_id, nouvelle_date_obj, nouvelle_heure_debut, nouvelle_heure_fin, 
                nouvelle_date_fin_repetition, reservation_id
            )
            if a_conflit_flag:
                flash(f"La salle est déjà réservée à cet horaire le {date_conflit}.", 'erreur')
                return render_template('modifier_reservation.html', 
                                       reservation=reservation, salles=salles)
        else:
            # Vérifier le conflit pour cette date uniquement
            if a_conflit(nouvelle_salle_id, nouvelle_date_obj, 
                        nouvelle_heure_debut, nouvelle_heure_fin, reservation_id):
                flash("La salle est déjà réservée à cet horaire.", 'erreur')
                return render_template('modifier_reservation.html', 
                                       reservation=reservation, salles=salles)
        
        # 4. Modifier la/les réservation(s)
        try:
            # Convertir date_obj et time en chaînes ISO pour SQLite
            nouvelle_date_iso = nouvelle_date_obj.isoformat()
            nouvelle_heure_debut_str = nouvelle_heure_debut.isoformat()
            nouvelle_heure_fin_str = nouvelle_heure_fin.isoformat()
            
            if is_occurrence and not modifier_toutes:
                # Transformer cette occurrence en une réservation indépendante
                cursor.execute("""
                    UPDATE reservations 
                    SET salle_id = ?, date = ?, heure_debut = ?, heure_fin = ?, nom = ?, 
                        participants = ?, repetition = ?, date_fin_repetition = ?, reservation_mere_id = ?
                    WHERE id = ?
                """, (nouvelle_salle_id, nouvelle_date_iso, nouvelle_heure_debut_str, nouvelle_heure_fin_str, 
                      nouveau_nom, nouveaux_participants, nouvelle_repetition, 
                      nouvelle_date_fin_repetition.isoformat() if nouvelle_date_fin_repetition else None, 
                      None, reservation_id))
                flash("Occurrence modifiée avec succès (détachée de la série) !", 'succes')
            elif is_occurrence and modifier_toutes:
                # Trouver la mère et modifier toutes les occurrences
                mere_id = get_reservation_mere_id(reservation_id)
                if mere_id:
                    # Mettre à jour la mère
                    cursor.execute("""
                        UPDATE reservations 
                        SET salle_id = ?, heure_debut = ?, heure_fin = ?, nom = ?, 
                            participants = ?, repetition = ?, date_fin_repetition = ?
                        WHERE id = ?
                    """, (nouvelle_salle_id, nouvelle_heure_debut_str, nouvelle_heure_fin_str, 
                          nouveau_nom, nouveaux_participants, nouvelle_repetition, 
                          nouvelle_date_fin_repetition.isoformat() if nouvelle_date_fin_repetition else None,
                          mere_id))
                    
                    # Mettre à jour toutes les filles
                    cursor.execute("""
                        UPDATE reservations 
                        SET salle_id = ?, heure_debut = ?, heure_fin = ?, nom = ?, 
                            participants = ?, repetition = ?, date_fin_repetition = ?
                        WHERE reservation_mere_id = ?
                    """, (nouvelle_salle_id, nouvelle_heure_debut_str, nouvelle_heure_fin_str, 
                          nouveau_nom, nouveaux_participants, nouvelle_repetition, 
                          nouvelle_date_fin_repetition.isoformat() if nouvelle_date_fin_repetition else None,
                          mere_id))
                    
                    flash("Réservation mère et toutes ses occurrences modifiées avec succès !", 'succes')
                else:
                    # Cas où is_occurrence mais mere_id est None (ne devrait pas arriver)
                    cursor.execute("""
                        UPDATE reservations 
                        SET salle_id = ?, date = ?, heure_debut = ?, heure_fin = ?, nom = ?, 
                            participants = ?, repetition = ?, date_fin_repetition = ?, reservation_mere_id = ?
                        WHERE id = ?
                    """, (nouvelle_salle_id, nouvelle_date_iso, nouvelle_heure_debut_str, nouvelle_heure_fin_str, 
                          nouveau_nom, nouveaux_participants, nouvelle_repetition, 
                          nouvelle_date_fin_repetition.isoformat() if nouvelle_date_fin_repetition else None,
                          None, reservation_id))
                    flash("Réservation modifiée avec succès !", 'succes')
            else:
                # C'est la mère ou une réservation simple
                if nouvelle_repetition:
                    # Si on active la répétition, il faut recréer toutes les occurrences
                    # D'abord supprimer les anciennes occurrences (filles)
                    cursor.execute("DELETE FROM reservations WHERE reservation_mere_id = ?", (reservation_id,))
                    
                    # Mettre à jour la mère
                    cursor.execute("""
                        UPDATE reservations 
                        SET salle_id = ?, date = ?, heure_debut = ?, heure_fin = ?, nom = ?, 
                            participants = ?, repetition = ?, date_fin_repetition = ?, reservation_mere_id = ?
                        WHERE id = ?
                    """, (nouvelle_salle_id, nouvelle_date_iso, nouvelle_heure_debut_str, nouvelle_heure_fin_str, 
                          nouveau_nom, nouveaux_participants, True, 
                          nouvelle_date_fin_repetition.isoformat() if nouvelle_date_fin_repetition else None, 
                          None, reservation_id))
                    
                    # Créer de nouvelles occurrences
                    if nouvelle_date_fin_repetition:
                        occurrences = generer_occurrences_repetition(nouvelle_date_obj + timedelta(days=7), nouvelle_date_fin_repetition)
                        for occ_date in occurrences:
                            occ_date_iso = occ_date.isoformat()
                            cursor.execute("""
                                INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants, 
                                                          repetition, date_fin_repetition, reservation_mere_id)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (nouvelle_salle_id, occ_date_iso, nouvelle_heure_debut_str, nouvelle_heure_fin_str, 
                                  nouveau_nom, nouveaux_participants, True, nouvelle_date_fin_repetition.isoformat(), 
                                  reservation_id))
                    
                    flash(f"Réservation modifiée avec succès ! {len(occurrences) + 1} occurrences.", 'succes')
                else:
                    # Désactiver la répétition : supprimer toutes les filles
                    cursor.execute("DELETE FROM reservations WHERE reservation_mere_id = ?", (reservation_id,))
                    
                    # Mettre à jour la mère comme une réservation simple
                    cursor.execute("""
                        UPDATE reservations 
                        SET salle_id = ?, date = ?, heure_debut = ?, heure_fin = ?, nom = ?, 
                            participants = ?, repetition = ?, date_fin_repetition = ?, reservation_mere_id = ?
                        WHERE id = ?
                    """, (nouvelle_salle_id, nouvelle_date_iso, nouvelle_heure_debut_str, nouvelle_heure_fin_str, 
                          nouveau_nom, nouveaux_participants, False, None, None, reservation_id))
                    
                    flash("Réservation modifiée avec succès ! La répétition a été désactivée.", 'succes')
            
            conn.commit()
            close_db(conn)
            return redirect(url_for('liste_reservations'))
        except Exception as e:
            conn.rollback()
            flash(f"Erreur : {e}", 'erreur')
    
    close_db(conn)
    return render_template('modifier_reservation.html', reservation=reservation, salles=salles, est_occurrence=is_occurrence)


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
        # Les champs date/heure de SQLite sont déjà des chaînes au format ISO
        # Pas besoin de convertir, mais si ce sont des objets, les convertir
        if isinstance(reservation['date'], date):
            reservation['date'] = reservation['date'].isoformat()
        if isinstance(reservation['heure_debut'], time):
            reservation['heure_debut'] = reservation['heure_debut'].isoformat()
        if isinstance(reservation['heure_fin'], time):
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
# ROUTES COMPATIBILITÉ AVEC LES TESTS EXISTANTS
# ============================================================================

@app.route('/reserver', methods=['POST'])
def reserver():
    """Route alternative pour ajouter une réservation (compatibilité avec les tests)."""
    salle_id = request.form.get('salle_id')
    date_str = request.form.get('date')
    heure_debut_str = request.form.get('debut')
    heure_fin_str = request.form.get('fin')
    nom = request.form.get('personne')
    participants_str = request.form.get('participants')
    
    # Validation des champs obligatoires
    if not salle_id or not date_str or not heure_debut_str or not heure_fin_str or not nom or not participants_str:
        flash("Tous les champs sont obligatoires.", 'erreur')
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
    valide, message = valider_horaires(heure_debut, heure_fin)
    if not valide:
        flash(message, 'erreur')
        return redirect(url_for('formulaire_ajouter_reservation'))
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Vérifier que la salle existe
        cursor.execute("SELECT capacite FROM salles WHERE id = ?", (salle_id,))
        salle = cursor.fetchone()
        if not salle:
            flash("Salle introuvable.", 'erreur')
            close_db(conn)
            return redirect(url_for('formulaire_ajouter_reservation'))
        
        # Vérifier la capacité
        if salle[0] < participants:
            flash(f"Réservation refusée : capacité dépassée (Salle: {salle[0]}, Participants: {participants}).", 'erreur')
            close_db(conn)
            return redirect(url_for('formulaire_ajouter_reservation'))
        
        # Vérifier les conflits
        if a_conflit(salle_id, date_obj, heure_debut, heure_fin):
            flash("Réservation refusée : chevauchement avec une autre réservation.", 'erreur')
            close_db(conn)
            return redirect(url_for('formulaire_ajouter_reservation'))
        
        # Ajouter la réservation
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


@app.route('/planning/<int:salle_id>')
def planning_old(salle_id):
    """Route alternative pour afficher le planning (compatibilité avec les tests)."""
    return planning_salle(salle_id)


# ============================================================================
# EXÉCUTION DE L'APPLICATION
# ============================================================================

if __name__ == '__main__':
    app.run(debug=True)
