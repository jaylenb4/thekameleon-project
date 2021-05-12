from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, join_room, leave_room, emit
from flask_session import Session
from datetime import timedelta
import os, random


from classes.lobby import Lobby
from classes.user import User, Player
from classes.game import Game


app = Flask(__name__)

app.debug = True
app.config["SESSION_PERMANENT"] = True
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=5)
app.config['SESSION_FILE_THRESHOLD'] = 100 

app.config['SECRET_KEY'] = 'myhimitsunakey$'
Lobbies = {}

sess = Session(app)

socketio = SocketIO(app, manage_session=False, cors_allowed_origins='*', ping_timeout=10, ping_interval=2) #remove cors later

@app.route('/')
def home():
    """Homepage responsible for choosing to join or host a game"""
    return redirect(url_for('host'))   

@app.route('/host')
def host():
    """User can choose username. Redirects to lobby.html"""
    session.clear()
    return render_template('host.html')

@app.route('/join/<join_key>')
def join_w_key(join_key):
    if join_key in Lobbies:
        session['lobbyid']=join_key
        session['host']="0"
        return render_template('lobby.html', session=session)
    else:
        return redirect(url_for('host'))


@app.route('/lobby', methods=['GET', 'POST'])
def lobby():
    """User joins a lobby - new if host, existing if not. If the game/lobby doesn't exist, users are sent back to the join page. If the user already has a session username, send back to appropriate lobby. The session information is sent along with them (host - 1 or 0 (string), room - room id, username."""
    if session.get('lobbyid') in Lobbies:
        return render_template('lobby.html', session=session)
    elif request.method == 'POST' and request.form['host'] == "1":
        
        lobbyid = str(random.randint(1000, 9999))
        while lobbyid in Lobbies:
            lobbyid = str(random.randint(1000, 9999))

        Lobbies[lobbyid] = Lobby(lobbyid, app,socketio)
        session['lobbyid'] = lobbyid
        session['host'] = request.form['host']
        return render_template('lobby.html', session=session)
    elif request.method == 'POST' and request.form['lobbyid'] in Lobbies:
        session['lobbyid'] = request.form['lobbyid']
        session['host'] = request.form['host']
        return render_template('lobby.html', session=session)
    elif session.get('lobbyid') in Lobbies:
        return render_template('lobby.html', session=session)
    else:
        return redirect(url_for('host'))    

if __name__ == '__main__':
    socketio.run(app, port=int(os.environ.get('PORT')))