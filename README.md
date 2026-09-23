# Max Tracker Server

FastAPI-based backend server for the Max Tracker parental-control system, designed to run on a Raspberry Pi. The server handles WebSocket communication between the parent and child applications, relays usage/call-log reports, manages device state, and provides a physical GPIO shutdown button.

---

## 1. Project Overview

The server runs on a Raspberry Pi and provides:

- FastAPI HTTP backend
- WebSocket relay for parent/child communication
- Child pairing and token handling
- Persistent queued reports
- Physical Raspberry Pi shutdown button
- LED status indication
- Automatic server startup through `systemd`
- Automatic restart if the server crashes

Typical project structure:

```text
server/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── shutdown_button.py
│   ├── led_controller.py
│   └── ...
├── venv/
├── requirements.txt
└── README.md
```

> The exact files may vary as the project grows.

---

# 2. Raspberry Pi Requirements

Recommended setup:

- Raspberry Pi
- Raspberry Pi OS Lite 64-bit
- Internet/network connection
- Python 3
- Git
- GPIO button connected to the configured GPIO pin
- LEDs/components required by `led_controller.py`

Check the OS:

```bash
cat /etc/os-release
```

Check architecture:

```bash
uname -m
```

For a 64-bit Raspberry Pi OS, this should normally show:

```text
aarch64
```

---

# 3. Initial Raspberry Pi Setup

Update the system:

```bash
sudo apt update
sudo apt upgrade -y
```

Install basic tools:

```bash
sudo apt install -y git python3 python3-pip python3-venv
```

For GPIO support used by `gpiozero` and `lgpio`:

```bash
sudo apt install -y python3-lgpio liblgpio-dev swig
```

Verify `lgpio` at the system level:

```bash
python3 -c "import lgpio; print('system lgpio OK')"
```

---

# 4. Clone the Server

Move to the desired directory:

```bash
cd ~
```

Clone the repository:

```bash
git clone https://github.com/akaadityagupta/server.git max-tracker
```

Enter the server directory:

```bash
cd ~/max-tracker
```

If the repository is already cloned:

```bash
cd ~/max-tracker/server
git pull origin main
```

---

# 5. Python Virtual Environment

Create the virtual environment:

```bash
cd ~/max-tracker/server
python3 -m venv venv
```

Activate it:

```bash
source venv/bin/activate
```

Your terminal should show:

```text
(venv) maxtracer2009@Max-tracer:~/max-tracker/server $
```

Upgrade pip:

```bash
pip install --upgrade pip
```

Install project dependencies:

```bash
pip install -r requirements.txt
```

If `lgpio` is not included in `requirements.txt`, install it manually:

```bash
pip install lgpio
```

On Raspberry Pi, `lgpio` may need to be built from source. If the build reports a missing `swig` or `-llgpio` library, install:

```bash
sudo apt install -y swig python3-lgpio liblgpio-dev
```

Then retry:

```bash
pip install lgpio
```

Verify:

```bash
python -c "import lgpio; print('lgpio OK')"
```

Verify gpiozero:

```bash
python -c "from gpiozero import Button; print('gpiozero OK')"
```

---

# 6. Configuration

Configuration is stored in:

```text
app/config.py
```

The shutdown button uses:

```python
SHUTDOWN_BUTTON_PIN
SHUTDOWN_HOLD_SECONDS
```

Example:

```python
SHUTDOWN_BUTTON_PIN = 26
SHUTDOWN_HOLD_SECONDS = 3
```

The physical wiring must match the configured GPIO pin.

## GPIO numbering

`gpiozero.Button()` uses BCM GPIO numbering.

For example:

```python
Button(26)
```

means **BCM GPIO 26**, not physical board pin 26.

Always verify your physical wiring against the configured BCM GPIO number.

---

# 7. Testing the FastAPI Server Manually

Activate the virtual environment:

```bash
cd ~/max-tracker/server
source venv/bin/activate
```

Start the server:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

If successful, Uvicorn should report that it is running on:

```text
http://0.0.0.0:8000
```

Stop the server with:

```text
Ctrl+C
```

For request/access logging:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --access-log
```

---

# 8. Raspberry Pi GPIO Shutdown Button

The shutdown button is implemented in:

```text
app/shutdown_button.py
```

The flow is:

```text
Physical Button
      ↓
gpiozero
      ↓
when_held callback
      ↓
_shutdown_sequence()
      ↓
Shutdown LED
      ↓
short delay
      ↓
Raspberry Pi shutdown
```

The button must remain pressed for:

```python
SHUTDOWN_HOLD_SECONDS
```

seconds.

Example:

```python
self._button = Button(
    SHUTDOWN_BUTTON_PIN,
    pull_up=True,
    hold_time=SHUTDOWN_HOLD_SECONDS,
)
```

---

# 9. Shutdown Permission

Because the FastAPI server runs as a system service, the Python process cannot normally interactively enter a `sudo` password.

If `shutdown_button.py` uses:

```python
subprocess.run(
    ["sudo", "-n", "/usr/sbin/shutdown", "-h", "now"],
    check=True,
)
```

configure passwordless permission for only the required shutdown command.

Create a sudoers file:

```bash
sudo visudo -f /etc/sudoers.d/parental-server
```

Add:

```text
maxtracer2009 ALL=(root) NOPASSWD: /usr/sbin/shutdown
```

Save and exit.

Test that sudo does not request a password:

```bash
sudo -u maxtracer2009 sudo -n /usr/sbin/shutdown --help
```

Do not grant unrestricted `NOPASSWD: ALL` access to the application user.

---

# 10. Systemd Service

Create the service:

```bash
sudo nano /etc/systemd/system/parental-server.service
```

Example:

```ini
[Unit]
Description=Parental Control FastAPI Server
After=network.target

[Service]
User=maxtracer2009
WorkingDirectory=/home/maxtracer2009/max-tracker/server
ExecStart=/home/maxtracer2009/max-tracker/server/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --access-log
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

If the project uses a different port, replace `8000`.

---

# 11. Enable and Start the Server

After creating or changing the service:

```bash
sudo systemctl daemon-reload
```

Enable it at boot:

```bash
sudo systemctl enable parental-server.service
```

Start it:

```bash
sudo systemctl start parental-server.service
```

Check status:

```bash
sudo systemctl status parental-server.service
```

A healthy service should show:

```text
Active: active (running)
```

Restart after code changes:

```bash
sudo systemctl restart parental-server.service
```

---

# 12. Live Server Logs

To watch the server logs in real time:

```bash
sudo journalctl -u parental-server.service -f
```

Show the last 100 lines:

```bash
sudo journalctl -u parental-server.service -n 100 --no-pager
```

Show logs since the current boot:

```bash
sudo journalctl -u parental-server.service -b
```

Filter shutdown/GPIO messages:

```bash
sudo journalctl -u parental-server.service --no-pager | grep -i -E "shutdown|button|gpio"
```

---

# 13. Testing the Shutdown Button

Start live logs:

```bash
sudo journalctl -u parental-server.service -f
```

Hold the physical button for the configured number of seconds.

Expected log sequence:

```text
Shutdown button held for 3s
Shutting down Raspberry Pi
Shutdown LED activated
Executing shutdown command
```

If the button is detected but shutdown fails, look for:

```text
System shutdown command failed
```

and inspect the exception printed immediately after it.

---

# 14. GPIO Troubleshooting

## Error: `gpiozero not available`

Test:

```bash
source ~/max-tracker/server/venv/bin/activate
python -c "from gpiozero import Button; print('gpiozero OK')"
```

Install if required:

```bash
pip install gpiozero
```

## Error: `No module named 'lgpio'`

Install the Raspberry Pi dependencies:

```bash
sudo apt install -y python3-lgpio liblgpio-dev swig
```

Then inside the venv:

```bash
pip install lgpio
```

Verify:

```bash
python -c "import lgpio; print('lgpio OK')"
```

## Error: `cannot find -llgpio`

Install the development library:

```bash
sudo apt install -y liblgpio-dev
```

Then retry:

```bash
pip install lgpio
```

## Error: `/sys/class/gpio/gpio26/value` not found

This can indicate that gpiozero has fallen back to the Native pin factory because a supported GPIO backend was not available.

Check:

```bash
python -c "import lgpio; print('lgpio OK')"
```

Also check:

```bash
sudo journalctl -u parental-server.service -n 100 --no-pager
```

Look for messages such as:

```text
PinFactoryFallback
NativePinFactoryFallback
Shutdown button hardware init failed
```

---

# 15. WebSocket Logs

The server uses WebSockets for parent/child communication.

A successful child connection may appear as:

```text
WebSocket /ws/child [accepted]
connection open
```

Pairing may appear as:

```text
Child paired successfully (new token issued)
```

Queued reports may appear as:

```text
Queued USAGE_REPORT for parent
Queued CALL_LOG_REPORT for parent
```

An invalid token may appear as:

```text
Child sent invalid/unknown token
```

These messages are useful when debugging parent/child communication.

---

# 16. Updating the Server from GitHub

Before pulling updates, check for local changes:

```bash
git status
```

If you have local changes that must be preserved:

```bash
git stash push -m "local server changes"
```

Then:

```bash
git pull origin main
```

Restart the service:

```bash
sudo systemctl restart parental-server.service
```

Check:

```bash
sudo systemctl status parental-server.service
```

View live logs:

```bash
sudo journalctl -u parental-server.service -f
```

## Important

Do not use:

```bash
git reset --hard
```

unless you intentionally want to discard local changes.

---

# 17. Common Systemd Problems

## `status=203/EXEC`

This normally means systemd cannot execute the program specified in `ExecStart`.

Check:

```bash
ls -l /home/maxtracer2009/max-tracker/server/venv/bin/uvicorn
```

If the virtual environment does not exist:

```bash
cd ~/max-tracker/server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl restart parental-server.service
```

## Service repeatedly restarting

Check:

```bash
sudo journalctl -u parental-server.service -n 100 --no-pager
```

The Python traceback in the journal is usually the most useful information.

---

# 18. Useful Commands

### Service status

```bash
sudo systemctl status parental-server.service
```

### Start

```bash
sudo systemctl start parental-server.service
```

### Stop

```bash
sudo systemctl stop parental-server.service
```

### Restart

```bash
sudo systemctl restart parental-server.service
```

### Enable at boot

```bash
sudo systemctl enable parental-server.service
```

### Disable at boot

```bash
sudo systemctl disable parental-server.service
```

### Live logs

```bash
sudo journalctl -u parental-server.service -f
```

### Last 100 logs

```bash
sudo journalctl -u parental-server.service -n 100 --no-pager
```

### Git status

```bash
git status
```

### Update code

```bash
git pull origin main
```

---

# 19. Recommended Deployment Checklist

Before considering the Raspberry Pi deployment complete:

- [ ] Raspberry Pi OS Lite 64-bit installed
- [ ] Network connection working
- [ ] Git installed
- [ ] Python and `python3-venv` installed
- [ ] Repository cloned
- [ ] Virtual environment created
- [ ] `requirements.txt` installed
- [ ] `gpiozero` installed
- [ ] `lgpio` working inside the venv
- [ ] `liblgpio-dev` installed if required
- [ ] GPIO button wired to the correct BCM pin
- [ ] `SHUTDOWN_BUTTON_PIN` verified
- [ ] `SHUTDOWN_HOLD_SECONDS` verified
- [ ] Shutdown sudoers rule configured
- [ ] FastAPI starts manually
- [ ] `parental-server.service` configured
- [ ] Service enabled at boot
- [ ] Service reports `active (running)`
- [ ] WebSocket connection tested
- [ ] Child pairing tested
- [ ] Usage/call-log relay tested
- [ ] Physical shutdown button tested
- [ ] Live logs verified

---

# 20. Production Notes

Keep the Raspberry Pi/server credentials, tokens, private keys, and environment secrets out of Git.

Do not commit:

```text
.env
*.key
*.pem
secrets/
tokens/
```

Use environment variables or a protected configuration file for secrets.

When debugging production issues, check the systemd journal first:

```bash
sudo journalctl -u parental-server.service -f
```

The journal is the primary source for startup errors, GPIO initialization errors, WebSocket events, and shutdown-button events.
