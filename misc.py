import re
import struct

def named_unpack(format, string):
    ''' hacky wrapper for struct.unpack() that allows for easier format specification '''
    format = re.sub("[^0-9a-zA-Z?/|]", "", format)
    sizes = {"x": 1, "c": 1, "b": 1, "B": 1, "?": 1, "h": 2, "H": 2, "i": 4, "I": 2, "l": 4, "L": 4, "q": 8, "Q": 8, "f": 0, "d": 0} #don"t use d or f!
    items = format.split("/")
    ret = dict()
    for item in items:
        base = item.split("|")
        count = re.sub("[^0-9]", "", base[0])
        byte = str(re.sub("[^a-zA-Z?]", "", base[0]))
        count = int(count) if len(count) != 0 else 1
        if byte not in ["p", "s"]:
            for i in range(1, count+1):
                sub = string[0:sizes[byte]]
                suffix = str(i) if count > 1 else ""
                key = base[1]+suffix if len(base[1]) > 0 else int(suffix)
                ret[key] = struct.unpack("<" + byte, sub)[0]
                string = string[sizes[byte]:]
        else:
            sub = string[0:count]
            if byte != "x":
                ret[base[1]] = struct.unpack("<" + str(count) + byte, sub)[0]
            string = string[count:]

    return ret