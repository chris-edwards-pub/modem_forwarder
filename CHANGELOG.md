# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[2.0.0]: https://github.com/chris-edwards-pub/modem_forwarder/releases/tag/v2.0.0
[1.0.0]: https://github.com/chris-edwards-pub/modem_forwarder/releases/tag/v1.0.0
