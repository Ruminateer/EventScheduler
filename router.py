#!/usr/bin/python3.7
# -*- coding: utf-8 -*-
import os
import datetime
import json
import flask
import requests
import pytz

import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery

import db


CLIENT_SECRETS_FILE = "client_secret.json"
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
API_SERVICE_NAME = 'calendar'
API_VERSION = 'v3'

app = flask.Flask(__name__)
app.secret_key = "development"


@app.route('/')
def show_home():
    if 'email' not in flask.session:
        return flask.redirect('authorize')

    args = flask.request.args
    emails = [flask.session['email']]
    if args.get('participants'):
        emails.extend(args.get('participants').split(','))
    if args.get('period'):
        period = float(args.get('period'))
    else:
        period = 7
    if args.get('duration'):
        duration = float(args.get('duration'))
    else:
        duration = 0

    data = {
        'email': flask.session['email'],
        'period': period,
        'duration': duration,
        'participants': args.get('participants') if args.get('participants')
                                                 else '',
        'intervals': []}

    try:
        data['intervals'] = schedule(emails, datetime.timedelta(days=period),
                                      datetime.timedelta(hours=duration))
    except NoToken as e:
        return (flask.render_template('index.html', **data) +
                'Error: {} didn\'t grant Scheduler permission to access calendar.'.format(e.args[0]))

    return flask.render_template('index.html', **data)


@app.route('/authorize')
def authorize():
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES)
    flow.redirect_uri = flask.url_for('oauth2callback', _external=True)
    authorization_url, state = flow.authorization_url(access_type='offline',
                                                    include_granted_scopes='true')

    flask.session['state'] = state

    return flask.redirect(authorization_url)


@app.route('/oauth2callback')
def oauth2callback():
    # Fetch token
    state = flask.session['state']
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, state=state)
    flow.redirect_uri = flask.url_for('oauth2callback', _external=True)
    authorization_response = flask.request.url
    # TODO: If user doesn't give permission,
    # oauthlib.oauth2.rfc6749.errors.AccessDeniedError: (access_denied)
    # will be raised from here.
    flow.fetch_token(authorization_response=authorization_response)

    # Query email address as key
    calendar = googleapiclient.discovery.build(
        API_SERVICE_NAME, API_VERSION, credentials=flow.credentials)
    email = calendar.calendars().get(calendarId='primary').execute()['id']

    # Store email and credentials
    flask.session['email'] = email
    db.store_cred(email, flow.credentials.token, flow.credentials.refresh_token)

    return flask.redirect('/')


@app.route('/signout')
def signout():
    if 'email' in flask.session:
        del flask.session['email']
    return flask.redirect('/')


@app.route('/revoke')
def revoke():
    if 'email' not in flask.session:
        return ('You need to <a href="/authorize">authorize</a> before ' +
                'revoking credentials.')

    credentials = get_credentials(flask.session['email'])

    response = requests.post('https://oauth2.googleapis.com/revoke',
        params={'token': credentials.token},
        headers = {'content-type': 'application/x-www-form-urlencoded'})

    if getattr(response, 'status_code') != 200:
        return 'An error occurred.'

    db.delete_cred(flask.session['email'])
    return flask.redirect('/signout')


class NoToken(Exception):
    pass

def schedule(emails, period, duration):
    start = datetime.datetime.now(pytz.timezone('US/Eastern'))
    end = start + period
    events = []
    for email in emails:
        calendar = googleapiclient.discovery.build(API_SERVICE_NAME, API_VERSION,
                                                   credentials=get_credentials(email))
        try:
            events_raw = calendar.events().list(calendarId='primary',
                                                timeMin=start.isoformat(),
                                                timeMax=end.isoformat()).execute().get('items', [])
        except google.auth.exceptions.RefreshError as err:
            db.delete_cred(email)
            raise NoToken(email) from err
        events.extend([(datetime.datetime.fromisoformat(event['start']['dateTime']),
                        datetime.datetime.fromisoformat(event['end']['dateTime']))
                        for event in events_raw])

    return [interval for interval in merge_revert(events,start,end)
                   if interval[1] - interval[0] > duration]


def merge_revert(intervals, start, end):
    if not intervals:
        return [(start, end)]

    intervals = sorted(intervals, key=lambda tup: tup[0])

    merged = []
    for interval in intervals:
        if not merged or interval[0] > merged[-1][1]:
            merged.append(list(interval))
        else:
            merged[-1][1] = max(merged[-1][1], interval[1])

    rev = []
    if start < merged[0][0]:
        rev.append((start, merged[0][0]))
    for i, _ in enumerate(merged[:-1]):
        rev.append((merged[i][1], merged[i+1][0]))
    if merged[-1][1] < end:
        rev.append((merged[-1][1], end))
    return rev


def get_credentials(email):
    tokens = db.load_cred(email)
    if not tokens:
        raise NoToken(email)
    with open(CLIENT_SECRETS_FILE, 'r') as secret:
        data = json.load(secret)["web"]
        return google.oauth2.credentials.Credentials(
            token=tokens[0],
            refresh_token=tokens[1],
            token_uri=data["token_uri"],
            client_id=data["client_id"],
            client_secret=data["client_secret"],
            scopes=SCOPES
        )


if __name__ == '__main__':
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    app.run('localhost', 8080, debug=True)
