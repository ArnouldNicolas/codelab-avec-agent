from flask import Flask, redirect, render_template_string, request, url_for, session

from base import ouvrir_base


def _time_to_minutes(t):
    h, m = map(int, t.split(":"))
    return h * 60 + m


def _minutes_to_time(m):
    return f"{m // 60:02d}:{m % 60:02d}"


def _verifier_creneaux(debut, fin, salle_id, conn):
    """Retourne True si le créneau est invalide (conflit, capacité, plage horaire)."""
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
    if duree_min > 0:
        participants = int(request.form.get("participants", 0))
    else:
        participants = 0
    if participants > capacite_salle:
        return f"Le nombre de participants ({participants}) dépasse la capacité de la salle ({capacite_salle})."

    debut_min = _time_to_minutes(debut)
    fin_min = _time_to_minutes(fin)
    jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    date_semaine = conn.execute(
        "SELECT strftime('%w', date) FROM reservations WHERE salle_id = ?",
        [salle_id],
    ).fetchall()
    for existant in conn.execute(
        "SELECT debut, fin FROM reservations WHERE salle_id = ?", [salle_id]
    ).fetchall():
        e_debut = _time_to_minutes(existant["debut"])
        e_fin = _time_to_minutes(existant["fin"])
        if debut_min < e_fin and e_debut < fin_min:
            return "Cette salle est déjà réservée à cet horaire (chevauchement)."
    return None


PAGE = """
<h1>Réservation de salles</h1>

{% if erreur %}
  <p style="color:red">{{ erreur }}</p>
{% endif %}

<h2>Salles</h2>
<ul>
  {% for salle in salles %}
    <li>{{ salle["nom"] }}</li>
  {% endfor %}
</ul>

<form method="post" action="/reserver">
  <select name="salle_id">
    {% for salle in salles %}
      <option value="{{ salle["id"] }}">{{ salle["nom"] }} (capacité: {{ salle["capacite"] }})</option>
    {% endfor %}
  </select>
  <br>
  <input name="personne" placeholder="Personne" required>
  <input name="date" type="date" required>
  <br>
  Début: <input name="debut" type="time" required>
  <br>
  Fin: <input name="fin" type="time" required>
  <br>
  Participants: <input name="participants" type="number" min="1" required>
  <br>
  <button>Réserver</button>
</form>
"""


app = Flask(__name__)
app.secret_key = "clé-secrète-pour-les-tests"


@app.get("/")
def accueil():
    with ouvrir_base() as conn:
        salles = conn.execute("SELECT * FROM salles").fetchall()
    erreur = session.pop("erreur", None)
    return render_template_string(PAGE, salles=salles, erreur=erreur)


@app.post("/reserver")
def reserver():
    salle_id = int(request.form["salle_id"])
    personne = request.form["personne"]
    date = request.form["date"]
    debut = request.form["debut"]
    fin = request.form["fin"]
    participants = int(request.form["participants"])

    with ouvrir_base() as conn:
        err = _verifier_creneaux(debut, fin, salle_id, conn)
        if err:
            session["erreur"] = err
            return redirect("/")
        conn.execute(
            "INSERT INTO reservations (salle_id, personne, date, debut, fin, participants) VALUES (?, ?, ?, ?, ?, ?)",
            [salle_id, personne, date, debut, fin, participants],
        )
    return redirect("/")


@app.get("/annuler/<int:reservation_id>")
def annuler(reservation_id):
    with ouvrir_base() as conn:
        conn.execute("DELETE FROM reservations WHERE id = ?", [reservation_id])
    return redirect("/")


@app.get("/planning/<int:salle_id>")
def planning(salle_id):
    with ouvrir_base() as conn:
        salles = conn.execute("SELECT * FROM salles WHERE id = ?", [salle_id]).fetchone()
        reservations = conn.execute(
            "SELECT date, debut, fin, personne, participants FROM reservations WHERE salle_id = ? ORDER BY date, debut", [salle_id]
        ).fetchall()
    return render_template_string(
        """
        <h1>Planning - {{ salle["nom"] }}</h1>
        <p>Capacité: {{ salle["capacite"] }}</p>
        <table border="1">
          <tr><th>Date</th><th>Début</th><th>Fin</th><th>Personne</th><th>Participants</th></tr>
          {% for r in reservations %}
          <tr><td>{{ r["date"] }}</td><td>{{ r["debut"] }}</td><td>{{ r["fin"] }}</td><td>{{ r["personne"] }}</td><td>{{ r["participants"] }}</td></tr>
          {% endfor %}
        </table>
        <p><a href="/">Retour</a></p>
        """,
        salle=salles,
        reservations=reservations,
    )


# Ajoutez vos fonctions ici. Le HTML va dans PAGE.


if __name__ == "__main__":
    app.run(debug=True)
