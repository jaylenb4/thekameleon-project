
import random, uuid, os
from threading import Thread
from time import sleep
from flask_socketio import Namespace, join_room, leave_room, emit
from flask import Flask, request, session, render_template, copy_current_request_context



from classes.user import Player
from classes.game import Game

class Lobby(): #
    #icons from https://icons8.com/
    
    def __init__(self, lobbyid, app, sio): #,*args, **kwargs):
        self.app = app
        self.socketio = sio
        self.users={}
        self.lobbyid = lobbyid
        self.setup_events()
        self.livegame=False
        self.waiting_list = []
        self.Icons =  []
        for png in os.listdir(str(os.getcwd())+"/static/icons"):
            if png.endswith(".png"):
                self.Icons.append(str(png[:-4]))

    def setup_events(self):
        self.socketio.on_event('join', self.join, namespace='/lobby')
        self.socketio.on_event('text', self.text, namespace='/lobby')
        self.socketio.on_event('disconnect', self.disconnect, namespace='/lobby')
        self.socketio.on_event('leave', self.leave, namespace='/lobby') 
        self.socketio.on_event('start_game', self.start_game, namespace='/lobby')
        self.socketio.on_event('change_username', self.change_username, namespace='/lobby')
        self.socketio.on_event('change_icon', self.change_icon, namespace='/lobby')
        self.socketio.on_event('kick_user', self.kick_user, namespace='/lobby')

    def kick_user(self, uid):
        emit('kick_out', room=self.get_user(uid).get_sid())

    def change_icon(self, data):
        uid = data['uid']
        new_icon = data['new_icon']
        if new_icon.lower() not in self.Icons:
            return

        old_icon = data['old_icon']
        user = self.get_user(uid)
        self.Icons.append(old_icon)
        self.Icons.remove(new_icon.lower())
        user.change_icon(new_icon)
        emit('usernameDisplay', {'username': user.get_username(), 'uid': uid, 'icon': user.get_icon(), 'icons':self.Icons},room = user.get_sid())
        emit('update_users', list([(user.get_username(), user.get_icon(), user.get_wins(), user.get_uid()) for user in self.get_users()]), room=self.lobbyid)

    def change_username(self, new_username, uid):
        user = self.get_user(uid)
        user.change_username(new_username)
        emit('usernameDisplay', {'username': user.get_username(), 'uid': uid, 'icon': user.get_icon(), 'icons':self.Icons},room = user.get_sid())
        emit('update_users', list([(user.get_username(), user.get_icon(), user.get_wins(), user.get_uid()) for user in self.get_users()]), room=self.lobbyid)

    def rejoin(self, uid):
        if uid in self.waiting_list:
            self.waiting_list.remove(uid)
        user = self.get_user(uid)
        user.update_sid(request.sid)
        join_room(self.lobbyid)
        if not self.livegame:
            if(session.get('host') == "1"):
                emit('show_host_options', room=user.get_sid())
            emit('update_users', list([(user.get_username(), user.get_icon(), user.get_wins(), user.get_uid()) for user in self.get_users()]), room=self.lobbyid)
            emit('usernameDisplay', {'username': user.get_username(), 'uid': user.get_uid(), 'icon':user.get_icon(), 'icons':self.Icons},room = user.get_sid())
        else:
            emit('update_users', list([(user.get_username(), user.get_icon(), user.get_wins(), user.get_uid()) for user in self.get_users()]), room=self.lobbyid)
            emit('usernameDisplay', {'username': user.get_username(), 'uid': user.get_uid(), 'icon':user.get_icon(), 'icons':self.Icons},room = user.get_sid())
            self.game.rejoin(uid)

    def join(self, message):
        """Receiver for when a user joins a room. Assign the host. The user joins the room and it notifies all members that another user has joined."""
        assert(self.lobbyid == session.get('lobbyid'))
        uid = session.get('uid')
        if session.get('uid') in self.users:
            if uid in self.waiting_list:
                self.waiting_list.remove(uid)
            self.rejoin(session.get('uid'))
            return
        uid = str(uuid.uuid1())
        
        while uid in self.users:
            uid = str(uuid.uuid1())
        new_user = None
        if(session.get('host') == "1"):
            new_user = self.add_host(uid, request.sid)
            emit('show_host_options', room=new_user.get_sid())
        else:
            new_user = self.add_user(uid, request.sid)
        join_room(self.lobbyid)
        username = new_user.get_username()
        icon = new_user.get_icon()
        session['username'] = username
        session['uid'] = uid
        emit('update_users', list([(user.get_username(), user.get_icon(), user.get_wins(), user.get_uid()) for user in self.get_users()]), room=self.lobbyid)
        emit('usernameDisplay', {'username': username, 'uid': uid, 'icon':icon, 'icons':self.Icons},room = new_user.get_sid())

    def text(self, message, recipient):
        """Receiver for chat messages. Can send messages to the entire group or private messages."""
        assert(self.lobbyid == session.get('lobbyid'))
        emit('message', {'msg': session.get('username') + ' : ' + message['msg']}, room=self.lobbyid)

    def leave(self, message):
        """Receiver for when someone leaves the game/lobby. Removes the player from the game. The user leaves the room and it clears their session. Notifies other users in the room who has left."""
        uid = session.get('uid')
        user = self.remove_user(uid)
        leave_room(self.lobbyid)
        session.clear()
        emit('update_users', list([(user.get_username(), user.get_icon(), user.get_wins(), user.get_uid()) for user in self.get_users()]), room=self.lobbyid)

    def disconnect(self):
        @copy_current_request_context
        def check_presence(uid, lobby):
            sleep(5)
            if uid in lobby.waiting_list:
                if uid in lobby.users:
                    user = lobby.remove_user(uid)

        uid = session.get('uid')
        if uid is not None:
            self.waiting_list.append(uid)
            thread = Thread(target=check_presence, args=(uid,self,))
            thread.start()

    def start_game(self, data):
        emit('update_users', list([(user.get_username(), user.get_icon(), user.get_wins(), user.get_uid()) for user in self.get_users()]), room=self.lobbyid)
        new_game = Game(self, self.lobbyid, self.users, self.app, self.socketio, self.host,stimer=(data['secret_timer'] if 'secret_timer' in data else None), vtimer=(data['voting_timer'] if 'voting_timer' in data else None),category=(data['category'] if 'category' in data else "Movies"))
        self.add_game(new_game)
        self.livegame = True
        self.game.request()

    def end_game(self):
        self.game = None
        emit('show_host_options', room=self.get_user(self.host).get_sid())


    def add_host(self, uid, sid):
        """Add a new player as a host of an existing lobby"""
        self.host = uid
        new_host = self.add_user(uid, sid)
        new_host.become_host()
        return new_host


    def add_user(self, uid, sid):
        """Add a player to an existing lobby"""
        username = self.Icons.pop(random.randrange(len(self.Icons))).capitalize()
        new_user = Player(uid, sid,username)
        self.users[uid] = new_user
        return new_user

    def add_game(self, game):
        self.game = game

    def remove_user(self, uid):
        return self.users.pop(uid)

    def get_lobbyid(self):
        return self.lobbyid

    def get_users(self):
        return self.users.values()

    def get_user(self, uid):
        return self.users[uid]

    def get_user_username(self, uid):
        return self.users[uid].get_username()
