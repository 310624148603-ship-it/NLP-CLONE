import sqlite3
import datetime

def seed_database():
    conn = sqlite3.connect('legal_vector_store.db')
    cursor = conn.cursor()
    
    # Schema for MVA Baseline
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS legal_statutes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            section TEXT NOT NULL,
            title TEXT,
            content TEXT NOT NULL,
            jurisdiction TEXT DEFAULT 'INDIA',
            last_updated TIMESTAMP
        )
    ''')

    baseline_data = [
        (
            '183', 
            'Punishment for speeding', 
            'Whoever drives a motor vehicle in contravention of the speed limits referred to in section 112 shall be punishable in the manner as specified in sub-section (2). ... LMV: 1000-2000 INR, MPV/HPV: 2000-4000 INR.',
            'INDIA',
            datetime.datetime.now()
        ),
        (
            '194D', 
            'Penalty for not wearing protective headgear', 
            'Whoever drives a motor cycle or causes or allows a motor cycle to be driven in contravention of the provisions of section 129 or the rules or regulations made thereunder shall be punishable with a fine of one thousand rupees and he shall be disqualified for holding licence for a period of three months.',
            'INDIA',
            datetime.datetime.now()
        )
    ]

    cursor.executemany('''
        INSERT INTO legal_statutes (section, title, content, jurisdiction, last_updated)
        VALUES (?, ?, ?, ?, ?)
    ''', baseline_data)

    conn.commit()
    conn.close()
    print("PERSONA_6_REPORT: MVA_BASELINE_SEED_COMPLETE. SQLITE_READY.")

if __name__ == "__main__":
    seed_database()
