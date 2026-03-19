# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] - 2026-02-27

### Added

- Initial release
- `Brain` class with `@on_query()` decorator for handler registration
- `QueryContext` with response methods: `reply()`, `ask_clarification()`, `reply_error()`, `say_processing()`, `play_hold_music()`, `terminate_call()`
- `auto_process()` for automatic heartbeat and hold music management
- Capabilities advertisement and tool checking via `has_tool()` and `available_tools`
- API key authentication (constructor param or `HUBUI_BRAIN_API_KEY` env var)
- Debug mode with full WebSocket traffic logging
- Graceful shutdown with configurable timeout
