# SPEC — LG PREMTA000 Embedded Wireless Slave Controller

**Document purpose:** Define the complete target device (hardware + firmware behavior) for a *non-invasive*, in-enclosure wireless “slave” controller that joins the LG PREMTA000 wired wall controller ecosystem and exposes HVAC control over **Thread + Matter** (with **BLE commissioning**).

---

## 1. Purpose and Goals

### 1.1 Primary objective
Build a wireless embedded controller that:
- Fits inside the PREMTA000 wall controller enclosure.
- Connects **in parallel** to the existing 3‑wire **CN‑REMO** bus.
- Behaves like a **slave wired controller node** (not inline, not MITM).
- Exposes HVAC control via **Thread + Matter**, with **BLE commissioning**.

### 1.2 Must‑have properties
- **Non-disruptive:** must not interfere with existing LG master controller operation.
- **Fail‑safe:** if this device loses power or crashes, the existing PREMTA000 continues to function normally.
- **No back‑feeding:** must not feed current back onto the CN‑REMO **Red (12 V)** wire.
- **Bus‑polite:** only transmits when safe, detects collisions, and backs off.
- **Matter mapping:** implements a thermostat-style interface consistent with Matter clusters.

### 1.3 Explicit non-goals
- Inline interception/modification of the master controller (no man‑in‑the‑middle).
- Replacing the master controller or indoor unit.
- Acting as a Thread Border Router.

---

## 2. System Context

### 2.1 Target installation
- Indoor unit: **LG ARNU123NJA4**
- Wired wall controller: **LG PREMTA000**

### 2.2 CN‑REMO bus (3-wire)
- **Red:** +12 V (supply)
- **Yellow:** Signal (single‑wire)
- **Black:** GND

**Physical layer:** single-wire, dominant‑low / recessive‑high.  
**Protocol (current understanding):** UART-like **104 bps**, **8N1**, **13‑byte frames**, checksum = **(sum of bytes) XOR 0x55**.  
**Topology:** the LG system supports **two wired controllers** (Master + Slave) on one indoor unit.

---

## 3. High‑Level Architecture

```
CN‑REMO (12V, SIG, GND)
   → TLIN14313‑Q1 (12 V single‑wire PHY + 3.3 V LDO)
        → nRF54L10 (Thread/Matter + BLE + application)
             → RF matching + antenna tuning → 2.4 GHz chip antenna (AANI‑CH‑0070)
```

### 3.1 Architectural principles
- **Parallel node:** Yellow/Black connect in parallel; power from Red.
- **Slave identity:** uses a *slave controller* source ID (e.g., 0x28 / 0x2A).
- **Polite bus access:** transmit only when the line is idle (high) for **≥500 ms** and echo‑verify.

---

## 4. Mechanical and PCB Constraints

### 4.1 PCB stackup (target)
- 2‑layer thin PCB:
  - 0.115 mm copper / 0.508 mm FR‑4 / 0.115 mm copper

### 4.2 Placement constraints
- **CN‑REMO connector:** edge-mounted, horizontal, on the short edge, **opposite** the antenna edge.
- **Antenna:** edge-mounted; requires full‑layer copper cutout + keepout (all layers).
- Must fit inside PREMTA000 enclosure with **no modifications** to the existing controller.

---

## 5. Electrical Architecture

## 5.1 Recommended net names (project standard)
**Power**
- `VBUS_12V_RAW` — CN‑REMO Red (incoming 12 V)
- `VSUP_PROT` — post reverse-blocking element feeding TLIN VSUP
- `VCC_3V3` — TLIN LDO output (3.3 V)
- `VDD_nRF` — filtered 3.3 V domain for nRF54L10
- `GND` — common ground (CN‑REMO Black)

**Bus**
- `BUS_SIG_RAW` — CN‑REMO Yellow before series resistor
- `LIN_BUS` — TLIN LIN pin side of series resistor

**TLIN ⇄ nRF digital**
- `SPI_CS`, `SPI_SCK`, `SPI_MOSI`, `SPI_MISO`
- `UART_TX`, `UART_RX`
- `TLIN_nINT`, `TLIN_nRST`
- `TLIN_DIV_ON`
- `PV_SENSE`

**RF**
- `RF_ANT` — nRF ANT pin / immediate RF network node
- `RF_50` — 50 Ω feedline between RF network and antenna tuning network

**Debug**
- `SWDIO`, `SWDCLK`, `nRF_RESET`

---

## 5.2 Power entry and protection

### 5.2.1 Reverse blocking (required)
Purpose: prevent back-feeding the CN‑REMO Red wire.

- **Primary option:** `D_VSUP_REV` in series with `VBUS_12V_RAW → VSUP_PROT`
  - Schottky diode or ideal‑diode solution.
- **Layout variant:** provide an optional **0 Ω bypass/jumper footprint** (DNP by default) for experiments, but production assemblies must enforce no-backfeed behavior.

### 5.2.2 Optional protection (recommended when cable exposure/transients are plausible)
- `D_VSUP_TVS`: `VBUS_12V_RAW → GND` (TVS sized for environment)
- `D_LIN_ESD`: `BUS_SIG_RAW → GND` (ESD/TVS clamp for signal wire)

### 5.2.3 Bulk capacitance
- Optional entry bulk: `C_VBUS_BULK` 10–47 µF from `VBUS_12V_RAW → GND` (near connector).
- TLIN decoupling and VCC bulk are **required** (see §5.3.2).

---

## 5.3 TLIN14313‑Q1 (12 V single‑wire PHY + LDO)

### 5.3.1 Intended configuration
- **Responder node**, SPI‑controlled.
- Provides single‑wire bus interface and a **3.3 V LDO** rail for the nRF54L10.

### 5.3.2 Electrical constraints (summary)
- `VSUP`, `VBAT`: 5.5 V to 28 V (recommended operating range)
- `VLIN`: 0 V to 28 V
- Logic pins (3.3 V variant): 0 V to 3.465 V
- `VCC` output: 3.3 V ±2.5%, up to 125 mA

### 5.3.3 Required decoupling (place as close as possible to TLIN pins)
- `C_VSUP` 100 nF: `VSUP_PROT → GND`
- `C_VCC_BULK` 10 µF: `VCC_3V3 → GND` (ESR 0.001–2 Ω)
- `C_VCC_HF` 100 nF: `VCC_3V3 → GND`

### 5.3.4 Mode straps and default pin behavior (important for clean bring‑up)
- **SPI mode strap:** ensure `PIN/nCS` is **high at power‑up**  
  - `R_nCS_PULLUP` 10 kΩ from `SPI_CS (TLIN nCS) → VCC_3V3` recommended.
- **nRST is open‑drain:** add external pull‑up  
  - `R_nRST_PULLUP` 10 kΩ from `TLIN_nRST → VCC_3V3`.
- **nINT pull‑up:** `R_nINT_PULLUP` 10 kΩ from `TLIN_nINT → VCC_3V3`.
- Keep unused TLIN pins explicitly **NC** (use no_connect markers) unless datasheet requires tie‑offs.

### 5.3.5 VBAT / PV sense (optional, recommended for telemetry)
TLIN has an internal VBAT divider and PV output for measuring the 12 V rail.

- `VBAT` connects to **pre‑diode** `VBUS_12V_RAW`
- Divider enable: `DIV_ON` controlled by `TLIN_DIV_ON` (nRF GPIO)
  - Default low; only enable during sampling to minimize bus loading.
- Recommended PV conditioning:
  - `R_PV_SER` 470 Ω in series TLIN PV → `PV_SENSE`
  - `C_PV` 20 pF: TLIN PV → GND (near TLIN)
  - Optional ADC RC: `C_ADC` 10 nF: `PV_SENSE → GND` (near nRF)

If PV sensing is not used: DNP the PV parts and hold `TLIN_DIV_ON` low.

---

## 5.4 CN‑REMO signal path (single‑wire bus)

- Series resistor: `R_LIN_SER` ≈ 1 kΩ from `BUS_SIG_RAW → LIN_BUS`
- EMI capacitor: `C_LIN` 220 pF from `LIN_BUS → GND` (place near TLIN LIN pin)
- **No external pull‑up** by default (TLIN provides internal pull‑up)

---

## 5.5 TLIN ⇄ nRF54L10 digital interfaces

### 5.5.1 SPI (control path, required)
- TLIN `nCS` → `SPI_CS`
- TLIN `CLK` → `SPI_SCK`
- TLIN `SDI` → `SPI_MOSI`
- TLIN `SDO` → `SPI_MISO`

Optional SI resistors near nRF:
- `R_SPI_SER` 22–47 Ω (x4 on SCK/MOSI/MISO/CS)

### 5.5.2 UART (bus data interface)
- TLIN `TXD` → `UART_TX` (to nRF UART TX pin)
- TLIN `RXD` → `UART_RX` (to nRF UART RX pin)

Optional series resistors near nRF:
- `R_UART_SER` 22–47 Ω (x2 on TX/RX)

### 5.5.3 Interrupt and reset
- TLIN `EN/nINT` → `TLIN_nINT` (10 kΩ pull‑up to `VCC_3V3`)
- TLIN `nRST` → `TLIN_nRST` (10 kΩ pull‑up to `VCC_3V3`)

---

## 5.6 nRF54L10 power, reset, clocks

### 5.6.1 Selected SoC
- **Nordic nRF54L10**, 5×5 mm QFN40 (fixed for this design).

### 5.6.2 Power entry
- `VCC_3V3` → **FB1 ferrite bead** (≈120 Ω @ 100 MHz, ≥200 mA) → `VDD_nRF`
- Decoupling on `VDD_nRF` (place per Nordic reference layout family):
  - 10 µF bulk
  - 2.2 µF decouplers as required
  - 100 nF HF decouplers (xN)
  - 10 nF where indicated by reference configuration (xN)

### 5.6.3 DC/DC network (per Nordic reference)
- `DCC` → `L_DCDC` 4.7 µH → `VDD_nRF`
- `DECD`: 10 nF to GND
- `DECA/DECRF`: 100 nF to GND (**DECRF must be tied to DECA**)

### 5.6.4 Reset network (recommended)
- `R_RESET_SER` 1 kΩ series into `nRF_RESET`
- `C_RESET` 2.2 nF from `nRF_RESET → GND`

### 5.6.5 Clocks
- 32 MHz crystal (2016, CL=8 pF, ±40 ppm): `XC1 ↔ XC2`
- 32.768 kHz crystal (2012, CL=9 pF, ±20 ppm): `XL1 ↔ XL2`
- Default: use nRF internal load capacitors; provide optional DNP pads for external caps if bring‑up indicates need.

---

## 5.7 RF and Antenna

### 5.7.1 RF network at nRF ANT pin (populate per Nordic reference)
Place as close as possible to ANT; keep grounds as specified by reference layout.

Reference values:
- L2 2.7 nH
- L3 3.5 nH
- L4 3.5 nH
- C6 1.5 pF
- C9 2.0 pF
- C11 0.3 pF
- C13 3.9 pF

RF network output should be routed as `RF_50` (50 Ω CPWG) to the antenna tuning network.

### 5.7.2 Antenna: Abracon AANI‑CH‑0070
- Edge mount only.
- Enforce **all‑layer copper cutout + keepout** per Abracon datasheet (typical keepout ~4.6 mm × 3.5 mm).
- Use via fence around cutout and along ground edge.
- Keep the feedline short.

### 5.7.3 Antenna tuning / matching footprint (at antenna feed)
Provide a 3‑part matching footprint; baseline starting values (0402, from Abracon EVB guidance):
- X1: DNP
- X2: 5.1 pF (Murata **GJM1555C1H5R1WB01**)
- X3: 2.2 nH (Murata **LQW15AN2N2C10**)

Expect enclosure-dependent retuning (plastic typically shifts resonance downward).

---

## 6. Pin and Net Assignments

> Note: Pin numbers below reflect the working mapping used for this design; always validate against the specific package variant and datasheet revisions.

### 6.1 TLIN14313‑Q1 (RGY 20‑pin QFN) — recommended mapping
| Pin | Name | Net / Usage |
|---:|---|---|
| 1 | VSUP | `VSUP_PROT` |
| 2 | VCC | `VCC_3V3` |
| 3 | nRST | `TLIN_nRST` (10 kΩ pull‑up to `VCC_3V3`) |
| 4 | WDT/CLK | `SPI_SCK` |
| 5 | nWDR/SDO | `SPI_MISO` |
| 6 | WDI/SDI | `SPI_MOSI` |
| 7 | PIN/nCS | `SPI_CS` (10 kΩ pull‑up to `VCC_3V3`) |
| 8 | EN/nINT | `TLIN_nINT` (10 kΩ pull‑up to `VCC_3V3`) |
| 9 | HSSC/FSO | NC |
| 10 | PV | PV → `R_PV_SER` → `PV_SENSE` |
| 11 | DIV_ON | `TLIN_DIV_ON` |
| 12 | TXD | `UART_TX` |
| 13 | RXD | `UART_RX` |
| 14 | GND | `GND` |
| 15 | LIN | `LIN_BUS` |
| 16 | WKRQ/INH | NC |
| 17 | WAKE | NC |
| 18 | HSS | NC |
| 19 | LIMP | NC |
| 20 | VBAT | `VBUS_12V_RAW` (pre‑diode) |

### 6.2 nRF54L10 (QFN40, QDAA) — working mapping
| Pin | Name | Net / Usage |
|---:|---|---|
| 1 | P1.00/XL1 | `XL1` |
| 2 | P1.01/XL2 | `XL2` |
| 5 | P1.04/AIN0 | `PV_SENSE` |
| 9 | VDD | `VDD_nRF` |
| 11 | P2.01/SPI.SCK | `SPI_SCK` |
| 12 | P2.02/SPI.SDO | `SPI_MOSI` |
| 13 | P2.03 | `TLIN_DIV_ON` |
| 14 | P2.04/SPI.SDI | `SPI_MISO` |
| 15 | P2.05/SPI.CSN | `SPI_CS` |
| 17 | P2.07/SWO | `UART_RX` |
| 18 | P2.08 | `UART_TX` |
| 20 | P0.00 | `TLIN_nINT` |
| 21 | P0.01 | `TLIN_nRST` |
| 22 | SWDIO | `SWDIO` |
| 23 | SWDCLK | `SWDCLK` |
| 25 | nRESET | `nRF_RESET` |
| 26 | ANT | `RF_ANT` |
| 27 | VSS_PA | `GND` |
| 28 | DECRF | `DECA` (tie together) |
| 29 | XC1 | `XC1` |
| 30 | XC2 | `XC2` |
| 36 | DECA | `DECA` (100 nF to GND) |
| 38 | DECD | `DECD` (10 nF to GND) |
| 39 | DCC | `DCC` (to 4.7 µH → `VDD_nRF`) |
| EP | VSS_EP | `GND` |

---

## 7. Firmware Behavior (LG Bus)

### 7.1 Bus handling rules
- Always listen and decode LG frames to maintain a local state mirror.
- Transmit only after `BUS_SIG_RAW` is high (idle) for **≥500 ms**.
- Echo‑verify transmissions to detect collisions.
- Use randomized back‑off and retry on collision.

### 7.2 Identity and role
- Operate as a **slave** controller ID (do not spoof the master controller).
- Never take actions that prevent the master from controlling the indoor unit.

### 7.3 Protocol specifics (current understanding)
- 104 bps, 8N1, 13‑byte frames
- Checksum: (sum of bytes) XOR 0x55

---

## 8. Matter / Thread Application Layer

### 8.1 Commissioning
- BLE commissioning for initial setup.
- Thread credentials are provided by the commissioner.

### 8.2 Thread role
- Prefer **Sleepy End Device (SED)** or **Minimal Thread Device (MTD)**.
- Router role is optional and not required.

### 8.3 Endpoint mapping (baseline)
1) **Thermostat** endpoint
   - Power/mode ↔ LG mode and power
   - Setpoints ↔ LG target temperature
2) **Fan control** endpoint (optional)
   - Fan mode/speed ↔ LG fan level
3) **Temperature sensor** endpoint (optional)
   - Ambient temperature if available from bus state

---

## 9. Safety, Reliability, and Fail‑Safe

### 9.1 Power safety
- Prevent back‑feeding on Red wire via reverse blocking element.
- TLIN VCC powers only local electronics (no external loads).

### 9.2 Bus safety
- Treat CN‑REMO signal as shared media; never dominate the line.
- Detect collision and back off to preserve master controller behavior.

### 9.3 Fail‑safe behavior
If the device is removed/unpowered:
- Existing PREMTA000 controller remains fully functional.
- Bus operation continues unaffected.

---

## 10. Manufacturing, Bring‑Up, and Test

### 10.1 Programming access
- Provide SWD pads for `SWDIO`, `SWDCLK`, `nRF_RESET`, `GND`, and Vref.
- Keep accessible without disassembling the wall controller if feasible.

### 10.2 RF tuning
- Provide the 3‑part antenna matching footprint.
- Plan for tuning in the final plastic enclosure.

### 10.3 Recommended test points
- `VBUS_12V_RAW`, `VSUP_PROT`, `VCC_3V3`, `VDD_nRF`, `GND`
- `BUS_SIG_RAW` and/or `LIN_BUS`
- `nRF_RESET`
- (Optional) `RF_50` test coupon/pad (production DNP)

---

## 11. KiCad / CAD Conventions

- Prefer hierarchical sheets.
- Every hierarchical label in a child sheet must have a matching sheet pin in the parent (KiCad ERC rule).
- Use explicit net labels; avoid multiple labels on the same net.
- Place `no_connect` markers on intentionally unused IC pins.

---

## 12. Electrical Implementation Checklist (condensed)

Use this as a pre-fab sanity pass:

1) **No backfeed:** `VBUS_12V_RAW` must not be driven from `VSUP_PROT`/`VCC_3V3`.
2) **TLIN decoupling present:** 100 nF at VSUP; 10 µF + 100 nF at VCC.
3) **SPI mode guaranteed:** TLIN nCS pulled high at power‑up.
4) **LIN front-end:** ~1 kΩ series + 220 pF to GND near TLIN LIN pin; no external pull‑up unless proven necessary.
5) **nRF power integrity:** ferrite bead into `VDD_nRF`, with bulk + HF decoupling placed per reference.
6) **Reset robustness:** TLIN nRST pull‑up; nRF reset RC network present.
7) **RF keepout enforced:** antenna edge placement; keepout/cutout and via fence are correct; feedline is short 50 Ω CPWG.
8) **Connector vs antenna:** on opposite edges; keep digital switching away from RF edge.
9) **Debug pads:** SWD and key rails accessible.

---

## 13. BOM Summary (value-level)

> Reference designators are schematic-defined; values below are the design baseline.

### 13.1 ICs
- U1: **TLIN14313‑Q1** (TI)
- U2: **nRF54L10** (Nordic)

### 13.2 Passives / protection (baseline)
- Reverse block: `D_VSUP_REV` (Schottky or ideal diode)
- Optional: `D_VSUP_TVS`, `D_LIN_ESD`
- `R_LIN_SER` 1 kΩ
- `C_LIN` 220 pF
- `R_nRST_PULLUP` 10 kΩ
- `R_nINT_PULLUP` 10 kΩ
- `R_nCS_PULLUP` 10 kΩ (recommended)
- `R_PV_SER` 470 Ω; `C_PV` 20 pF; optional `C_ADC` 10 nF
- Optional series damping: `R_SPI_SER` 22–47 Ω (x4), `R_UART_SER` 22–47 Ω (x2)

### 13.3 Power filtering / decoupling
- `FB1` ferrite bead: ~120 Ω @100 MHz, ≥200 mA, low DCR
- TLIN: `C_VSUP` 100 nF; `C_VCC_BULK` 10 µF; `C_VCC_HF` 100 nF
- nRF: 10 µF bulk + 2.2 µF + 100 nF (+ 10 nF where shown) per reference design
- DC/DC: `L_DCDC` 4.7 µH; `DECD` 10 nF; `DECA/DECRF` 100 nF

### 13.4 Clocks
- 32 MHz crystal (2016, CL=8 pF, ±40 ppm)
- 32.768 kHz crystal (2012, CL=9 pF, ±20 ppm)

### 13.5 Antenna and matching
- Abracon **AANI‑CH‑0070** antenna
- Matching baseline: 5.1 pF (Murata GJM1555C1H5R1WB01), 2.2 nH (Murata LQW15AN2N2C10), plus one DNP pad

---

## 14. Open Decisions / Future Work
1) OTA strategy: internal flash only vs external QSPI storage
2) Physical reset/commissioning access: tact switch vs reed switch vs capacitive pad
3) Final LG protocol field mapping to Matter clusters (requires finalized decoding)

---

## 15. Summary (one line)
A thin, embedded Thread/Matter **slave** controller that taps the LG CN‑REMO bus in parallel using **TLIN14313‑Q1 + nRF54L10**, speaks the LG 104‑bps single‑wire protocol politely, and never disrupts the existing PREMTA000 master controller.
