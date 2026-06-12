from backend.config.database import get_mysql_connection

def update_elo_and_record(winner_uid, p1_uid, p2_uid):
    """
    Calculates Elo ratings using the standard formula and updates the database.
    Also logs the outcome to the matches history ledger.
    """
    conn = get_mysql_connection()
    cursor = conn.cursor()

    try:
        # 1. Fetch current ratings before the calculation
        cursor.execute("SELECT uid, elo_rating FROM users WHERE uid IN (%s, %s)", (p1_uid, p2_uid))
        rows = cursor.fetchall()
        ratings = {row[0]: row[1] for row in rows}

        r1 = ratings[p1_uid]
        r2 = ratings[p2_uid]

        # 2. Compute Expected Win Probability (E)
        e1 = 1 / (1 + 10 ** ((r2 - r1) / 400))
        e2 = 1 / (1 + 10 ** ((r1 - r2) / 400))

        # 3. Determine the actual score outcomes (S)
        K = 32
        db_winner = None
        
        if winner_uid == "Draw":
            s1, s2 = 0.5, 0.5
        elif winner_uid == p1_uid:
            s1, s2 = 1.0, 0.0
            db_winner = p1_uid
        else:
            s1, s2 = 0.0, 1.0
            db_winner = p2_uid

        # 4. Calculate New Scaled Ratings
        new_r1 = round(r1 + K * (s1 - e1))
        new_r2 = round(r2 + K * (s2 - e2))

        # 5. Commit Updated Ratings to Users Table
        cursor.execute("UPDATE users SET elo_rating=%s WHERE uid=%s", (new_r1, p1_uid))
        cursor.execute("UPDATE users SET elo_rating=%s WHERE uid=%s", (new_r2, p2_uid))

        # 6. Record Match History in the Matches Table
        cursor.execute(
            "INSERT INTO matches (player1_uid, player2_uid, winner_uid) VALUES (%s, %s, %s)",
            (p1_uid, p2_uid, db_winner)
        )
        conn.commit()

    except Exception as e:
        print(f"Error executing Elo update: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()