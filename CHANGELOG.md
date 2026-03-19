# Changelog

## 1.0.1 - 2026-03-19

### Added
- Radera markerade filer direkt i listan via `Backspace`/`Delete`.

### Fixed
- macOS `.app`-bygge: hantering av Tcl/Tk när Python använder `lib/tcl8.x` + `lib/tk8.x` istället för `Tcl.framework` + `Tk.framework`.
- macOS `.app`-start: undvik Tk-menyradsfix i `frozen`-läge för att minska risken för abort vid `TkpInit` på macOS 26+.

### Changed
- add semver VERSION + bump_version tooling

## Unreleased

### Added
### Fixed
### Changed
