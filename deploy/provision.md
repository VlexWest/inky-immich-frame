# Provisioning the Inky Immich Frame

Verified end-to-end on a Pi Zero 2 W + Inky Impression 7.3" (Spectra 6 / E673)
running Raspberry Pi OS **Trixie** (Debian 13, Python 3.13).

## 1. Flash the SD card (Raspberry Pi Imager)
- OS: **Raspberry Pi OS Lite (64-bit)**. Trixie and Bookworm both work.
- Edit settings before writing:
  - Hostname (e.g. `inky-frame`) — this becomes the address the picker is opened at
  - Enable SSH, add your public key
  - Username + locale/timezone
  - Wi-Fi: SSID + password

> **The Wi-Fi must be 2.4 GHz.** The Pi Zero 2 W has no 5 GHz radio. If your router
> uses a separate SSID per band, enter the 2.4 GHz one — a 5 GHz-only SSID is
> invisible to the Pi, so it silently never joins and never appears on the network.

## 2. First boot + base packages
```bash
ssh <user>@<hostname>.local
sudo apt update
sudo apt install -y python3-venv python3-dev git libopenjp2-7
```
`python3-dev` is required: the `inky` dependency `spidev` is a C extension and its
wheel build fails with `fatal error: Python.h: No such file or directory` without it.
`libopenjp2-7` is a Pillow runtime dep.

## 3. Enable SPI **and** I2C, and free the SPI chip-select
The panel needs SPI for pixels and **I2C for its EEPROM**, which is what
`inky.auto()` reads to identify the board. Without I2C you get
`RuntimeError: No EEPROM detected!`.

```bash
sudo raspi-config nonint do_spi 0
sudo raspi-config nonint do_i2c 0
echo "dtoverlay=spi0-0cs" | sudo tee -a /boot/firmware/config.txt
sudo reboot
```

`dtoverlay=spi0-0cs` stops the kernel claiming GPIO8 as spi0 CS0 so `inky` can drive
it. Without it the library prints

```
Woah there, some pins we need are in use!
  ⚠️  Chip Select: (line 8, GPIO8) currently claimed by spi0 CS0
```

and `gpiodevice` **exits the process** — no traceback, so it looks like a hang.

After rebooting, verify:
```bash
ls /dev/spidev*                 # expect /dev/spidev0.0
ls /dev/i2c-*                   # expect /dev/i2c-1
sudo i2cdetect -y 1             # expect the panel EEPROM at 0x50
```

> **If the I2C bus is completely empty** (nothing at 0x50 or anywhere), the panel is
> not making contact — on a self-soldered header this means cold joints. Reflow them
> (~370 °C, chisel tip); the power and GND pins are hardest because the ground plane
> sinks heat. No software setting can work around a joint that isn't connected.

## 4. Tailscale (SSH support + Immich transport)
```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --hostname=<hostname>
```
- Approve the node in the admin console.
- **Disable key expiry** for the node (admin console → node → Disable key expiry) so
  the unattended device never needs re-auth.
- Verify Immich is reachable over the tailnet:
```bash
curl -s -o /dev/null -w '%{http_code}\n' http://your-immich-host:2283/api/server/ping   # expect 200
```

## 5. Install the app
```bash
git clone https://github.com/<you>/inky-immich-frame.git
cd inky-immich-frame
python3 -m venv .venv
.venv/bin/pip install -e ".[device]"
cp config.example.yaml config.yaml
chmod 600 config.yaml
# edit config.yaml: immich_url + the scoped read-only Immich API key
```
The API key needs read access to albums and assets (`album.read`, `asset.read`,
`asset.view`). `config.yaml` is gitignored — never commit it.

Check the panel before going further:
```bash
.venv/bin/python -c "from inky.auto import auto; i=auto(); print(i.resolution)"   # (800, 480)
```

## 6. Enable the service
Edit `deploy/inky-frame.service` first if your username/home differ from `pi`.
```bash
sudo cp deploy/inky-frame.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now inky-frame
systemctl status inky-frame        # expect active (running)
journalctl -u inky-frame -f        # watch the first render
```
The picker is then at `http://<hostname>.local` (port 80 — nothing to type after the
name). A refresh takes ~40 s; the page shows a "loading" note and locks the buttons
while it runs, so it never hangs the browser.

## 7. Comitup (auto-hotspot Wi-Fi onboarding) — do this LAST
Comitup takes over Wi-Fi management, so a mistake here can drop your SSH session.
Do it once everything else is verified, with the device physically in reach.

On Trixie, comitup is packaged — no `.deb` download needed:
```bash
sudo apt install -y comitup
```

**Verified on Trixie:** comitup coexists with the netplan-rendered NetworkManager
connection (`netplan-wlan0-<SSID>`). It adopts it — `comitup-cli` reports
`State: CONNECTED, Connection: <SSID>` — and survives a reboot without touching it.

### Name the hotspot
```bash
sudo sed -i '/^# *ap_name:/a ap_name: MyFrame-Setup' /etc/comitup.conf
```
Comitup creates its hotspot NM connection **at install time**, using the name that
was configured then. If you set `ap_name` afterwards, delete the stale connection so
it gets recreated:
```bash
sudo nmcli connection delete comitup-<nnn>-0000
sudo systemctl restart comitup
nmcli -g 802-11-wireless.ssid connection show MyFrame-Setup-0000   # verify
```

### Give the portal port 80 (required)
comitup serves its setup portal on port 80 — **the same port this app uses**. Without
this, hotspot mode shows the app (which cannot reach the server anyway) instead of the
wifi portal, and the phone never gets a captive-portal prompt.

```bash
sudo cp deploy/comitup-callback /usr/local/bin/comitup-callback
sudo chmod +x /usr/local/bin/comitup-callback
sudo sed -i '/^# *external_callback:/a external_callback: /usr/local/bin/comitup-callback' /etc/comitup.conf
sudo systemctl restart comitup
```
The callback stops `inky-frame` in `HOTSPOT` state and starts it again on `CONNECTED`.

### Testing the fallback
Downing the connection (`nmcli connection down …`) does **not** test this: comitup
just reconnects, which is correct behaviour. To reach hotspot mode the network has to
be genuinely unknown. Delete the connection, and restore it afterwards from netplan:
```bash
sudo nmcli connection delete netplan-wlan0-<SSID>   # hotspot must now come up and stay
# ... test the portal at 10.41.0.1 ...
sudo netplan apply                                   # restores the connection
```
Back up `/etc/netplan/` first — on Trixie the wifi credentials live there, **not** in
`/etc/NetworkManager/system-connections/` (which is empty).

## Acceptance checklist (bench test before deploying)
1. Boot → SSH works; Tailscale node visible, key expiry disabled.
2. `.venv/bin/python -c "from inky.auto import auto; i=auto(); print(i.resolution)"` → `(800, 480)`.
3. Open the picker on a phone → pick an album → a photo appears on the panel (~40 s).
4. Switch albums → the panel updates; the button locks and a loading note shows while it runs.
5. Comitup fallback: wrong Wi-Fi password / out of range → `InkyPi-Setup` hotspot appears
   → join with a phone → choose the real network → device reconnects.
6. Power-loss: pull and re-plug → clean boot, service autostarts, the cached photo shows
   even before Immich is reached.
