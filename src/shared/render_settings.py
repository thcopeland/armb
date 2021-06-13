import random, re

class RenderSettings:
    @staticmethod
    def deserialize(serialized):
        props = {
            "resolution_x": 1000,
            "resolution_y": 1000,
            "percentage": 100
        }
        
        for prop in serialized.split(","):
            m = re.match("(\w+)=(\d+)", prop)
            if m:
                props[m.group(1)] = int(m.group(2))
        
        return RenderSettings(props["resolution_x"], props["resolution_y"], props["percentage"])
    
    def __init__(self, res_x, res_y, percent):
        self.resolution_x = res_x
        self.resolution_y = res_y
        self.percentage = percent
        self.synchronization_id = random.getrandbits(32)
    
    def apply(self):
        pass
    
    def serialize(self):
        data = [
            ("resolution_x", self.resolution_x),
            ("resolution_y", self.resolution_y),
            ("percentage", self.percentage),
        ]
        
        return ",".join(map(lambda x: "{}={}".format(*x), data))
