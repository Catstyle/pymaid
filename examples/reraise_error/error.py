from pymaid.error import Error


class PlayerNotExist(Error):

    code = 12345
    message_format = 'player not exist in this server'
