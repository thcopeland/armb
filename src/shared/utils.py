import select

def socket_status(socket):
    read, write, err = select.select([socket], [socket], [], 0)
    return (socket in read, socket in write)

class BadMessageError(Exception):
    def __init__(self, description, message):
        self.message = description
        self.message_data = message
