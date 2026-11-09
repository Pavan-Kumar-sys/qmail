import sqlite3
from quantum_crypto import generate_quantum_keys

DB_NAME = "quantum_mail.db"

def init_db():
    """Builds our filing cabinet and creates two test users (Alice and Bob)."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Drawer 1: Users and their Quantum Keys
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            name TEXT,
            public_key TEXT,
            secret_key TEXT
        )
    ''')
    
    # Drawer 2: Encrypted Emails
    c.execute('''
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT,
            recipient TEXT,
            subject TEXT,
            kem_capsule TEXT,
            nonce TEXT,
            ciphertext TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create Alice and Bob automatically if they aren't in the cabinet yet
    for email, name in [("alice@qmail.com", "Alice"), ("bob@qmail.com", "Bob")]:
        c.execute("SELECT email FROM users WHERE email = ?", (email,))
        if not c.fetchone():
            keys = generate_quantum_keys()
            c.execute(
                "INSERT INTO users (email, name, public_key, secret_key) VALUES (?, ?, ?, ?)",
                (email, name, keys["public_key"], keys["secret_key"])
            )
            
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Filing cabinet (quantum_mail.db) created with Alice and Bob's quantum keys!")