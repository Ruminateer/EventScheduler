import sqlite3
from flask import g
from router import app

DATABASE = './credentials.sqlite3'

def _get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def store_cred(email, token, refresh_token):
    _get_db().execute('''
        INSERT OR REPLACE INTO creds
        VALUES ('{}', '{}', '{}')
    '''.format(email, token, refresh_token))
    _get_db().commit()

def delete_cred(email):
    _get_db().execute('''
        DELETE FROM creds
        WHERE useremail='{}'
    '''.format(email))
    _get_db().commit()

def load_cred(email):
    return _get_db().execute('''
        SELECT token, refresh_token FROM creds
        WHERE useremail='{}'
    '''.format(email)).fetchone()
