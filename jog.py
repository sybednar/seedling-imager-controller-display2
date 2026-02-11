# jog.py
import time, gpiod
from gpiod.line import Direction, Value, Bias

CHIP = "/dev/gpiochip0"  # <-- change if gpioinfo shows a different chip
EN, STEP, DIR = 21, 20, 16

req = gpiod.request_lines(
    CHIP,
    consumer="jog_test",
    config={
        EN:   gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.INACTIVE), # EN low = enabled
        DIR:  gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.ACTIVE),   # start CW
        STEP: gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.INACTIVE),
    }
)

def pulses(n, delay=0.0025):
    for _ in range(n):
        req.set_value(STEP, Value.ACTIVE);  time.sleep(delay)
        req.set_value(STEP, Value.INACTIVE); time.sleep(delay)

try:
    print("Enable driver (EN low), DIR=HIGH (CW), 400 steps...")
    req.set_value(EN, Value.INACTIVE)  # enable
    req.set_value(DIR, Value.ACTIVE)   # CW
    pulses(400, delay=0.0025)

    time.sleep(0.5)

    print("Reverse (DIR low), 400 steps back (CCW)...")
    req.set_value(DIR, Value.INACTIVE)  # CCW
    pulses(400, delay=0.0025)

    print("Done. Restoring DIR high (CW).")
    req.set_value(DIR, Value.ACTIVE)

finally:
    # Optionally keep enabled for holding torque, or disable to cool
    print("Disable driver (EN high).")
    req.set_value(EN, Value.ACTIVE)