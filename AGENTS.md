# Project objectives

- A hardware MITM between an existing LG HVAC unit wired to an LG controller unit.
    - Non-invasively installed inside the controller's plastic enclosure.
    - Reachable as a Thread-based, Matter-supported end device.

# Reference material

## HVAC components
- Unit Wiring: Page 28 [ARNU123NJA4 Installation Guide](reference/hvac/MFL65003108_00_210820_00_WEB_IM_English.pdf)
- Controller Wiring: Page 77 (marked 152) [PREMTA000 User Guide](reference/hvac/LG-PREMTA000-User-Guide.pdf)
- Controller Settings: Page 85 (marked 168) [PREMTA000 User Guide](reference/hvac/LG-PREMTA000-User-Guide.pdf)
- Control Protocol: [protocol.md](reference/hvac/esphome-lg-controller/protocol.md)
- Group Control Wiring: Page 4 [PZCWRCG3 Cable Assembly Installation Guide ](reference/hvac/3828A20860M-IM.pdf)

## Wireless control device
- Transceiver: [TLIN14313-Q1](reference/device/tlin1431-q1.pdf)
- Wireless SoC: [nRF54L10](reference/device/nRF54L15_nRF54L10_nRF54L05_Datasheet_v1.0.pdf)
    - [Reference Layout](./reference/device/nRF54L15-QFAA%20Reference%20Layout%200_8)
- Antenna: [AANI-CH-0070](reference/device/AANI-CH-0070.pdf)

# Environment

## Utilities
  - Before reading large PDF documents, use the `pdf` utility in your `$PATH` to split it into individual pages.
  - For analyzing Excel documents, use `uv run --with openpyxl python -c "import openpyxl ..."`.

## Capabilities
  - `.png`/`.jpeg`/`.gif`/`.webp` LLM perception enabled.
  - `.pdf` LLM perception enabled.
  - Unrestricted internet access enabled.