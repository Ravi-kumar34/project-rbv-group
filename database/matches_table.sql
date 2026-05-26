-- Run this once to add the matches table to your existing 'project' database
-- (your users table from Phase 1 already exists)

USE project;

CREATE TABLE IF NOT EXISTS matches (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    player1_uid VARCHAR(50) NOT NULL,
    player2_uid VARCHAR(50) NOT NULL,
    winner_uid  VARCHAR(50) NULL,          -- NULL means Draw
    played_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (player1_uid) REFERENCES users(uid),
    FOREIGN KEY (player2_uid) REFERENCES users(uid)
);
