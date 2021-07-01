import random, re

class RenderSettings:
    @staticmethod
    def deserialize(serialized):
        props = {
            "resolution_x": 1000,
            "resolution_y": 1000,
            "percentage": 100,
            "display_mode": 'AREA'
        }
        
        for prop in serialized.split(","):
            m = re.match("(\w+)=(\w+)", prop)
            if m:
                name, val = m.groups()
                if val.isnumeric():
                    val = int(val)
                props[name] = val
        
        return RenderSettings(props["resolution_x"], props["resolution_y"], props["percentage"], props["display_mode"])
    
    def __init__(self, res_x, res_y, percent, display_mode):
        self.resolution_x = res_x
        self.resolution_y = res_y
        self.percentage = percent
        self.display_mode = display_mode
        self.synchronization_id = random.getrandbits(32)
    
    def serialize(self):
        data = [
            ("resolution_x", self.resolution_x),
            ("resolution_y", self.resolution_y),
            ("percentage", self.percentage),
            ("display_mode", self.display_mode)
        ]
        
        return ",".join(map(lambda x: "{}={}".format(*x), data))
