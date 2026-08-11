#!/usr/bin/env python3
"""Toggle the Sino Wealth / CM Storm keyboard backlight with the Scroll Lock key.

These keyboards drive their backlight from the Scroll Lock LED: when the LED is
on, the backlight is on. Wayland compositors (Hyprland) do not toggle this LED
when Scroll Lock is pressed, and they reset any external LED change shortly
after it is applied. This daemon therefore:
  - tracks a desired LED state (starts ON),
  - toggles it on every Scroll Lock press (read from evdev),
  - keeps re-asserting it so the compositor cannot silently turn it off.
"""

import fcntl
import glob
import os
import select
import struct
import sys
import time

TARGET_NAME = "SINO WEALTH USB KEYBOARD"
BY_ID = "/dev/input/by-id/usb-SINO_WEALTH_USB_KEYBOARD-event-kbd"

EV_KEY = 0x01
KEY_SCROLLLOCK = 70
KEY_PRESS = 1

# struct input_event on 64-bit: timeval(2x long) + u16 type + u16 code + s32 value
INPUT_EVENT_STRUCT = "llHHi"
INPUT_EVENT_SIZE = struct.calcsize(INPUT_EVENT_STRUCT)

# Poll this fast so a compositor LED reset (which happens on every keystroke)
# is corrected quickly enough to be visually imperceptible.
POLL_INTERVAL = 0.005


def log(msg):
    print(msg, flush=True)


def find_led_brightness():
    for led in glob.glob("/sys/class/leds/*::scrolllock"):
        device = os.path.realpath(os.path.join(led, "device"))
        name = os.path.join(device, "name")
        if os.path.exists(name):
            try:
                with open(name) as fh:
                    if fh.read().strip() == TARGET_NAME:
                        return os.path.join(led, "brightness")
            except OSError:
                pass
    return None


def find_evdev():
    candidates = [BY_ID] if os.path.exists(BY_ID) else []
    if not candidates:
        for ev in glob.glob("/dev/input/event*"):
            try:
                fd = os.open(ev, os.O_RDONLY | os.O_NONBLOCK)
            except OSError:
                continue
            try:
                EVIOCGNAME = (2 << 30) | (0x45 << 8) | 0x06 | (256 << 16)
                buf = bytearray(256)
                n = fcntl.ioctl(fd, EVIOCGNAME, buf)
                name = bytes(buf[:n]).decode(errors="replace")
                if name == TARGET_NAME:
                    candidates.append(ev)
            except OSError:
                pass
            finally:
                os.close(fd)
    return candidates[0] if candidates else None


def read_brightness(path):
    try:
        with open(path) as fh:
            return int(fh.read().strip())
    except (OSError, ValueError):
        return None


def write_brightness(path, value):
    try:
        with open(path, "w") as fh:
            fh.write("1" if value else "0")
        return True
    except OSError as err:
        log(f"error: could not write brightness: {err}")
        return False


def set_trigger_none():
    for led in glob.glob("/sys/class/leds/*::scrolllock"):
        trigger = os.path.join(led, "trigger")
        try:
            with open(trigger) as fh:
                if "[none]" not in fh.read():
                    with open(trigger, "w") as fh2:
                        fh2.write("none")
        except OSError:
            pass


def main():
    log(f"{sys.argv[0]} starting: backlight initial state ON")

    set_trigger_none()
    desired = 1

    led_path = None
    evfd = None
    last_poll = 0.0
    last_reassert_log = 0.0

    while True:
        if led_path is None:
            led_path = find_led_brightness()
            if led_path is None:
                log("waiting for scrolllock LED sysfs entry...")
                time.sleep(2)
                continue

        if evfd is None:
            evdev = find_evdev()
            if evdev is None:
                log("waiting for keyboard evdev device...")
                time.sleep(2)
                continue
            evfd = os.open(evdev, os.O_RDONLY | os.O_NONBLOCK)
            log(f"watching {evdev}")

        now = time.monotonic()
        if now - last_poll >= POLL_INTERVAL:
            last_poll = now
            current = read_brightness(led_path)
            if current != desired:
                if now - last_reassert_log >= 30.0:
                    last_reassert_log = now
                    log(f"re-asserting backlight -> {'ON' if desired else 'OFF'}")
                if not write_brightness(led_path, desired):
                    led_path = None

        try:
            ready, _, _ = select.select([evfd], [], [], POLL_INTERVAL)
        except (OSError, ValueError):
            evfd = None
            continue

        if not ready:
            continue

        try:
            data = os.read(evfd, INPUT_EVENT_SIZE * 32)
        except OSError:
            evfd = None
            continue

        for off in range(0, len(data) - (len(data) % INPUT_EVENT_SIZE), INPUT_EVENT_SIZE):
            _, _, etype, code, value = struct.unpack_from(INPUT_EVENT_STRUCT, data, off)
            if etype == EV_KEY and code == KEY_SCROLLLOCK and value == KEY_PRESS:
                desired ^= 1
                log(f"scroll lock pressed: backlight -> {'ON' if desired else 'OFF'}")
                write_brightness(led_path, desired)


if __name__ == "__main__":
    main()
