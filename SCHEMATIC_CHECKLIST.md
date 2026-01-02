# SCHEMATIC CHECKLIST — CN-REMO SLAVE CONTROLLER

This is a schematic-level netlist checklist aligned to `SPEC.md`, `THEORY.md`, and `COMPONENTS.md`. It is written as a wiring checklist with suggested net names and reference designators. Pin numbers are intentionally omitted; map each signal to the correct pins per the TLIN14313‑Q1 and nRF54L10 datasheets.

---

## 0) Net Naming (recommended)

- `VBUS_12V_RAW` : CN‑REMO Red (incoming 12 V)
- `VSUP_PROT` : post‑reverse‑diode 12 V feeding TLIN VSUP
- `VCC_3V3` : TLIN LDO output (3.3 V)
- `VDD_nRF` : filtered 3.3 V domain for nRF54L10
- `GND` : common ground (CN‑REMO Black)
- `BUS_SIG_RAW` : CN‑REMO Yellow before series R
- `LIN_BUS` : TLIN LIN pin side of series R
- `PV_SENSE` : nRF ADC sense of TLIN PV divider
- `TLIN_DIV_ON` : GPIO control of TLIN VBAT divider
- `RF_50` : 50 Ω feed between RF network and antenna tuning

---

## 1) Connector and Cable Entry (CN‑REMO)

- **J1 (CN‑REMO female)**  
  - J1‑RED  → `VBUS_12V_RAW`  
  - J1‑YELLOW → `BUS_SIG_RAW`  
  - J1‑BLACK → `GND`

Optional protection at the connector:
- **D_VSUP_TVS**: `VBUS_12V_RAW` → `GND`
- **D_LIN_ESD**: `BUS_SIG_RAW` → `GND`

---

## 2) Power Entry and TLIN VSUP

### Reverse blocking
- **D_VSUP_REV** (Schottky/ideal diode):  
  - Anode → `VBUS_12V_RAW`  
  - Cathode → `VSUP_PROT`

### TLIN supply
- **U1 (TLIN14313‑Q1)**  
  - VSUP → `VSUP_PROT`  
  - GND → `GND`
  - VCC → `VCC_3V3`

### Required decoupling (near TLIN pins)
- **C_VSUP 100 nF**: `VSUP_PROT` → `GND`
- **C_VCC_BULK 10 µF**: `VCC_3V3` → `GND` (ESR 0.001–2 Ω)
- **C_VCC_HF 100 nF**: `VCC_3V3` → `GND`

### Optional bulk at entry
- **C_VBUS_BULK 10–47 µF**: `VBUS_12V_RAW` → `GND`

---

## 3) TLIN VBAT / PV Sense (optional but in COMPONENTS.md)

- **VBAT**: `VBUS_12V_RAW` → TLIN VBAT (pre-diode)
- **DIV_ON**: TLIN DIV_ON → `TLIN_DIV_ON` (nRF GPIO, enable only during PV sampling)
- **PV sense path**:
  - **R_PV_SER 470 ohm**: TLIN PV → `PV_SENSE` (nRF AIN)
  - **C_PV 20 pF**: TLIN PV → `GND`
  - **C_ADC 10 nF**: `PV_SENSE` → `GND` (optional ADC RC)

If PV sensing is not used, leave footprints DNP and keep DIV_ON low.

---

## 4) LIN Signal Path (CN‑REMO Yellow)

- **R_LIN_SER ~1 kΩ**: `BUS_SIG_RAW` → `LIN_BUS`
- **U1 LIN pin**: `LIN_BUS`
- **C_LIN 220 pF**: `LIN_BUS` → `GND`

Notes:
- Do **not** add an external pull‑up unless required; TLIN provides internal pull‑up.
- Place R_LIN_SER and C_LIN close to U1 LIN pin.

---

## 5) TLIN Control and Data Interfaces

### SPI control (required)
- **U1 nCS** → `SPI_CS` (add **R_SPI_SER** 22–47 Ω near nRF, optional)  
- **U1 SCLK** → `SPI_SCK` (R_SPI_SER optional)  
- **U1 SDI/WDI** → `SPI_MOSI` (R_SPI_SER optional)  
- **U1 SDO** → `SPI_MISO` (R_SPI_SER optional)

### Mode strap (ensure SPI mode)
- **R_nCS_PULLUP 10 kΩ**: `U1 nCS` → `VCC_3V3` (optional but recommended)

### LIN data interface (for actual bus traffic)
- **U1 TXD** → `UART_TX` (add **R_UART_SER** 22–47 Ω near nRF, optional)
- **U1 RXD** → `UART_RX` (add **R_UART_SER** 22–47 Ω near nRF, optional)

### Interrupt / Reset
- **U1 nINT** → `TLIN_nINT`  
  - **R_nINT_PULLUP 10 kΩ**: `U1 nINT` → `VCC_3V3`
- **U1 nRST** → `TLIN_nRST` (or tie to nRF reset logic)  
  - **R_nRST_PULLUP 10 kΩ**: `U1 nRST` → `VCC_3V3`

### VBAT divider control
- **U1 DIV_ON** → `TLIN_DIV_ON` (nRF GPIO)

### Unused TLIN pins
Follow TLIN datasheet guidance for any unused pins (e.g., WAKE, LIMP, HSS/FSO, PWM). Use DNP footprints or tie‑offs as recommended by the datasheet to avoid unintended modes.

---

## 6) nRF54L10 Power and Reset

### Power entry
- **FB1 (Ferrite bead 120 Ω @ 100 MHz)**: `VCC_3V3` → `VDD_nRF`
- **C_VDD_BULK 10 µF**: `VDD_nRF` → `GND`
- **C_VDD_2u2 xN**: `VDD_nRF` → `GND` (per Nordic reference)
- **C_VDD_100n xN**: `VDD_nRF` → `GND` (per Nordic reference)
- **C_VDD_10n xN**: `VDD_nRF` → `GND` (per Nordic reference)
- **L_DCDC 4.7 µH**: per Nordic DC/DC network

### Reset
- **R_RESET_SER 1 kΩ**: `nRF_RESET` (series)
- **C_RESET 2.2 nF**: `nRF_RESET` → `GND`

---

## 7) nRF54L10 Clocks

- **X_HFXO 32 MHz (2016, CL=8 pF)**: `nRF_XC1` ↔ `nRF_XC2`
- **X_LFXO 32.768 kHz (2012, CL=9 pF)**: `nRF_XL1` ↔ `nRF_XL2`

Optional DNP load caps:
- **C_XC1, C_XC2**: `nRF_XC1`/`nRF_XC2` → `GND`
- **C_XL1, C_XL2**: `nRF_XL1`/`nRF_XL2` → `GND`

Default assumption is internal load caps on nRF.

---

## 8) RF Network and Antenna

### Nordic reference RF network (place close to nRF ANT pin)
Populate per Nordic reference:
- L2 2.7 nH
- L3 3.5 nH
- L4 3.5 nH
- C6 1.5 pF
- C9 2.0 pF
- C11 0.3 pF
- C13 3.9 pF

Output net from RF network → `RF_50` (50 Ω CPWG feedline).

### Antenna tuning network (at antenna feed)
Place a 3‑part matching footprint; start with:
- **C_MATCH 5.1 pF**
- **L_MATCH 2.2 nH**
- **DNP pad** (per Abracon EVB)

### Antenna
- **ANT1 (AANI‑CH‑0070)**: `RF_50` → ANT feed
- Enforce all‑layer copper cutout + keepout per Abracon.

---

## 9) Debug and Test Points

Recommended test pads:
- `VBUS_12V_RAW`
- `VSUP_PROT`
- `VCC_3V3`
- `GND`
- `BUS_SIG_RAW` / `LIN_BUS`
- `nRF_RESET`
- SWDIO / SWDCLK / Vref / GND

---

## 10) Quick Sanity Checks

- Red wire is **input only**: no paths that can back‑feed `VBUS_12V_RAW`.
- TLIN VCC only supplies the nRF and local logic (no external loads).
- LIN bus is only connected through TLIN (single‑wire bus isolation).
- SPI mode is guaranteed at power‑up (nCS pulled high).
- RF and connector are on **opposite PCB edges**.
