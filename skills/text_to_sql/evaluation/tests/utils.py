# sql_utils.py
import re
import sqlite3

def extract_sql(text):
    match = re.search(r'<sql>(.*?)</sql>', text, re.DOTALL)
    return match.group(1).strip() if match else ""

def execute_sql(sql):
    conn = sqlite3.connect('../data/data.db')
    cursor = conn.cursor()
    cursor.execute(sql)
    results = cursor.fetchall()
    conn.close()
    return results