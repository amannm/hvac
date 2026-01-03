
## A) Power + Protection Nets

### `GND`

**Connects:**

* J1-BLACK (CN-REMO GND)
* U1(TLIN) GND
* U2(nRF) VSS, VSS_PA, exposed pad (VSS_EP)
* All decoupling caps return pins (C_VSUP, C_VCC_BULK, C_VCC_HF, C_VDD_* , C_DECA, C_DECD, etc.)
* C_LIN, C_PV, C_ADC, C_RESET
* TVS/ESD returns: D_VSUP_TVS, D_LIN_ESD (if used)
* RF shunt capacitor grounds per Nordic guidance (place/partition grounds as required)

### `VBUS_12V_RAW`  (CN-REMO Red, **pre-diode**)

**Connects:**

* J1-RED
* D_VSUP_REV anode (reverse-blocking diode)
* (Optional) C_VBUS_BULK (+)
* (Optional) D_VSUP_TVS cathode (TVS to GND)
* U1(TLIN) VBAT (pre-diode feed for PV divider / measurement)

### `VSUP_PROT`  (post-diode 12 V feeding TLIN VSUP)

**Connects:**

* D_VSUP_REV cathode
* U1(TLIN) VSUP
* C_VSUP 100 nF (+) to GND

### `VCC_3V3`  (TLIN LDO output)

**Connects:**

* U1(TLIN) VCC
* C_VCC_BULK 10 µF (+) to GND
* C_VCC_HF 100 nF (+) to GND
* Pullups: R_nRST_PULLUP (to TLIN_nRST), R_nINT_PULLUP (to TLIN_nINT), R_nCS_PULLUP (to SPI_CS, recommended)
* FB1 input (ferrite bead into nRF rail)

### `VDD_nRF`  (filtered 3V3 domain for nRF)

**Connects:**

* FB1 output
* U2(nRF) all VDD pins
* C_VDD_BULK 10 µF (+) to GND
* C_VDD_2u2 (one or more) to GND
* C_VDD_100n (one or more) to GND
* (Any additional nRF decouplers per reference)
* DC/DC return network node(s) as below

### `DCC`  (nRF DC/DC switch node)

**Connects:**

* U2 DCC
* L_DCDC 4.7 µH (between `DCC` and `VDD_nRF`)

### `DECA`  (includes DECRF tied to DECA)

**Connects:**

* U2 DECA and U2 DECRF (same net)
* C_DECA 100 nF to GND

### `DECD`

**Connects:**

* U2 DECD
* C_DECD 10 nF to GND

---

## B) CN-REMO Signal (Yellow) / LIN Front-End

### `BUS_SIG_RAW`  (CN-REMO Yellow, before series R)

**Connects:**

* J1-YELLOW
* (Optional) D_LIN_ESD cathode (ESD/TVS to GND)
* R_LIN_SER (~1 kΩ) **input side**

### `LIN_BUS`  (TLIN LIN pin side of series resistor)

**Connects:**

* R_LIN_SER output side
* U1(TLIN) LIN
* C_LIN 220 pF to GND

---

## C) TLIN VBAT / PV Sense (optional but supported)

### `TLIN_DIV_ON`

**Connects:**

* U1(TLIN) DIV_ON
* U2 GPIO (DIV_ON control)

### `PV_SENSE`

**Connects:**

* U1(TLIN) PV → R_PV_SER 470 Ω → `PV_SENSE`
* C_ADC 10 nF from `PV_SENSE` to GND (optional ADC RC)

### `PV` (optional intermediate net if you want it explicit)

If you prefer naming the TLIN-side node:

* U1 PV pin and the TLIN-side of R_PV_SER and C_PV

### `PV` shunt

**Connects:**

* C_PV 20 pF from U1 PV (or `PV`) to GND

---

## D) TLIN ↔ nRF Digital Interfaces

### SPI control (TLIN in SPI mode)

* `SPI_CS`: U1 PIN/nCS ↔ U2 SPI_CSN  (optional R_SPI_SER in series near nRF; recommended pull-up to `VCC_3V3`)
* `SPI_SCK`: U1 WDT/CLK ↔ U2 SPI_SCK  (optional R_SPI_SER)
* `SPI_MOSI`: U1 WDI/SDI ↔ U2 SPI_MOSI (optional R_SPI_SER)
* `SPI_MISO`: U1 nWDR/SDO ↔ U2 SPI_MISO (optional R_SPI_SER)

### UART data (actual bus traffic)

* `UART_TX`: U1 TXD ↔ U2 UART_TX  (optional R_UART_SER)
* `UART_RX`: U1 RXD ↔ U2 UART_RX  (optional R_UART_SER)

### Interrupt / Reset between chips

* `TLIN_nINT`: U1 EN/nINT ↔ U2 GPIO (interrupt) + R_nINT_PULLUP 10 k to `VCC_3V3`
* `TLIN_nRST`: U1 nRST ↔ U2 GPIO (reset control) + R_nRST_PULLUP 10 k to `VCC_3V3`

---

## E) nRF Reset + Debug

### `nRF_RESET`

**Connects:**

* U2 nRESET
* R_RESET_SER 1 k in series (inline on the reset trace)
* C_RESET 2.2 nF from `nRF_RESET` to GND

### `SWDIO`

**Connects:**

* U2 SWDIO
* SWD test pad/header pin

### `SWDCLK`

**Connects:**

* U2 SWDCLK
* SWD test pad/header pin

### `VREF_SWD` (recommended)

**Connects:**

* `VDD_nRF` to SWD Vref pad (so the debugger senses I/O voltage)

---

## F) Clocks

### 32 MHz HFXO

* `XC1`: U2 XC1 ↔ one side of X_HFXO
* `XC2`: U2 XC2 ↔ other side of X_HFXO
* (Optional) `C_XC1`: XC1 to GND (DNP footprint)
* (Optional) `C_XC2`: XC2 to GND (DNP footprint)

### 32.768 kHz LFXO

* `XL1`: U2 XL1 ↔ one side of X_LFXO
* `XL2`: U2 XL2 ↔ other side of X_LFXO
* (Optional) `C_XL1`: XL1 to GND (DNP footprint)
* (Optional) `C_XL2`: XL2 to GND (DNP footprint)

---

## G) RF

Because the exact Nordic matching topology is reference-schematic-defined, it’s best to name **intermediate RF nodes explicitly** so your schematic/netlist is unambiguous:

### Primary RF nets

* `RF_ANT`: U2 ANT pin → input of the Nordic RF matching network
* `RF_50`: output of the RF network → 50 Ω CPWG feed to antenna/match

### Suggested intermediate nodes (recommended)

* `RF_N1`, `RF_N2`, `RF_N3` … as needed between L2/L3/L4 and C6/C9/C11/C13 according to the Nordic reference network.
* Antenna tuning network at feed: place `C_MATCH`, `L_MATCH`, and DNP position between `RF_50` and ANT1 feed (node can remain `RF_50` unless you want `ANT_FEED`).

### Antenna

* ANT1 (AANI-CH-0070): feed pin on `RF_50` (or `ANT_FEED`), ground per footprint/keepout rules

---

## H) Recommended Testpoints (nets to expose)

* TP_VBUS: `VBUS_12V_RAW`
* TP_VSUP: `VSUP_PROT`
* TP_3V3: `VCC_3V3`
* TP_VDD: `VDD_nRF`
* TP_GND: `GND`
* TP_LIN_RAW: `BUS_SIG_RAW`
* TP_LIN: `LIN_BUS`
* TP_RST: `nRF_RESET`
* SWD pads: `SWDIO`, `SWDCLK`, `VREF_SWD`, `GND`

---
