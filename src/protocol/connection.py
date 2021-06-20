import socket, re, time
from collections import deque

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
    
    def complete(self):
        return self.progress == self.hmd_len()
    
    def h_len(self):
        return len(self.header)
        
    def hm_len(self):
        return len(self.header) + len(self.message)
        
    def hmd_len(self):
        return len(self.header) + len(self.message) + len(self.data)

class ARMBMessageTimeoutError(Exception):
    def __init__(self, message_data):
        super().__init__("Unable to send or receive entire message within timeout")
        self.message_data = message_data

class ARMBMessageFormatError(Exception):
    def __init__(self, message_data):
        super().__init__("Received message does not match ARMB format")
        self.message_data = message_data

class ARMBConnection:
    def __init__(self, socket, timeout):
        self.socket = socket
        self.msg_timeout = timeout
        self.error = None
        self.outgoing = deque()
        self.incoming = deque()
        self.closed = False
    
    def ok(self):
        return self.error is None and not self.closed
    
    def sending(self):
        return self.ok() and self.outgoing
    
    def receiving(self):
        return self.ok() and self.incoming and not self.incoming[-1].complete()
    
    def finished_receiving(self):
        return self.ok() and self.incoming and self.incoming[0].complete()

    def send(self, message, data=None):
        self.outgoing.append(ARMBMessageData.from_content(message, data))
    
    def receive(self):
        if self.finished_receiving():
            return self.incoming.popleft()
    
    def close(self):
        self.closed = True
        self.socket.close()
    
    def update(self, read, write):
        try:
            if self.sending():
                if time.time() - self.outgoing[0].start > self.msg_timeout:
                    self.error = ARMBMessageTimeoutError(self.outgoing)
                elif write:
                    self.__continue_sending()
                    if self.outgoing[0].complete():
                        print(f"{self.outgoing[0].start}: Sent message \"{self.outgoing[0].message.tobytes().decode()}\" in {self.outgoing[0].elapsed()} seconds")
                        self.outgoing.popleft()
            
            if self.receiving() and time.time() - self.incoming[-1].start > self.msg_timeout:
                self.error = ARMBMessageTimeoutError(self.incoming[-1])
            elif self.ok() and read:
                if self.receiving():
                    self.__continue_receiving()
                    if self.incoming[-1].complete():
                        print(f"{self.incoming[-1].start}: Received message \"{self.incoming[-1].message.tobytes().decode()}\" in {self.incoming[-1].elapsed()} seconds")
                else:
                    self.incoming.append(ARMBMessageData(memoryview(bytearray(16)), memoryview(bytes(0)), memoryview(bytes(0))))
        except (ConnectionResetError, BrokenPipeError):
            self.close()
    
    def __continue_sending(self):
        outgoing = self.outgoing[0]
        
        if outgoing.progress < outgoing.h_len():
            outgoing.progress += self.socket.send(outgoing.header[outgoing.progress:])
        
        if outgoing.h_len() <= outgoing.progress < outgoing.hm_len():
            outgoing.progress += self.socket.send(outgoing.message[(outgoing.progress - outgoing.h_len()):])
        
        if outgoing.hm_len() <= outgoing.progress < outgoing.hmd_len():
            outgoing.progress += self.socket.send(outgoing.data[(outgoing.progress - outgoing.hm_len()):])
        
        if outgoing.complete():
            outgoing.end = time.time()
    
    def __continue_receiving(self):
        incoming = self.incoming[-1]
        original_progress = incoming.progress
        
        if incoming.progress < incoming.h_len():
            incoming.progress += self.socket.recv_into(incoming.header[incoming.progress:])
            
            if incoming.progress == incoming.h_len():
                msg = ARMBMessageData.from_header(incoming.header)
                
                if msg:
                    # replace the top message
                    self.incoming.pop()
                    self.incoming.append(msg)
                    incoming = msg
                else:
                    self.error = ARMBMessageFormatError(incoming)
                    return
        
        if incoming.h_len() <= incoming.progress < incoming.hm_len():
            incoming.progress += self.socket.recv_into(incoming.message[(incoming.progress - incoming.h_len()):])
        
        if incoming.hm_len() <= incoming.progress < incoming.hmd_len():
            incoming.progress += self.socket.recv_into(incoming.data[(incoming.progress - incoming.hm_len()):])
        
        if incoming.complete():
            incoming.end = time.time()
        
        if incoming.progress == original_progress: # read 0 bytes, EOF
            self.close()
