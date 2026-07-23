import sqlite3

conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

def setup_db():
    # ECONOMY
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS economy (
        user_id INTEGER PRIMARY KEY,
        wallet INTEGER DEFAULT 0,
        bank INTEGER DEFAULT 0,
        last_daily TEXT
    )
    """)

    # JOBS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        user_id INTEGER PRIMARY KEY,
        job TEXT,
        level INTEGER DEFAULT 1,
        xp INTEGER DEFAULT 0,
        last_daily TEXT
    )
    """)

    # ACTIVITY
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS activity (
        user_id INTEGER PRIMARY KEY,
        messages INTEGER DEFAULT 0
    )
    """)

    # WELCOME
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS welcome (
        guild_id INTEGER PRIMARY KEY,
        channel_id INTEGER,
        message TEXT,
        image TEXT
    )
    """)

    # AUTOROLES
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS autoroles (
        guild_id INTEGER PRIMARY KEY,
        role_id INTEGER
    )
    """)

    # REACTION ROLES
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reaction_roles (
        guild_id INTEGER,
        message_id INTEGER,
        emoji TEXT,
        role_id INTEGER,
        PRIMARY KEY (guild_id, message_id, emoji)
    )
    """)

    conn.commit()
