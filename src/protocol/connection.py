import socket, re, time

class ARMBMessageData:
    @staticmethod
    def from_content(message, data):
        data = data or bytes(0)
        header = bytes("ARMB {:02x} {:08x}".format(len(message), len(data)).encode())
        return ARMBMessageData(memoryview(header), memoryview(message), memoryview(data), 0, True)
    
    @staticmethod
    def from_header(header):
        match = re.match("ARMB ([a-f0-9]{2}) ([a-f0-9]{8})", header.tobytes().decode())
        if match:
            msg_len, data_len = int(match.group(1), 16), int(match.group(2), 16)
            return ARMBMessageData(memoryview(header), memoryview(bytearray(msg_len)), memoryview(bytearray(data_len)), len(header), False)
    
    def __init__(self, header=None, message=None, data=None, progress=0, outgoing=True):
        self.start = time.time()
        self.end = None
        self.header = header
        self.message = message
        self.data = data
        self.progress = progress
        self.outgoing = outgoing
    
    def elapsed(self):
        return self.end - self.start
    
    def h_len(self):
        return len(self.header)
        
    def hm_len(self):
        return len(self.header) + len(self.message)
        
    def hmd_len(self):
        return len(self.header) + len(self.message) + len(self.data)

class ARMBMessageTimeoutError(Exception):
    def __init__(self, message_data):
        self.message = "Unable to send or receive entire message within timeout"
        self.message_data = message_data

class ARMBMessageFormatError(Exception):
    def __init__(self, message_data):
        self.message = "Received message does not match ARMB format"
        self.message_data = message_data

class ARMBConnection:
    def __init__(self, socket, timeout):
        self.socket = socket
        self.msg_timeout = timeout
        self.error = None
        self.outgoing = None
        self.incoming = None
    
    def ok(self):
        return self.error is None
    
    def ready_to_send(self):
        return self.ok() and self.outgoing is None
    
    def ready_to_receive(self):
        return self.ok() and self.incoming is None
        
    def sending(self):
        return self.ok() and self.outgoing
    
    def receiving(self):
        return self.ok() and self.incoming

    def finished_sending(self): # only practical for internal use
        return self.sending() and self.outgoing.progress == self.outgoing.hmd_len()

    def finished_receiving(self):
        return self.receiving() and self.incoming.progress == self.incoming.hmd_len()
        
    def get_received(self):
        if self.finished_receiving():
            received = self.incoming
            self.incoming = None
            return received
    
    def send(self, message, data=None):
        if not self.ready_to_send():
            return False
        
        self.outgoing = ARMBMessageData.from_content(message, data)
        return True
    
    def receive(self):
        if not self.ready_to_receive():
            return False
        
        self.incoming = ARMBMessageData(memoryview(bytearray(16)), memoryview(bytes(0)), memoryview(bytes(0)))
        return True
    
    def close(self):
        self.socket.close()
    
    def update(self, read, write):
        if self.sending():
            if time.time() - self.outgoing.start > self.msg_timeout:
                self.error = ARMBMessageTimeoutError(self.outgoing)
            elif write:
                self.__continue_sending()
                if self.finished_sending():
                    # log somewhere
                    print(f"{self.outgoing.start}: Sent message \"{self.outgoing.message.tobytes().decode()}\" in {self.outgoing.elapsed()} seconds")
                    self.outgoing = None
        
        if self.receiving():
            if time.time() - self.incoming.start > self.msg_timeout:
                self.error = ARMBMessageTimeoutError(self.incoming)
            elif read:
                self.__continue_receiving()
                if self.finished_receiving():
                    # log somewhere
                    print(f"{self.incoming.start}: Received message \"{self.incoming.message.tobytes().decode()}\" in {self.incoming.elapsed()} seconds")
                    pass
    
    def __continue_sending(self):
        if self.outgoing.progress < self.outgoing.h_len():
            self.outgoing.progress += self.socket.send(self.outgoing.header[self.outgoing.progress:])

        if self.outgoing.h_len() <= self.outgoing.progress < self.outgoing.hm_len():
            self.outgoing.progress += self.socket.send(self.outgoing.message[(self.outgoing.progress - self.outgoing.h_len()):])
        
        if self.outgoing.hm_len() <= self.outgoing.progress < self.outgoing.hmd_len():
            self.outgoing.progress += self.socket.send(self.outgoing.data[(self.outgoing.progress - self.outgoing.hm_len()):])
        
        if self.outgoing.progress == self.outgoing.hmd_len():
            self.outgoing.end = time.time()
    
    def __continue_receiving(self):
        if self.incoming.progress < self.incoming.h_len():
            self.incoming.progress += self.socket.recv_into(self.incoming.header[self.incoming.progress:])
            
            if self.incoming.progress == self.incoming.h_len():
                msg = ARMBMessageData.from_header(self.incoming.header)
                
                if msg:
                    self.incoming = msg
                else:
                    self.error = ARMBMessageFormatError(self.incoming)
                    return
        
        if self.incoming.h_len() <= self.incoming.progress < self.incoming.hm_len():
            self.incoming.progress += self.socket.recv_into(self.incoming.message[(self.incoming.progress - self.incoming.h_len()):])
        
        if self.incoming.hm_len() <= self.incoming.progress < self.incoming.hmd_len():
            self.incoming.progress += self.socket.recv_into(self.incoming.data[(self.incoming.progress - self.incoming.hm_len()):])
        
        if self.incoming.progress == self.incoming.hmd_len():
            self.incoming.end = time.time()
