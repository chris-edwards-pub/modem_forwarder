# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.2.0] - 2026-02-06

### Added
- Local access mode (`--local`) for testing without a modem using stdin/stdout
- `--debug` CLI flag to show log output on console in local mode
- Configurable inactivity timeout (`idle_timeout`, default 5 minutes)
- Timeout resets on any data flow in either direction (safe for Zmodem transfers)
- Timeout applies to bridge sessions, menu prompts, and external BBS selection
- CLI argument support via argparse (`--local`, `--debug`, `--config`)

## [2.1.0] - 2026-02-06

### Added
- External BBS list support with search and browsing from syncterm.lst
- SSH and rlogin protocol support alongside telnet
- Password masking with `*` characters on SSH login
- Anonymous SSH connections (press Enter at username to skip credentials)
- Retry prompt on SSH authentication failure instead of disconnecting
- Character echo for modem input fields

### Fixed
- Search prompt now echoes input and shows instructions
- Empty username no longer blocks SSH connection flow
- SSH auth failure returns to menu instead of hanging up

## [2.0.0] - 2026-02-05

### Added
- Multi-BBS menu system with YAML configuration
- Terminal type detection (ANSI, PETSCII, ASCII)
- Auto-login macro support with wait/send/delay actions
- Color support for PETSCII, ANSI, and VT100 menus
- Configurable modem initialization sequence
- Session logging to file
- Support for multiple ports for PETSCII terminal with Synchronet

### Fixed
- PETSCII color codes being corrupted by UTF-8 encoding
- PETSCII case inversion for Commodore 64 terminals
- Duplicate CONNECT message display
- Goodbye message now uses correct terminal emulation

## [1.0.0] - 2024-01-01

### Added
- Initial release
- Basic modem-to-telnet bridge functionality
- Single BBS connection support

[2.2.0]: https://github.com/chris-edwards-pub/modem_forwarder/releases/tag/v2.2.0
[2.1.0]: https://github.com/chris-edwards-pub/modem_forwarder/releases/tag/v2.1.0
[2.0.0]: https://github.com/chris-edwards-pub/modem_forwarder/releases/tag/v2.0.0
[1.0.0]: https://github.com/chris-edwards-pub/modem_forwarder/releases/tag/v1.0.0
