class User():
    def __init__(self, uid, sid, username):
        """Player object with a unique id and a general username"""
        self.sid = sid #this is needed for communication
        self.uid = uid #this is a unique identifier that doesn't change
        self.username = username
        self.host = False
        self.add_icon(username.lower())
        self.wins = 0

    def become_host(self):
        """A player becomes the host of a lobby"""
        self.host = True

    def get_uid(self):
        return self.uid
    
    def get_sid(self):
        return self.sid

    def update_sid(self, sid):
        self.sid = sid

    def get_username(self):
        return self.username

    def get_role(self):
        if self.chameleon:
            return "Chameleon"
        else:
            return "Not Chameleon"

    def change_username(self, username):
        self.username = username

    def add_icon(self, name):
        self.icon = name
    
    def get_icon(self):
        return self.icon

    def change_icon(self, icon):
        self.icon = icon

    def add_win(self):
        #print("adding win for " + self.username)
        self.wins += 1
    
    def get_wins(self):
        return self.wins

class Player(User):
    
    def __init__(self, *args, **kwargs):
        self.chameleon = False
        self.votes = 0
        self.clue = ""
        self.wins = 0
        self.voted = False
        self.sent_clue = False
        self.has_lost=False
        super().__init__(*args, **kwargs)

    def reset_player(self):
        self.chameleon = False
        self.votes = 0
        self.clue = ""
        self.voted = False
        self.has_lost=False
        self.sent_clue = False
    

    def make_chameleon(self):
        self.chameleon = True

    def add_vote(self):
        self.votes +=1

    def add_clue(self, clue):
        self.clue = clue

    def get_clue(self):
        return self.clue

    def get_votes(self):
        return self.votes

    def get_role(self):
        return "Chameleon" if self.chameleon else "Not a Chameleon"

    # def reset(self):
    #     self.chameleon = False
    #     self.votes = 0
    #     self.clue = "N/A"
    #     self.has_lost = False
    #     self.voted = False

    def lose(self):
        self.has_lost = True

    def make_voted(self):
        self.voted = True

    def sent_clue_true(self):
        self.sent_clue = True