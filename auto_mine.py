"""
Auto-miner: clicks the mine button every 10 seconds.

Setup (one time):
    pip install pyautogui

How to use:
    1. Run:  python auto_mine.py
    2. When prompted, move your mouse over the green mine button
       and DON'T move it for 3 seconds. The script captures that spot.
    3. It then clicks that spot every 10 seconds.

To stop:
    - Press Ctrl+C in this terminal, OR
    - Slam your mouse into the very top-left corner of the screen
      (PyAutoGUI failsafe).
"""

import time
import sys

try:
    import pyautogui
except ImportError:
    sys.exit("pyautogui is not installed. Run:  pip install pyautogui")

# Moving the mouse to a screen corner aborts the script (safety switch).
pyautogui.FAILSAFE = True

INTERVAL_SECONDS = 30
CAPTURE_DELAY = 10


def capture_button_position():
    print(f"Move your mouse over the MINE button and hold it still "
          f"for {CAPTURE_DELAY} seconds...")
    for remaining in range(CAPTURE_DELAY, 0, -1):
        x, y = pyautogui.position()
        print(f"  capturing in {remaining}s  (mouse at {x}, {y})", end="\r")
        time.sleep(1)
    x, y = pyautogui.position()
    print(f"\nLocked on button position: ({x}, {y})")
    return x, y


def main():
    target_x, target_y = capture_button_position()

    print(f"\nClicking every {INTERVAL_SECONDS}s. "
          f"Press Ctrl+C (or shove mouse to top-left corner) to stop.\n")

    clicks = 0
    try:
        while True:
            pyautogui.click(target_x, target_y)
            clicks += 1
            print(f"Mined! (click #{clicks})  next click in {INTERVAL_SECONDS}s")
            time.sleep(INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print(f"\nStopped after {clicks} clicks.")


if __name__ == "__main__":
    main()
