# Provisioning the Inky Immich Frame

## 1. Flash the SD card (Raspberry Pi Imager)
- OS: **Raspberry Pi OS Lite (64-bit)** (Bookworm).
- Edit settings before writing:
  - Hostname: `inky-frame`
  - Enable SSH, add your public key
  - Username `alex`
  - Locale/timezone `Europe/Berlin`
  - Wi-Fi: your test SSID + password (temporary, for the bench).

## 2. First boot + base packages
```bash
ssh pi@inky-frame.local
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y python3-venv git libopenjp2-7   # Pillow runtime dep
```

## 3. Enable SPI (required by the Inky panel)
```bash
sudo raspi-config nonint do_spi 0
sudo reboot
```

## 4. Tailscale (SSH support + Immich transport)
```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```
- Approve the node in the admin console.
- **Disable key expiry** for the `inky-frame` node (admin console → node → Disable key
  expiry) so the unattended device never needs re-auth.
- Verify Immich is reachable over the tailnet:
```bash
curl -s -o /dev/null -w '%{http_code}\n' http://your-immich-host:2283/api/server/ping   # expect 200
```

## 5. Install the app
```bash
git clone https://github.com/<you>/inky-immich-frame.git
cd inky-immich-frame
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[device]"
cp config.example.yaml config.yaml
# edit config.yaml: paste the scoped read-only Immich API key
```

## 6. Comitup (auto-hotspot Wi-Fi onboarding)
```bash
curl -O https://davesteele.github.io/comitup/latest/comitup-1.40-1_all.deb   # check latest
sudo apt install -y ./comitup-*.deb
```
- Set the hotspot name in `/etc/comitup.conf`:
  ```
  ap_name: InkyPi-Setup
  ```
- Comitup uses NetworkManager on Bookworm. Follow its post-install notes to hand
  Wi-Fi management to NetworkManager (disable `dhcpcd`/`wpa_supplicant` service conflicts
  per the comitup docs), then reboot.
- **VERIFY (open item from spec):** confirm the pre-baked test Wi-Fi still connects with
  comitup active; if not, connect once via the `InkyPi-Setup` hotspot so comitup stores it.

## 7. Enable the service
```bash
sudo cp deploy/inky-frame.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now inky-frame
systemctl status inky-frame        # expect active (running)
```
The album picker is then at `http://inky-frame.local:8080`.

## Acceptance checklist (bench test on your Wi-Fi, before deploying)
1. Flash → boot → `ssh pi@inky-frame.local` works; Tailscale node visible, key expiry disabled.
2. `python -c "from inky.auto import auto; i=auto(); print(i.resolution)"` prints `(800, 480)`.
3. Pick an album in the picker → a photo appears on the panel within a few seconds.
4. Switch to another album on the phone → the panel updates.
5. Comitup fallback: set a wrong Wi-Fi password / move out of range → `InkyPi-Setup`
   hotspot appears → join with phone → choose the real network → device reconnects →
   restore the test Wi-Fi.
6. Power-loss: pull and re-plug power → clean boot, `inky-frame` autostarts, the cached
   photo shows even before Immich is reached.
