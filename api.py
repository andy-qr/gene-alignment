from itertools import cycle
import threading
 
api_keys = [
    "6aa784ef049697c8d1801ce03dd5b1344908",
    "99a5eb22f29477dc1049ad12fd597780d608",
    "00467ee59fa0c04894a15ab97c75ec6b5f09",
]
 
wait = 0.11
 

_key_cycle = cycle(api_keys)
_lock = threading.Lock()
 
def get_next_key():
    with _lock:
        return next(_key_cycle)