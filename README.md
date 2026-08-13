# sino-wealth-backlight

Toggle a Sino Wealth / CM Storm keyboard backlight with the **Scroll Lock** key on Linux (KDE/Wayland/Hyprland).

Many budget gaming keyboards (Cooler Master Devastator/CM Storm, and other boards built around the
Sino Wealth `258a:0001` controller) drive their backlight from the **Scroll Lock LED**: when the
LED is on, the backlight is on.

On X11 this worked with `xset led 3`. Wayland compositors like Hyprland don't toggle the Scroll Lock
LED when the key is pressed, and they overwrite any external LED change on every keystroke, so the
backlight can't be controlled — it either stays off or blinks. This daemon fixes that.

## How it works

The daemon runs as a **root systemd service** and:

1. Watches the keyboard's evdev device for `Scroll Lock` key presses (`/dev/input/by-id/usb-SINO_WEALTH_USB_KEYBOARD-event-kbd`).
2. Toggles the desired backlight state on each press.
3. Polls `/sys/class/leds/*::scrolllock/brightness` every 5&nbsp;ms and re-asserts the desired state,
   so the compositor's LED resets (which happen on every keystroke) are corrected too fast to be visible.
4. Starts with the backlight **ON** and sets the LED trigger to `none` so the kernel driver can't fight it.

Device paths are discovered dynamically (keyboard name match + LED sysfs scan), so it survives input
device renumbering between boots and handles keyboard replugs.

## Requirements

- Linux (systemd)
- Python 3 (stdlib only, no pip dependencies)
- A keyboard that reports its backlight via the Scroll Lock LED

## Install

```sh
git clone https://github.com/CodexOmega/sino-wealth-backlight.git
```

```sh
cd sino-wealth-backlight
```

```sh
sudo install -m 755 sino-wealth-backlight.py /usr/local/bin/sino-wealth-backlight.py
sudo install -m 644 sino-wealth-backlight.service /etc/systemd/system/sino-wealth-backlight.service
sudo systemctl daemon-reload
sudo systemctl enable --now sino-wealth-backlight
```

## Usage

- Press **Scroll Lock** to toggle the backlight on/off.
- The backlight starts **ON** at boot and stays on (even at the login screen).

Check it with:

```sh
systemctl status sino-wealth-backlight
journalctl -u sino-wealth-backlight -f
```

Stop it anytime with `sudo systemctl stop sino-wealth-backlight` (the backlight keeps its last state).

## Configuration

The script targets this specific keyboard by default. If your keyboard differs, edit the constants
at the top of `sino-wealth-backlight.py`:

| Constant | Purpose |
|---|---|
| `TARGET_NAME` | Input device name shown in `/sys/class/input/*/device/name` / `evtest` |
| `BY_ID` | Stable device symlink, fallback scan of `/dev/input/event*` is used if absent |

To verify your device is a match:

```sh
cat /sys/class/input/event*/device/name   # find your keyboard
cat /sys/class/leds/*::scrolllock/brightness   # echo 1 to test the backlight
```

## Troubleshooting

- **Backlight still off after install**: confirm the Scroll Lock LED sysfs entry exists
  (`ls /sys/class/leds/ | grep scrolllock`) and that `echo 1 | sudo tee /sys/class/leds/*::scrolllock/brightness`
  turns it on.
- **Flicker while typing**: the compositor resets the LED on every keystroke. The 5&nbsp;ms poll
  should make this invisible; if you still see it, lower `POLL_INTERVAL`.
- **Wrong device targeted**: check `journalctl -u sino-wealth-backlight -f` to see which device it
  attached to, and adjust `TARGET_NAME`.

## License

MIT
