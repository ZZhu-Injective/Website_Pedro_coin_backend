"""
Auto-press the spacebar into a game.

Uses pydirectinput (scan-code input) so games recognize the keypress.

Controls:
    1    -> start (you get a 3 second countdown to click into the game)
    2    -> stop the auto-presser
    Esc  -> quit the program

Run the terminal AS ADMINISTRATOR. Requires:
    py -m pip install keyboard pydirectinput
"""

import time
import keyboard
import pydirectinput

pydirectinput.PAUSE = 0  # remove the built-in delay between calls

INTERVAL = 0.02    # seconds between presses
HOLD = 0.05                                                                                                                                                                                                                                                                                                                          # how long each press is held down (helps games register it)
COUNTDOWN = 3      # seconds after pressing 1 before spamming starts
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
            # countdown so you can click into the game window first
            for n in range(COUNTDOWN, 0, -1):
                print(f"Click into the GAME now... starting in {n}", flush=True)
                time.sleep(1)
            running = True
            print("Spamming SPACE...", flush=True)

        if keyboard.is_pressed(STOP_KEY) and running:
            running = False   
            print("Stopped. Press 1 to start again.", flush=True)

        if running:
            pydirectinput.keyDown("space")
            time.sleep(HOLD)
            pydirectinput.keyUp("space")
            time.sleep(INTERVAL)
        else:
            time.sleep(0.02)


if __name__ == "__main__":
    main()
