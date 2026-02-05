# Modem Forwarder

A Python-based modem-to-telnet bridge that provides a configurable BBS menu system with auto-login support.

## Project Overview

This application bridges a physical modem (connected via serial port) to remote BBS systems over telnet. Users dialing in via modem are presented with a menu of available BBSes and can select which one to connect to.

## Architecture

```
┌─────────────┐     ┌─────────────────┐     ┌─────────────┐
│   Modem     │────▶│ Modem Forwarder │────▶│  BBS Server │
│  (Serial)   │◀────│   (Python)      │◀────│  (Telnet)   │
└─────────────┘     └─────────────────┘     └─────────────┘
```

### Module Structure

```
modem_forwarder/
├── main.py                  # Entry point, main loop
├── config.yaml              # BBS entries and settings
├── modem_forwarder/         # Package
│   ├── config.py            # YAML loading, dataclasses
│   ├── modem.py             # Serial I/O functions
│   ├── bridge.py            # Telnet bridge logic
│   ├── menu.py              # Menu display/selection
│   ├── terminal.py          # Terminal detection
│   ├── autologin.py         # Auto-login macros
│   └── logging_config.py    # Logging setup
└── tests/                   # Unit tests
```

### Key Modules

- **config.py**: Loads YAML configuration, defines `GlobalConfig`, `BBSEntry`, and `AutoLoginStep` dataclasses
- **modem.py**: Low-level serial I/O functions (`modem_print`, `modem_getch`, `force_hangup`, `init_modem`)
- **terminal.py**: Detects terminal type (ANSI, PETSCII, ASCII, VT100) or prompts user
- **menu.py**: Displays numbered BBS menu and handles user selection
- **bridge.py**: Bidirectional proxy between modem and telnet socket using selectors
- **autologin.py**: Executes login macros (wait/send/delay actions)

## Running the Application

```bash
# Install dependencies
pip install -r requirements.txt

# Run the forwarder
python main.py
```

The application will:
1. Initialize the modem and wait for incoming calls
2. Detect terminal type (or prompt user)
3. Display BBS menu
4. Bridge to selected BBS
5. Return to waiting for next call

## Configuration

Edit `config.yaml` to configure:

### Global Settings
```yaml
global:
  modem_port: "/dev/ttyUSB0"    # Serial port
  default_baudrate: 9600         # Modem baud rate
  welcome_message: "Welcome!"    # Greeting shown after connect
  log_file: "modem_forwarder.log"
  log_level: "INFO"              # DEBUG, INFO, WARNING, ERROR
```

### BBS Entries
```yaml
bbs_entries:
  - name: "Example BBS"
    description: "An example BBS"
    host: "bbs.example.com"
    port: 23
    auto_login: null             # null = no auto-login

  - name: "Auto-Login BBS"
    host: "auto.example.com"
    port: 6400
    auto_login:
      - wait: "login:"
      - send: "guest"
      - wait: "password:"
      - send: "guest123"
```

### Auto-Login Actions
| Action | Value | Description |
|--------|-------|-------------|
| `wait` | string | Wait for text from BBS |
| `send` | string | Send text + CR |
| `send_raw` | string | Send without CR |
| `delay` | int | Wait N milliseconds |

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_config.py -v

# Run with coverage
pytest tests/ --cov=modem_forwarder
```

## Development Notes

### Terminal Detection
- Sends ANSI cursor position request (`ESC[6n`)
- ANSI/VT100 terminals respond with `ESC[row;colR`
- If no response, user is prompted to select terminal type

### Connection Flow
1. `force_hangup()` - Ensure clean modem state
2. `init_modem()` - Send AT initialization commands
3. `wait_for_connect()` - Wait for CONNECT from modem
4. `get_terminal_type()` - Detect or prompt for terminal
5. `display_menu()` / `get_selection()` - Show BBS menu
6. `bridge_session()` - Proxy data between modem and BBS
7. `force_hangup()` - Clean up after session

### Adding New BBSes
Simply add entries to `bbs_entries` in `config.yaml`. No code changes required.

### Debugging
Set `debug_modem: true` and `log_level: "DEBUG"` in config for verbose logging.
