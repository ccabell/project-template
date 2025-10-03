import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional

DATABASE_FILE = "transcripts.db"

def init_database():
    """Initialize the SQLite database with transcripts table"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transcripts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            content TEXT NOT NULL,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            file_size INTEGER,
            word_count INTEGER,
            description TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prompt_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transcript_id INTEGER,
            prompt TEXT NOT NULL,
            result TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (transcript_id) REFERENCES transcripts (id)
        )
    """)
    
    conn.commit()
    conn.close()

def save_transcript(filename: str, content: str, description: str = "") -> int:
    """Save a transcript to the database"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    word_count = len(content.split())
    file_size = len(content.encode('utf-8'))
    
    cursor.execute("""
        INSERT INTO transcripts (filename, content, file_size, word_count, description)
        VALUES (?, ?, ?, ?, ?)
    """, (filename, content, file_size, word_count, description))
    
    transcript_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return transcript_id

def get_all_transcripts() -> List[Dict]:
    """Get all transcripts from the database"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, filename, upload_date, file_size, word_count, description
        FROM transcripts
        ORDER BY upload_date DESC
    """)
    
    transcripts = []
    for row in cursor.fetchall():
        transcripts.append({
            'id': row[0],
            'filename': row[1],
            'upload_date': row[2],
            'file_size': row[3],
            'word_count': row[4],
            'description': row[5] or ""
        })
    
    conn.close()
    return transcripts

def get_transcript_content(transcript_id: int) -> Optional[str]:
    """Get the content of a specific transcript"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    cursor.execute("SELECT content FROM transcripts WHERE id = ?", (transcript_id,))
    result = cursor.fetchone()
    
    conn.close()
    return result[0] if result else None

def save_prompt_result(transcript_id: int, prompt: str, result: str) -> int:
    """Save a prompt result to the database"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO prompt_results (transcript_id, prompt, result)
        VALUES (?, ?, ?)
    """, (transcript_id, prompt, result))
    
    result_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return result_id

def get_recent_results(limit: int = 10) -> List[Dict]:
    """Get recent prompt results"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT pr.id, pr.prompt, pr.result, pr.timestamp, t.filename
        FROM prompt_results pr
        JOIN transcripts t ON pr.transcript_id = t.id
        ORDER BY pr.timestamp DESC
        LIMIT ?
    """, (limit,))
    
    results = []
    for row in cursor.fetchall():
        results.append({
            'id': row[0],
            'prompt': row[1],
            'result': row[2],
            'timestamp': row[3],
            'filename': row[4]
        })
    
    conn.close()
    return results

def delete_transcript(transcript_id: int) -> bool:
    """Delete a transcript and its associated results"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    # Delete associated prompt results first
    cursor.execute("DELETE FROM prompt_results WHERE transcript_id = ?", (transcript_id,))
    
    # Delete the transcript
    cursor.execute("DELETE FROM transcripts WHERE id = ?", (transcript_id,))
    
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    return deleted