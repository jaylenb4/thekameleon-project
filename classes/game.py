import abc
import random
import time
from flask_socketio import Namespace, join_room, leave_room, emit
from flask import Flask, request, session
from classes.user import User, Player
import os

class Configuration():
    def __init__(self, stimer=30, vtimer=30,category="Movies"):
        self.stimer = stimer
        self.vtimer = vtimer
        self.category = category.lower()

    def reset_config(self):
        self.timer_length = 30

    def get_timer_length(self):
        return self.timer_length

    def get_category(self):
        return self.word_category

    def set_timer_length(self, seconds=0):
        self.timer_length = seconds

class Timer():
    def __init__(self, timerid, minutes=0, seconds=0):
        self.timerid = timerid
        self.duration = (60 * minutes) + seconds
        self.live = False
    
    def turn_on(self):
        self.live = True

    def kill(self):
        self.live = False

class Game():

    def __init__(self, lobby, lobbyid, users, app, socketio, host,stimer=30, vtimer=30, category="Movies"):
        self.host = host
        self._lobby = lobby
        self._state = ChameleonSelection()
        self.players = {}
        self.lobbyid = lobbyid
        self.app = app
        self.socketio = socketio
        self.players = users
        self.timers = {}
        self.end_by_no_clue = False
        self.win_by_abstain = False
        self.add_config(stimer if stimer is not None else 30, vtimer if vtimer is not None else 30, category if category is not None else "Movies")
        self.words = self.generate_words()
        random.shuffle(self.words)
        self.setup_events()

    def add_config(self, *args, **kwargs):
        self.config = Configuration(*args, **kwargs)

    def generate_words(self):
        with open(str(os.getcwd() + "/static/categories/" + self.config.category) + ".txt", 'r') as f:
            total_words = f.read().split(',')
            return random.sample(total_words, 16)

    def setup_events(self):
        self.socketio.on_event('game_start', self.game_start, namespace='/lobby')
        self.socketio.on_event('to_secret_words', self.to_secret_words, namespace='/lobby')
        self.socketio.on_event('send_clue', self.receive_clue, namespace='/lobby')
        self.socketio.on_event('send_vote', self.receive_vote, namespace='/lobby')
        self.socketio.on_event('play_again', self.play_again, namespace='/lobby')
        self.socketio.on_event('timer_end', self.timer_end, namespace='/lobby')
        self.socketio.on_event('send_suggestion', self.receive_suggestion, namespace='/lobby')
        self.socketio.on_event('set_timer_length', self.set_timer_length, namespace='/lobby')
        
    def set_timer_length(self, seconds):
        self.config.set_timer_length(seconds)

    def receive_suggestion(self, target, uid):
        emit('display_suggestion', {'target': target, 'icon': self.get_player(uid).get_icon()}, room=self.lobbyid)

    def timer_end(self, timerid):
        timer = self.timers[timerid]
        if timer.live:
            timer.kill()
            emit('kill_timer', {'timerid':timer.timerid},room=self.lobbyid)
            self.next()
            self.request()
            
    def add_secret_word(self, word):
        self.secret_word = word

    def send_body(self, body, target):
        emit('body_replace', {'msg': body}, room= (self.lobbyid if target is None else target))

    def append_body(self, body, target):
        emit('body_append', {'msg':body}, room= (self.lobbyid if target is None else target))

    def add_timer(self, duration):
        timerid = str(random.randint(100, 999))
        while timerid in self.timers:
            timerid = str(random.randint(100, 999))

        dur = duration
        new_timer = Timer(timerid, seconds=dur)
        self.timers[timerid] = new_timer
        new_timer.turn_on()
        emit('add_timer', {'duration': new_timer.duration, 'timerid': new_timer.timerid}, room=self.lobbyid)

    def kill_timers(self):
        for k in list(self.timers.keys()):
            timer = self.timers[k]
            if timer.live:
                timer.kill()
                del self.timers[k]
                emit('kill_timer', {'timerid':timer.timerid},room=self.lobbyid)

    def send_individual(self, message, target):
        pass

    def game_start(self, stimer, ):
        self.next()
        self.request()

    def to_secret_words(self, message):
        self.next()
        self.request()
    
    def receive_clue(self, message):
        uid = session.get('uid')
        self.get_player(uid).add_clue(message['msg'])
        self.get_player(uid).sent_clue_true()
        if self.check_clues():
            self.next()
            self.request()

    def receive_vote(self, target, uid):
        if not self.get_player(uid).voted:
            self.get_player(target).add_vote()
            self.get_player(uid).make_voted()
            if self.check_votes():
                self.next()
                self.request()

    def play_again(self):
        self.send_body("<center><p>Waiting on new game<p><center>", None)
        for player in self.get_players():
            player.reset_player()
        self._lobby.end_game()

    def check_clues(self):
        for player in self.get_players():
            if player.get_clue() == "":
                return False
        return True

    def check_votes(self):
        vote_sum = 0
        for player in self.get_players():
            vote_sum+= player.get_votes()
        return vote_sum == len(self.get_players())

    def rejoin(self, uid):
        self._state.rejoin(self, uid)

    def request(self):
        self._state.handle(self)

    def next(self):
        self.kill_timers()
        self._state.next(self)

    def get_player(self, uid):
        return self.players[uid]

    def get_players(self):
        return self.players.values()
    
    def get_timer_length(self):
        return self.config.get_timer_length()

    def get_category(self):
        return self.config.get_category()

    def get_chameleon(self):
        chameleon = list([player for player in self.get_players() if player.get_role() == "Chameleon"])[0]
        return chameleon

    def get_words(self):
        return self.words

    def change_state(self, state):
        self._state = state

    def get_results(self):
        chameleon = self.get_chameleon()
        for player in self.get_players():
            if player.get_uid() != chameleon.get_uid() and not player.voted:
                self.win_by_abstain=True
        if self.win_by_abstain:
            return True
        max_votes = max(player.get_votes() for player in self.get_players())
        chameleon_win = True
        if len([player for player in self.get_players() if player.get_votes() == max_votes]) == 1 and self.get_chameleon().get_votes() == max_votes:
            chameleon_win = False

        return chameleon_win
        if chameleon_win:
            return "<h2>The Chameleon Wins!</h2>"
        else:
            return "<h2>The Chameleon was discovered and has lost!</h2>"

    def get_words(self):
        return self.words

class GameState(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def handle(self):
        pass

class ChameleonSelection(GameState):
    """
    -randomly pick a chameleon
    -display role to each member
    """
    def handle(self, game):
        players = list(game.get_players())
        chameleon = random.choice(players)
        chameleon.make_chameleon()

        for player in game.get_players():
            output = "<p><center>Your role is: " + player.get_role() + "</center></p></br>"
            game.send_body(output, player.get_sid())
        game.add_timer(10)

    def next(self, game):
        game.change_state(SecretWordSelection())

    def display(self, game):
        pass

    def rejoin(self, game, uid):
        player = game.get_player(uid)
        game.send_body("<p><center>Your role is: " + player.get_role() + "</center></p>", game.get_player(uid).get_sid())
        

class SecretWordSelection(GameState):
    """
    -select a random word from a set
    -send word to each member
    """
    def handle(self, game):
        secret_word = random.choice(game.get_words())
        game.add_secret_word(secret_word)
        table = self.generate_table(game.get_words())
        for player in game.get_players():
            if player.get_role() == "Not a Chameleon":
                game.send_body(self.highlight_word(table, secret_word), player.get_sid())
            else:
                game.send_body(table, player.get_sid())
        game.add_timer(5)        
    
    def generate_table(self,words):
        output = """<center><h2>Table of words<h2><center>\n"""
        output += "<table style='width:100%'>"
        x = 0
        for i in range(4):
            output+="   <tr>"
            for j in range(4):
                output+="       <td>"+words[x]+"</td>\n"
                x+=1 
            output+="   </tr>\n"
        output+="</table>"
        return output

    def highlight_word(self, table, word):
        return table.replace(word, "<span style='background-color: #FFFF00'>"+ word +"</span>")

    def next(self, game):
        game.change_state(SingleWordRound())

    def rejoin(self, game, uid):
        player = game.get_player(uid)
        table = self.generate_table(game.get_words())
        if player.get_role() == "Not a Chameleon":
            game.send_body(self.highlight_word(table, game.secret_word), player.get_sid())
        else:
            game.send_body(table, player.get_sid())

class SingleWordRound(GameState):
    """
    -have each player say a word with a 10 second timer
    """

    def handle(self, game):
        game.add_timer(game.config.stimer)
        output = "<input type='text' id='clue' size='60' placeholder='Enter your message here' /><button type='button' id='send_clue_button' class='btn btn-success' onclick=send_clue()>Send</button>"
        game.append_body(output, None)

    def next(self, game):
        game.change_state(ChameleonDebate())

    def rejoin(self, game, uid):
        player = game.get_player(uid)
        SecretWordSelection.rejoin(SecretWordSelection(), game, uid)
        if not player.sent_clue:
            game.append_body("<input type='text' id='clue' size='60' placeholder='Enter your message here' /><button type='button' id='send_clue_button' class='btn btn-success' onclick=send_clue()>Send</button>", player.get_sid())
        else:
            game.append_body("<input type='text' id='clue' size='60' placeholder='You sent : "+player.clue+ "' />", player.get_sid())


class ChameleonDebate(GameState):
    """
    -have each player select a player they think is the chamleon
    """
    def handle(self, game):
        chameleon = game.get_chameleon()
        for player in game.get_players():
            if player.get_clue() == "":
                game.end_by_no_clue=True
                game.next()
                game.request()
                return None
            
        game.add_timer(game.config.vtimer)
        game.send_body(self.generate_table(game.get_players()), None)
        
    def generate_table(self,players):
        output = """<center><h2>Vote for who you think the Chameleon is<h2><center>\n
        <div id='voting'>"""
        output += "<table style='width:75%' id='voting_table'>"
        x = 0
        for player in players:
            output+="<tr id=\'"+ player.get_uid() +"\'>\n <td>" + player.get_username() + "</td><td>" + (player.get_clue() if player.get_clue() != "" else "N/A")  + "</td></tr>\n"
        output+="""</table>
            <br>
            <input type="button" class="ok" id="submit_vote" value="Submit" /></br>
        </div>
        <script>
            $("#voting_table tr").click(function(){
                $(this).addClass('selected').siblings().removeClass('selected');
                var uid=this.id;
                var username=$(this).find('td:first').html();
                console.log("uid:" + uid);
                console.log("username:" + username)
                show_suggestion(uid);
            });
            $('.ok').live('click', function(e){
                if($("#voting_table tr.selected").attr('id') == $("#uidDisplay").text()){
                    $('#voting').append("Can't vote for self!<br>")
                } else {
                    send_vote($("#voting_table tr.selected").attr('id'));
                    $('#submit_vote').hide();
                    $('#voting_table tr').unbind('click');
                }
                console.log($("#voting_table tr.selected").attr('id'));

            });
        </script>
        """
        #
        return output

    def next(self, game):
        game.change_state(GameEnd())

    def rejoin(self, game, uid):
        player = game.get_player(uid)
        game.send_body(self.generate_table(game.get_players()), player.get_sid())


class GameEnd(GameState):
    """
    -reveal who the chameleon was (victory or loss)
    -offer play again button
    """

    def handle(self, game):
        chameleon_win=game.get_results()
        output=""
        chameleon = game.get_chameleon()
        if game.end_by_no_clue:
            output="<h2>The Game is over since a player did not submit a clue!</h2>"
        elif chameleon_win:
            chameleon.add_win()
            output=""
            if game.win_by_abstain:
                output="<h2>The Chameleon Wins since a player abstained!</h2>"
            else:
                output="<h2>The Chameleon was not discovered and has won!</h2>"
        else:
            [player.add_win() for player in game.get_players() if (not player.chameleon and not player.has_lost)]
            output="<h2>The Chameleon was discovered and has lost!</h2>"
        emit('update_users', list([(user.get_username(), user.get_icon(), user.get_wins()) for user in game.get_players()]), room=game.lobbyid)

        output+="<h3>The Chameleon was " + game.get_chameleon().get_username() + ".</h3>"
        if not game.end_by_no_clue:
            output+= self.generate_table(game.get_players())
        game.send_body(output, None)
        game.append_body("\n<center><button type='button' id='next' onclick=play_again()>PLAY AGAIN</button></center>", game.get_player(game.host).get_sid())
    
    def generate_table(self,players):
        output = """<center><h2>Votes are in!<h2><center>\n
        <div id='vote_results'>"""
        output += "<table style='width:50%'>"
        x = 0
        for player in players:
            output+="<tr>\n <td>"+player.get_username()+"</td>\n<td>" + str(player.get_votes()) + "    </td></tr>\n"
        output+="</table>\n</div>"

        return output

    def next(self, game):
        game.reset_game()

    def rejoin(self, game, uid):
        player = game.get_player(uid)
        if player.host:
            game.append_body("\n<center><button type='button' id='next' onclick=play_again()>PLAY AGAIN</button></center>", game.get_player(game.host).get_sid())
        else:
            game.send_body("<h3>The Chameleon was " + game.get_chameleon().get_username() + ".</h3>", player.get_sid())
