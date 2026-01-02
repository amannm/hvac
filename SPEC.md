# SPEC - LG PREMTA000 Embedded Wireless Slave Controller

This document defines the target device to be built for the LG PREMTA000 wired wall controller ecosystem. It consolidates the intended architecture, electrical/mechanical constraints, and firmware behavior described in `THEORY.md` and `COMPONENTS.md`, plus component datasheets and KiCad schematic rules.

Primary references (local):
- TLIN14313-Q1 datasheet (pinout, electrical limits, typical application)
- nRF54L15/L10/L05 datasheet v1.0 (QFN40 pinout, operating conditions, reference circuitry notes)
- nRF54L15 QFAA reference layout v0.8 (decoupling + RF values)
- Abracon AANI-CH-0070 datasheet (layout, matching, keepout)
- KiCad documentation (hierarchical sheet/label rules)

---

## 1. Purpose and Goals

### Primary objective
Build a non-invasive, in-enclosure wireless slave controller that:
- Fits inside the PREMTA000 controller enclosure.
- Connects in parallel to the existing 3-wire CN-REMO bus.
- Acts as a slave wired controller node (not an inline man-in-the-middle).
- Exposes HVAC control via Thread + Matter, with BLE commissioning.

### Must-have properties
- No disruption of the existing LG master controller behavior.
- Fail-safe: if the device dies/unpowers, the HVAC system still works via the existing master.
- No back-feeding of the 12 V Red wire.
- Protocol-compatible: listens and transmits only when safe on the single-wire bus.
- Matter-compliant mapping for thermostat-like control.

### Non-goals (explicitly avoided)
- Inline bus interception or modification of the master controller.
- Replacing the master controller or the indoor unit.
- Acting as a Thread Border Router.

---

## 2. System Context (Target Environment)

### HVAC installation
- Indoor unit: LG ARNU123NJA4
- Wired wall controller: LG PREMTA000

### LG CN-REMO bus
- 3-wire cable:
  - Red = 12 V
  - Yellow = Signal
  - Black = GND
- Physical layer: single-wire, dominant-low, recessive-high behavior.
- Protocol: UART-like 104 bps, 8N1, 13-byte frames, checksum = (sum of bytes) XOR 0x55.
- The LG system supports two wired controllers on one indoor unit (Master + Slave).

---

## 3. High-Level Architecture

### Block diagram (logical)
```
CN-REMO (12V, SIG, GND)
   -> TLIN14313-Q1 (12 V single-wire PHY + 3.3 V LDO)
         -> nRF54L10 (logic + Thread/Matter + BLE)
               -> 2.4 GHz chip antenna (AANI-CH-0070)
```

### Architectural principles
- Parallel bus node: connect in parallel to Yellow/Black, and power from Red.
- Slave identity: uses a slave controller source ID (e.g., 0x28 / 0x2A).
- Polite bus access: transmit only when the line is idle (high) for >=500 ms and verify echo.

---

## 4. Mechanical and PCB Constraints

### PCB stackup
- 0.115 mm copper / 0.508 mm FR-4 / 0.115 mm copper (2-layer thin PCB).

### Placement constraints
- CN-REMO connector: edge-mounted, horizontal, short edge, opposite the antenna.
- Antenna: edge-mounted; requires full-layer copper cutout and keepout.
- Must fit within PREMTA000 controller enclosure without modifying the existing controller.

---

## 5. Electrical Architecture

### 5.1 Key net names (schematic convention)
- VBUS_12V_RAW: CN-REMO Red (incoming 12 V)
- VSUP_PROT: post-reverse-diode 12 V feeding TLIN VSUP
- VCC_3V3: TLIN LDO output (3.3 V)
- VDD_nRF: filtered 3.3 V domain for nRF54L10
- GND: common ground (CN-REMO Black)
- BUS_SIG_RAW: CN-REMO Yellow before series R
- LIN_BUS: TLIN LIN pin side of series R
- SPI_CS/SCK/MOSI/MISO: TLIN SPI control
- UART_TX/UART_RX: TLIN TXD/RXD data interface
- TLIN_nINT/TLIN_nRST: TLIN interrupt/reset lines
- TLIN_DIV_ON: GPIO control for TLIN VBAT divider enable
- PV_SENSE: nRF AIN sense of VBAT (via PV divider)
- RF_ANT: RF output from nRF matching network
- SWDIO/SWDCLK/nRF_RESET: debug/programming

### 5.2 Power entry and protection (TLIN front-end)
- Input: 12 V from CN-REMO Red wire.
- Reverse blocking required to prevent back-feeding the bus:
  - D_VSUP_REV (Schottky or ideal diode) in series with Red input.
- Optional but recommended protection:
  - TVS on 12 V input (VBUS_12V_RAW -> GND)
  - ESD/TVS on LIN/SIG if cable runs are long/exposed

### 5.3 TLIN14313-Q1 electrical constraints and defaults
- Recommended operating ranges (TLIN datasheet):
  - VSUP, VBAT: 5.5 V to 28 V
  - VLIN: 0 V to 28 V
  - Logic pins (3.3 V variant): 0 V to 3.465 V
  - Operating temperature: -40 C to 150 C
- VCC LDO output: 3.3 V +/- 2.5%, up to 125 mA.
- Required decoupling (near TLIN pins):
  - C_VSUP 100 nF at VSUP
  - C_VCC_BULK 10 uF at VCC (ESR 0.001-2 ohm)
  - C_VCC_HF 100 nF at VCC
- VBAT/PV divider (TLIN internal):
  - VBAT connects before the reverse diode (VBUS_12V_RAW).
  - DIV_ON enables the internal divider; for the 3.3 V device the divider ratio is 1:9.
  - DIV_ON is GPIO-controlled; default low and enable only during PV sampling to minimize loading.
  - PV is clamped for VBAT above ~20 V (3.3 V LDO variant).
  - Recommended for PV sense: 470 ohm series + 20 pF to GND; optional ADC RC (10 nF at nRF AIN).
- Internal pull-ups/pull-downs (floating pins behavior):
  - TXD pull-up ~350 k
  - WDT/CLK pull-up ~240 k
  - WDI/SDI pull-up ~240 k
  - PIN/nCS pull-up ~240 k
  - DIV_ON pull-down ~370 k
  - LIN pull-up ~45 k
  - EN/nINT pull-down ~350 k
  - nRST pull-up ~45 k (open-drain pin)
- nRST behavior: open-drain; add external 10 k pull-up to VCC_3V3 for clean logic.
- SPI mode selection: ensure PIN/nCS is high at power-up (add 10 k pull-up to VCC_3V3).

### 5.4 CN-REMO bus physical layer
- Responder node configuration.
- Series element on SIG: R_LIN_SER ~1 k between BUS_SIG_RAW and LIN_BUS.
- EMI cap: C_LIN 220 pF from LIN_BUS to GND, placed near TLIN LIN pin.
- No external pull-up required (TLIN has internal pull-up).

### 5.5 TLIN <-> nRF digital interfaces
- SPI control (TLIN in SPI mode):
  - TLIN nCS -> nRF SPI_CS
  - TLIN CLK -> nRF SPI_SCK
  - TLIN SDI -> nRF SPI_MOSI
  - TLIN SDO -> nRF SPI_MISO
- UART data path (LG bus I/O):
  - TLIN TXD -> nRF UART_TX
  - TLIN RXD -> nRF UART_RX
- PV divider control:
  - TLIN DIV_ON -> nRF GPIO (TLIN_DIV_ON), drive high only when sampling PV
- Optional series resistors (22-47 ohm) on SPI/UART near nRF for signal integrity.
- TLIN_nINT and TLIN_nRST pulled up to VCC_3V3 with 10 k.

### 5.6 nRF54L10 power domain
- Selected SoC: nRF54L10 (fixed for this design).
- Recommended operating conditions (nRF datasheet):
  - VDD: 1.7 V to 3.6 V (extended: 1.7 V to 3.4 V)
  - VDDPOR: 1.75 V
  - Operating temperature: -40 C to 85 C (extended to 105 C)
- Power entry:
  - VCC_3V3 -> ferrite bead (120 ohm @ 100 MHz) -> VDD_nRF
- VDD decoupling (per Nordic reference circuit family):
  - 10 uF bulk on VDD_nRF
  - 2.2 uF on VDD_nRF
  - 100 nF on VDD_nRF (x1 or more)
- DC/DC network:
  - DCC pin -> L_DCDC 4.7 uH -> VDD_nRF
  - DECD: 10 nF to GND
  - DECA/DECRF: 100 nF to GND (DECRF must be tied to DECA)

---

## 6. Pin and Net Assignments

### 6.1 TLIN14313-Q1 (RGY 20-pin QFN)
Pin | Name | Net / Usage
--- | ---- | -----------
1 | VSUP | VSUP_PROT
2 | VCC | VCC_3V3
3 | nRST | TLIN_nRST (10 k pull-up to VCC_3V3)
4 | WDT/CLK | SPI_SCK
5 | nWDR/SDO | SPI_MISO
6 | WDI/SDI | SPI_MOSI
7 | PIN/nCS | SPI_CS (10 k pull-up to VCC_3V3)
8 | EN/nINT | TLIN_nINT (10 k pull-up to VCC_3V3)
9 | HSSC/FSO | NC (unused)
10 | PV | PV (to PV_SENSE via R/C)
11 | DIV_ON | TLIN_DIV_ON (GPIO from nRF, enable during PV sampling)
12 | TXD | UART_TX
13 | RXD | UART_RX
14 | GND | GND
15 | LIN | LIN_BUS
16 | WKRQ/INH | NC (unused)
17 | WAKE | NC (unused)
18 | HSS | NC (unused)
19 | LIMP | NC (unused)
20 | VBAT | VBUS_12V_RAW (pre-diode)

### 6.2 nRF54L10 (QFN40, QDAA)
Pin | Name | Net / Usage
--- | ---- | -----------
1 | P1.00/XL1 | XL1 (32.768 kHz crystal)
2 | P1.01/XL2 | XL2 (32.768 kHz crystal)
3 | P1.02/NFC1 | NC
4 | P1.03/NFC2 | NC
5 | P1.04/AIN0 | PV_SENSE
6 | P1.05/AIN1 | NC
7 | P1.06/AIN2 | NC
8 | P1.08/CLK16M | NC
9 | VDD | VDD_nRF
10 | P2.00 | NC
11 | P2.01/SPI.SCK | SPI_SCK (clock-capable pin)
12 | P2.02/SPI.SDO | SPI_MOSI (master-out)
13 | P2.03 | TLIN_DIV_ON
14 | P2.04/SPI.SDI | SPI_MISO (master-in)
15 | P2.05/SPI.CSN | SPI_CS
16 | P2.06/TRACECLK | NC
17 | P2.07/SWO | UART_RX (from TLIN RXD)
18 | P2.08 | UART_TX (to TLIN TXD)
19 | VDD | VDD_nRF
20 | P0.00 | TLIN_nINT
21 | P0.01 | TLIN_nRST
22 | SWDIO | SWDIO
23 | SWDCLK | SWDCLK
24 | P0.04/CLKOUT32K | NC
25 | nRESET | nRF_RESET (RC reset network)
26 | ANT | RF_ANT
27 | VSS_PA | GND
28 | DECRF | DECA (tie together)
29 | XC1 | XC1 (32 MHz crystal)
30 | XC2 | XC2 (32 MHz crystal)
31 | VDD | VDD_nRF
32 | P1.11/AIN4 | NC
33 | P1.12/AIN5 | NC
34 | P1.13/AIN6 | NC
35 | P1.14/AIN7 | NC
36 | DECA | DECA (100 nF to GND)
37 | VSS | GND
38 | DECD | DECD (10 nF to GND)
39 | DCC | DCC (to 4.7 uH -> VDD_nRF)
40 | VDD | VDD_nRF
EP | VSS_EP | GND (exposed pad)

Notes:
- SPIM SCK requires a clock-capable pin; P2.01 satisfies this requirement.
- DECRF must be tied to DECA (datasheet requirement).
- SWDIO has an on-chip pull-up; SWDCLK has an on-chip pull-down.

---

## 7. Clocking

- 32 MHz crystal (2016, CL=8 pF, +/-40 ppm): XC1 <-> XC2.
- 32.768 kHz crystal (2012, CL=9 pF, +/-20 ppm): XL1 <-> XL2.
- Default: use internal load capacitors; keep optional DNP footprints for external caps if needed.

---

## 8. RF and Antenna

### 8.1 nRF reference RF network (near ANT pin)
Populate per Nordic reference values:
- L2 2.7 nH
- L3 3.5 nH
- L4 3.5 nH
- C6 1.5 pF
- C9 2.0 pF
- C11 0.3 pF
- C13 3.9 pF

Layout notes from Nordic reference:
- C6 ground must only connect to VSS_PA and the exposed pad under the IC (top layer).
- C9 ground must be isolated from all ground layers except the bottom ground layer.
- Place the RF network as close as possible to the ANT pin.

### 8.2 Antenna (Abracon AANI-CH-0070)
- Dimensions: 1.0 x 0.5 x 0.4 mm, 50 ohm impedance.
- Edge mount only; do not place in the middle of the PCB.
- Copper cutout must extend through all layers (no copper in keepout on any layer).
- Recommended ground clearance (from datasheet figure): 4.6 mm x 3.5 mm keepout.
- Use via fence around the cutout and along the ground edge.
- Keep the feedline short; use 50 ohm CPWG.

### 8.3 Antenna matching network
- Place a 3-part matching footprint at the antenna feed.
- Abracon EVB baseline values (0402):
  - X1: DNP
  - X2: 5.1 pF (Murata GJM1555C1H5R1WB01)
  - X3: 2.2 nH (Murata LQW15AN2N2C10)
- Expect retuning in the final plastic enclosure (plastic often shifts resonance downward).

---

## 9. Firmware Behavior (LG Bus)

### Bus handling
- Always listen and decode LG frames to maintain a local state mirror.
- Transmit only after SIG is high >=500 ms.
- Echo-verify transmissions to detect collisions.
- Use back-off and retry on detected collisions.

### Identity and role
- Use a slave controller ID (e.g., 0x28 / 0x2A).
- Never spoof the master controller ID.

### Protocol specifics (as currently understood)
- 104 bps, 8N1, 13-byte frames.
- Checksum = (sum of bytes) XOR 0x55.

---

## 10. Matter/Thread Application Layer

### Commissioning
- BLE commissioning for initial setup.
- Thread credentials provided by commissioner.

### Thread role
- Sleepy End Device (SED) or Minimal Thread Device (MTD) recommended.
- Router role is optional and not required.

### Matter endpoint mapping (baseline)
1) Thermostat endpoint
   - Power/mode <-> LG mode and power
   - Setpoints <-> LG target temperature
2) Fan control endpoint (optional)
   - Fan mode/speed <-> LG fan level
3) Temperature sensor endpoint (optional)
   - Ambient temperature if available

---

## 11. Safety, Reliability, and Fault Handling

### Power safety
- No back-feeding on Red wire (use diode/ideal-diode).
- Treat bus as shared media; never dominate it.

### Electrical robustness
- TLIN LIN pin is fault tolerant for bus transients (see datasheet).
- Optional TVS/ESD recommended for cable transients.

### Fail-safe behavior
- If device power is removed or firmware crashes:
  - Existing PREMTA000 controller remains functional.
  - Bus operation continues unaffected.

---

## 12. Manufacturing and Test Considerations

### Programming access
- Provide SWD pads (SWDIO/SWDCLK/RESET/GND/Vref).
- Keep accessible without disassembling the wall controller.

### RF tuning
- Expect to retune antenna matching in the final enclosure.
- Provide 3-part matching footprint for tuning.

### Test points (recommended)
- VBUS_12V_RAW, VSUP_PROT, VCC_3V3, VDD_nRF, GND
- LIN_BUS
- nRF_RESET

---

## 13. CAD and KiCad Implementation Conventions

- Use hierarchical sheets; every hierarchical label in a child sheet must have a matching sheet pin in the parent (KiCad ERC rule).
- Use explicit net labels; avoid multiple labels on the same net.
- Place no_connect markers on intentionally unused IC pins to keep ERC clean.

---

## 14. Open Decisions / Future Work

1) OTA strategy: internal flash only vs external QSPI storage
2) Physical reset/commissioning access: tact switch, reed switch, or capacitive pad
3) Exact LG protocol field mapping to Matter clusters (requires finalized decoding)

---

## 15. Summary (One-line)

Build a thin, embedded Thread/Matter slave controller that taps the LG CN-REMO bus in parallel using TLIN14313-Q1 + nRF54L10, speaks the LG 104-bps single-wire protocol politely, and exposes HVAC control via Matter without ever disrupting the existing PREMTA000 master controller.
