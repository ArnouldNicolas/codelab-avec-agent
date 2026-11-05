import streamlit as st
from base import ouvrir_base


def _time_to_minutes(t):
    h, m = map(int, str(t).split(":"))
    return h * 60 + m


def _minutes_to_time(m):
    return f"{m // 60:02d}:{m % 60:02d}"


def _verifier_creneau(debut, fin, salle_id, participants, conn):
    duree_min = _time_to_minutes(fin) - _time_to_minutes(debut)
    if duree_min < 30:
        return "La réservation doit durer au moins 30 minutes."
    if duree_min > 240:
        return "La réservation ne peut pas dépasser 4 heures."
    if _time_to_minutes(debut) < 8 * 60:
        return "Les réservations ne peuvent pas commencer avant 8 h."
    if _time_to_minutes(fin) > 20 * 60:
        return "Les réservations ne peuvent pas finir après 20 h."
    capacite_salle = conn.execute(
        "SELECT capacite FROM salles WHERE id = ?", [salle_id]
    ).fetchone()[0]
    if participants > capacite_salle:
        return f"Le nombre de participants ({participants}) dépasse la capacité de la salle ({capacite_salle})."
    debut_min = _time_to_minutes(debut)
    fin_min = _time_to_minutes(fin)
    for existant in conn.execute(
        "SELECT debut, fin FROM reservations WHERE salle_id = ?", [salle_id]
    ).fetchall():
        e_debut = _time_to_minutes(existant["debut"])
        e_fin = _time_to_minutes(existant["fin"])
        if debut_min < e_fin and e_debut < fin_min:
            return "Cette salle est déjà réservée à cet horaire (chevauchement)."
    return None


if "erreur" not in st.session_state:
    st.session_state.erreur = None

with ouvrir_base() as conn:
    salles = conn.execute("SELECT * FROM salles").fetchall()

st.title("Réservation de salles")

st.header("Salles")
for salle in salles:
    st.write(salle["nom"], f"capacité: {salle['capacite']}")

st.header("Réserver une salle")
salle_ids = [s["id"] for s in salles]
salle_choisie = st.selectbox("Salle", salle_ids, format_func=lambda x: next(s["nom"] for s in salles if s["id"] == x))
personne = st.text_input("Personne")
date = st.date_input("Date", value=None)
debut = st.time_input("Heure de début", value=None)
fin = st.time_input("Heure de fin", value=None)
participants = st.number_input("Participants", min_value=1, value=1)

if st.button("Réserver") and personne and date and debut and fin:
    err = _verifier_creneau(
        debut.strftime("%H:%M"),
        fin.strftime("%H:%M"),
        salle_choisie,
        int(participants),
        conn,
    )
    if err:
        st.session_state.erreur = err
    else:
        conn.execute(
            "INSERT INTO reservations (salle_id, personne, date, debut, fin, participants) VALUES (?, ?, ?, ?, ?, ?)",
            [salle_choisie, personne, str(date), debut.strftime("%H:%M"), fin.strftime("%H:%M"), int(participants)],
        )
        st.session_state.erreur = None
        st.rerun()

if st.session_state.erreur:
    st.error(st.session_state.erreur)

st.header("Annuler une réservation")
with ouvrir_base() as conn:
    reservations = conn.execute("SELECT id, date, debut, fin, personne FROM reservations ORDER BY date, debut").fetchall()
for r in reservations:
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write(f"{r['date']} {r['debut']}-{r['fin']} par {r['personne']}")
    with col2:
        if st.button("Annuler", key=f"annul_{r['id']}"):
            conn.execute("DELETE FROM reservations WHERE id = ?", [r["id"]])
            st.session_state.erreur = None
            st.rerun()

st.header("Planning d'une salle")
salle_planning_id = st.selectbox("Salle pour le planning", salle_ids, format_func=lambda x: next(s["nom"] for s in salles if s["id"] == x))
if st.button("Afficher le planning"):
    with ouvrir_base() as conn:
        salle = conn.execute("SELECT * FROM salles WHERE id = ?", [salle_planning_id]).fetchone()
        rows = conn.execute(
            "SELECT date, debut, fin, personne, participants FROM reservations WHERE salle_id = ? ORDER BY date, debut",
            [salle_planning_id],
        ).fetchall()
    st.write(f"Planing - {salle['nom']} (capacité: {salle['capacite']})")
    if rows:
        for r in rows:
            st.write(f"{r['date']} : {r['debut']} - {r['fin']} par {r['personne']} ({r['participants']} participants)")
    else:
        st.write("Aucune réservation pour cette salle.")
    if st.button("Retour"):
        st.rerun()