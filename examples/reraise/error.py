from pymaid.error import Warning


class PlayerNotExist(Warning):

    code = 12345
    message = '[player|{}] not exist in this server'
