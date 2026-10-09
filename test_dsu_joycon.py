
import time
from dsu_joycon import DSUJoyCon

joycon = DSUJoyCon()

try:
    for i in range(30):
        joycon.update()
        print("Aceleración:", joycon.get_accels()[0])
        time.sleep(0.05)
finally:
    joycon.close()