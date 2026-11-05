-- Schéma de la base de données pour le projet Réservation de Salles
-- Ce fichier est utilisé pour initialiser data.db

-- Table des salles
CREATE TABLE IF NOT EXISTS salles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL UNIQUE,
    capacite INTEGER NOT NULL CHECK (capacite > 0)
);

-- Table des réservations
CREATE TABLE IF NOT EXISTS reservations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    salle_id INTEGER NOT NULL,
    date DATE NOT NULL,
    heure_debut TIME NOT NULL,
    heure_fin TIME NOT NULL,
    nom TEXT NOT NULL,
    participants INTEGER NOT NULL CHECK (participants > 0),
    FOREIGN KEY (salle_id) REFERENCES salles(id) ON DELETE CASCADE,
    CHECK (heure_debut >= '08:00' AND heure_debut <= '20:00'),
    CHECK (heure_fin >= '08:00' AND heure_fin <= '20:00'),
    CHECK (heure_fin > heure_debut)
);

-- Exemples de salles
INSERT INTO salles (nom, capacite) VALUES ('Amphi A', 100);
INSERT INTO salles (nom, capacite) VALUES ('Amphi B', 80);
INSERT INTO salles (nom, capacite) VALUES ('Salle C1', 30);
INSERT INTO salles (nom, capacite) VALUES ('Salle C2', 25);
INSERT INTO salles (nom, capacite) VALUES ('Salle D1', 20);
INSERT INTO salles (nom, capacite) VALUES ('Salle D2', 15);

-- Exemples de réservations
INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants) 
VALUES (1, '2026-01-20', '08:00', '10:00', 'Cours de Mathématiques', 80);

INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants) 
VALUES (1, '2026-01-20', '14:00', '16:00', 'Conférence sur l''IA', 90);

INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants) 
VALUES (2, '2026-01-20', '10:00', '12:00', 'Cours de Physique', 60);

INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants) 
VALUES (3, '2026-01-21', '09:00', '11:00', 'Réunion d''équipe', 25);

INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants) 
VALUES (4, '2026-01-21', '14:00', '15:30', 'Atelier Python', 20);

INSERT INTO reservations (salle_id, date, heure_debut, heure_fin, nom, participants) 
VALUES (5, '2026-01-22', '10:00', '12:00', 'Soutenance de projet', 15);
