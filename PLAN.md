Below is a **minimal “3-wire tap” slave controller** that can sit **in parallel** with the LG indoor unit + wired wall controller on **CN-REMO** and bridge the bus onto **Thread / Matter 1.5 Thermostat cluster** using **nRF54L10 + TLIN14313-Q1**.

---

## 1) What we must interface to (from `protocol.md`)

* Physical layer is **single-wire** serial on a **3-wire cable**: **Red=12 V**, **Yellow=Signal**, **Black=GND**, **104 bps, 8N1**. ([GitHub][1])
* Bus is collision-prone; practical approach is to only transmit after **~500 ms recessive/high** observed. ([GitHub][1])
* It is truly **one wire** (your node “hears itself” when it transmits). ([GitHub][1])

**Key gotcha:** TLIN14313 has **TXD dominant timeout (DTO)** on the order of **20–80 ms (typ ~45 ms)**, and at **104 bps** a `0x00` byte can hold TXD low ~86 ms (start + 8 bits), tripping DTO unless disabled. ([Texas Instruments][2])
TI explicitly notes DTO can be **turned off in SPI mode** via register **0x1D[5] = 1**. ([Texas Instruments][2])
➡️ Therefore: **you must use TLIN14313 in SPI mode and disable DTO** during init.

---

## 2) Architecture (minimal)

**Power:** use the TLIN14313’s integrated **3.3 V LDO (VCC output)** to power the nRF54L10 (no separate regulator). TLIN14313 provides **3.3 V regulated output** from 12 V supply. ([Texas Instruments][2])

**Bus I/O:** LG “Signal” (yellow) → **TLIN LIN pin**; nRF talks to TLIN via:

* **TXD/RXD** (bit-banged UART @ 104 bps recommended)
* **SPI** (to disable DTO and set watchdog/mode as needed)

**Thread/Matter:** nRF54L10 supports **Thread / Matter / 802.15.4** and needs **1.7–3.5 V** supply and **single 32 MHz crystal operation** (LF 32.768 kHz optional). ([Digi-Key][3])
Radio output is **single-ended with on-chip balun**. ([Digi-Key][3])

---

## 3) ASCII schematic (minimal, with “stuff later if you need it” footprints)

```
                      LG CN-REMO / 3-wire harness
                 (parallel tap; do NOT break existing cable)
            +12V (RED) o----+-----------------------------+
                            |                             |
                            |        D1 Schottky          |
                            +----->|----+-----------------+-----> VSUP (U1)
                            |   (rev prot) |
                            |              |        C1 100nF
                            |              +------||----- GND
                            |
                            +--R1 470Ω--+-------> VBAT (U1)    (sense input)
                            |           |
                            |          C2 100nF
                            |           |
            GND (BLK) o-----+-----------+------------------------------ GND

            SIG (YEL) o-----------------------------------------------> LIN (U1)
                                           |
                                          (optional ESD diode to GND footprint)

     U1: TLIN14313-Q1  (SPI MODE; DTO disabled in FW)
     -------------------------------------------------
     VSUP  <--- from D1
     VBAT  <--- from R1/C2 node (or tie to VSUP if you don't care about sensing)
     GND   <--- GND
     VCC   ----+-----> 3V3 rail
               |
              C3 10uF
               |
              GND
               |
              C4 100nF
               |
              GND

     LIN   <--- to SIG (YEL)
     TXD   <--- nRF GPIO (LG_TX)
     RXD   ---> nRF GPIO (LG_RX)

     SPI (for config: disable DTO, watchdog, mode control)
     WDT/CLK  <--- nRF SPIM_SCK
     WDI/SDI  <--- nRF SPIM_MOSI
     nWDR/SDO ---> nRF SPIM_MISO
     PIN/nCS  <--- nRF SPIM_CS   (with external pull-up so it boots into SPI)
     EN/nINT  ---> nRF GPIO (TLIN_nINT)  (SPI mode: interrupt output) :contentReference[oaicite:8]{index=8}

     nRST  <--- (optional) nRF GPIO or RC to 3V3
     (All other pins: leave NC unless you use HSS/INH/etc.)

     Pull-ups / straps:
       R2 10k:  PIN/nCS (U1) ---/\/\/\--- 3V3    (ensures SPI mode at power-up) :contentReference[oaicite:9]{index=9}
       R3 100k: WAKE (U1)  ---/\/\/\--- GND      (keep local wake quiet)
       R4 100k: DIV_ON(U1) ---/\/\/\--- GND      (divider off)

     -------------------------------------------------

     U2: nRF54L10 (Thread/Matter)
     ----------------------------
     VDD / VDDH  <--- 3V3 rail (from U1 VCC)   (decouple near pins)
     GND         <--- GND

     HF crystal (required): 32 MHz
       XC1 o---||---+---[X1 32MHz]---+---||---o XC2
                C5  |               |   C6
                    GND             GND

     LF crystal (optional): 32.768 kHz (if you want best sleep timing)
       XL1 o---||---+---[X2 32.768k]---+---||---o XL2
                C7  |                 |   C8
                    GND               GND

     RF:
       ANT o---[PI MATCH FOOTPRINT: C-L-C (DNP/tune)]---(U.FL or chip antenna)

     Programming:
       JTAG/SWD header: 3V3, GND, SWDIO, SWDCLK, nRESET

     Optional (but typical for Matter commissioning):
       SW1: GPIO -> GND (commission / factory reset)
       D2 + Rled: GPIO -> LED -> R -> 3V3 (status)
```

---

## 4) Firmware-critical configuration notes (because of 104 bps)

1. **Disable TLIN TXD dominant timeout (DTO)** after boot, otherwise 104 bps traffic can trip it. DTO timing and the fact it can be disabled in SPI mode are documented by TI. ([Texas Instruments][2])
2. Keep your device “quiet” on the LG bus:

   * Observe bus via RXD; transmit only after **≥500 ms recessive/high** to avoid collisions. ([GitHub][1])
3. nRF54L10 UARTE likely won’t support **104 bps** as a standard divisor; plan on **bit-banging** (timer + GPIO) for TX and sampling RX, or an oversampling state machine.

---

## 5) BOM (minimal)

### Core ICs

* **U2:** Nordic **nRF54L10** (QFN48 or WLCSP variant per your assembly capability) — Thread/Matter capable ([Nordic Semiconductor][4])
* **U1:** TI **TLIN14313-Q1** LIN SBC w/ **3.3 V LDO** output ([Texas Instruments][2])

### Power / protection

* **D1:** Schottky diode, ≥1 A, ≥40 V (reverse blocking on +12 V into VSUP)
* **C1:** 100 nF, 50 V (VSUP decouple)
* **C3:** 10 µF, ≥6.3 V (VCC (3V3) bulk per TI recommendation range) ([Texas Instruments][2])
* **C4:** 100 nF, ≥6.3 V (VCC high-freq decouple)
* **R1:** 470 Ω (VBAT sense filter series, per TI typical notes) ([Texas Instruments][2])
* **C2:** 100 nF (VBAT sense filter cap)

*(Optional but recommended footprints)*

* TVS diode on +12 V input (SMBJ ~18V-ish)
* ESD diode on SIG/LIN line

### TLIN straps / misc

* **R2:** 10 kΩ pull-up on **PIN/nCS** → 3V3 (ensures SPI mode at power-up) ([Mouser Electronics][5])
* **R3:** 100 kΩ WAKE→GND
* **R4:** 100 kΩ DIV_ON→GND

### nRF clocking (minimum viable RF)

* **X1:** 32 MHz crystal (per nRF54L series “single 32 MHz crystal operation”) ([Digi-Key][3])
* **C5/C6:** crystal load caps per crystal CL (often 8–12 pF range; pick to match X1)

*(Optional)*

* **X2:** 32.768 kHz crystal (optional per Nordic) ([Digi-Key][3])
* **C7/C8:** load caps for X2

### RF output

* **RF pi network footprints:** C-L-C (DNP initially, then tune)
* **Antenna:** u.FL + external antenna *or* a 2.4 GHz chip antenna (choose based on enclosure/PCB)

### Connectors / UX

* **J1:** 3-pin connector to CN-REMO harness (12V / SIG / GND)
* **J2:** SWD header (3V3, GND, SWDIO, SWDCLK, RESET)
* *(Optional)* **SW1** tact button + **LED** + resistor for commissioning/status

---

If you want, I can also provide a **pin map suggestion** (exact nRF54L10 GPIO assignments for SPI + TXD/RXD + SWD) and a **minimal “bring-up” register sequence** for TLIN14313 (SPI init → disable DTO → watchdog handling) consistent with TI’s behavior described in the datasheet.

[1]: https://raw.githubusercontent.com/JanM321/esphome-lg-controller/refs/heads/main/protocol.md "raw.githubusercontent.com"
[2]: https://www.ti.com/lit/ds/symlink/tlin1431-q1.pdf "TLIN1431-Q1 Automotive LIN SBC with Integrated High-Side Switch and Watchdog datasheet (Rev. A)"
[3]: https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/7136/NRF54L15-CAAA-R.pdf "nRF54L15 | nRF54L10 | nRF54L05 Preliminary Datasheet"
[4]: https://www.nordicsemi.com/Products/nRF54L10?utm_source=chatgpt.com "nRF54L10 wireless SoC"
[5]: https://www.mouser.com/datasheet/2/405/1/sllu326a-3077594.pdf?srsltid=AfmBOoq8LC2u8BTO2zDiTR3vz4iD3zvKkazKm-f3Wc21HWjE1EER3BB9 "TLIN1431EVM User's Guide (Rev. A)"
