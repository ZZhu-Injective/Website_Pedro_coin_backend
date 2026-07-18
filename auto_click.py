"""
Auto-click wherever your mouse is hovering.

Clicks at the current mouse position on a loop, so just move/hover the
mouse over whatever you want clicked.

Controls:
    1    -> start (3 second countdown so you can move the mouse into place)
    2    -> stop the auto-clicker
    Esc  -> quit the program

Run the terminal AS ADMINISTRATOR. Requires:
    py -m pip install keyboard pydirectinput
"""

import time
import keyboard
import pydirectinput

pydirectinput.PAUSE = 0  # remove the built-in delay between calls

INTERVAL = 0.02    # seconds between clicks
COUNTDOWN = 3      # seconds after pressing 1 before clicking starts
START_KEY = "1"
STOP_KEY = "2"
QUIT_KEY = "esc"


def main():
    running = False
    print(f"Ready. Press {START_KEY} to start, {STOP_KEY} to stop, {QUIT_KEY.upper()} to quit.",
          flush=True)

    while True:
        if keyboard.is_pressed(QUIT_KEY):
            print("Quitting.", flush=True)
            break

        if keyboard.is_pressed(START_KEY) and not running:
            # countdown so you can move the mouse where you want first
            for n in range(COUNTDOWN, 0, -1):
                print(f"Move your mouse into place... starting in {n}", flush=True)
                time.sleep(1)
            running = True
            print("Clicking at the mouse position...", flush=True)

        if keyboard.is_pressed(STOP_KEY) and running:
            running = False
            print("Stopped. Press 1 to start again.", flush=True)

        if running:
            x, y = pydirectinput.position()
            pydirectinput.click(x, y)
            time.sleep(INTERVAL)
        else:
            time.sleep(0.02)


if __name__ == "__main__":
    main()
