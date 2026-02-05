# Modem Forwarder

A Python-based modem-to-telnet bridge that provides a configurable BBS menu system. Users dialing in via modem are presented with a menu of available BBSes and can select which one to connect to.

## Features

- YAML-configurable BBS directory
- Terminal type detection (ANSI, PETSCII, ASCII, VT100)
- Auto-login macro support
- Logging to file and console

## Requirements

- Python 3.8+
- Physical modem connected via serial port
- pyserial
- pyyaml

## Installation

```bash
# Clone the repository
git clone https://github.com/chris-edwards-pub/modem_forwarder.git
cd modem_forwarder

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

Edit `config.yaml` to configure your setup:

### Global Settings

```yaml
global:
  modem_port: "/dev/ttyUSB0"    # Serial port for modem
  default_baudrate: 9600         # Modem baud rate
  welcome_message: "Welcome to the BBS Gateway!"
  log_file: "modem_forwarder.log"
  log_level: "INFO"              # DEBUG, INFO, WARNING, ERROR
```

### Adding BBS Entries

```yaml
bbs_entries:
  - name: "My Favorite BBS"
    description: "A great retro BBS"
    host: "bbs.example.com"
    port: 23
    auto_login: null             # No auto-login

  - name: "Auto-Login BBS"
    description: "BBS with automatic login"
    host: "auto.example.com"
    port: 6400
    auto_login:
      - wait: "login:"           # Wait for this text
      - send: "guest"            # Send username + Enter
      - wait: "password:"
      - send: "guest123"
```

### Auto-Login Actions

| Action | Value | Description |
|--------|-------|-------------|
| `wait` | string | Wait for text from BBS |
| `send` | string | Send text + carriage return |
| `send_raw` | string | Send text without carriage return |
| `delay` | int | Wait N milliseconds |

## Running

```bash
# Activate virtual environment
source .venv/bin/activate

# Run the forwarder
python main.py
```

The application will:
1. Initialize the modem and wait for incoming calls
2. Detect terminal type (or prompt user to select)
3. Display the BBS menu
4. Bridge the connection to the selected BBS
5. Return to waiting after the session ends

## Usage

When a caller connects:

1. Terminal type is auto-detected (or caller selects from menu)
2. BBS directory is displayed:
   ```
   Welcome to the BBS Gateway!

   === BBS Directory ===

   1. C64 BBS
      Commodore 64 public BBS
   2. Level 29
      Retro computing BBS

   0. Hang up
   ```
3. Caller enters a number to connect
4. Connection is bridged to the selected BBS
5. When BBS disconnects, modem hangs up

## Testing

```bash
# Run unit tests
pytest tests/ -v
```

## Debugging

For verbose logging, edit `config.yaml`:

```yaml
global:
  debug_modem: true
  log_level: "DEBUG"
```

Check `modem_forwarder.log` for detailed session information.

## License

MIT
