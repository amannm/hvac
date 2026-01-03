# Project objectives
- A wireless controller for an existing LG HVAC unit wired to an existing LG controller unit.
    - Non-invasively installed inside the controller's plastic enclosure.
    - Reachable as a Thread-based, Matter-supported end device.

# Reference material

## HVAC components
- Unit Wiring: Page 28 [ARNU123NJA4 Installation Guide](reference/hvac/MFL65003108_00_210820_00_WEB_IM_English/28.pdf)
- Controller Wiring: Page 77 (marked 152) [PREMTA000 User Guide](reference/hvac/LG-PREMTA000-User-Guide/77.pdf)
- Controller Settings: Page 85 (marked 168) [PREMTA000 User Guide](reference/hvac/LG-PREMTA000-User-Guide/85.pdf)
- Control Protocol: [protocol.md](reference/hvac/esphome-lg-controller/protocol.md)
- Group Control Wiring: Page 4 [PZCWRCG3 Cable Assembly Installation Guide ](reference/hvac/3828A20860M-IM/4.pdf)

## Wireless control device
- Transceiver: [TLIN14313-Q1](datasheets/tlin1431-q1)
- Wireless SoC: [nRF54L10](datasheets/nRF54L15_nRF54L10_nRF54L05_Datasheet_v1.0)
- Antenna: [AANI-CH-0070](datasheets/AANI-CH-0070)

## Electronic design automation tools
- [KiCad Developer Documentation](reference/eda/kicad-dev-docs)
- [KiCad User Documentation](reference/eda/kicad-doc)
- [KiCad Source Code](reference/eda/kicad)
- [Freerouting Source Code](reference/eda/freerouting)

## Software stack
- [Matter 1.5 Specification](reference/matter)

# Environment

## Utilities
- Before reading large PDF documents, use the `pdf` utility in your `$PATH` to split it into individual pages.
- For analyzing Excel documents, use `uv run --with openpyxl python -c "import openpyxl ..."`.
- For working with electronic design files, use the `kicad-cli` in your `$PATH`.
- For working with PCB auto-routing `.dsn` (Specctra) files, use the `freerouting-cli` CLI in your `$PATH`.
- Use the `kicad_sch_api` Python library to manipulate schematic files.

## Capabilities
- `.png`/`.jpeg`/`.gif`/`.webp` LLM perception enabled.
- `.pdf` LLM perception enabled.
- Unrestricted internet access enabled.

# Techniques

## Extracting component information from datasheets
1. Symbol: .kicad_sym (or imported foreign library symbol)
2. Footprint: .kicad_mod (inside a library folder)
3. Metadata row: SQLite (+ .kicad_dbl mapping) for MPN, manufacturer, key electrical params, package, footprint name, datasheet path, supplier SKUs, etc. ￼

## Developing KiCad schematic files
1. Parse/edit schematics with the `kicad-sch-api` Python library.
2. Validate with `kicad-cli sch erc ... --exit-code-violations` in scripts/CI.
3. Export artifacts (PDF/SVG/netlist/BOM) with `kicad-cli` for deterministic outputs.