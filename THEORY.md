Here’s what I think is the *best* (lowest-risk + highest-compatibility) way to build your “tiny wireless slave controller” **inside the PREMTA000 master controller**.

## 1) What the target system looks like (from your docs)

* The LG wired wall controller bus is a **3-wire CN-REMO link**: **Red = 12 V**, **Yellow = Signal**, **Black = GND**.  
* Signaling is **(very slow) 104 bps, 8N1 serial** on the single signal wire. 
* Frames are **13 bytes** with a checksum (sum of bytes XOR 0x55). 
* The protocol explicitly supports a “slave controller” source ID (examples **0x28 / 0x2A**) and a “master controller” source ID (examples **0xA8 / 0xAA**). 
* LG supports **two wired remote controllers (max) on one indoor unit**, with one set to Master and the other(s) to Slave. 
* Collisions can happen; a proven approach is “only transmit if RX has been high ≥500 ms”, and verify your own echo (single-wire bus). 
* LG also warns in group-control contexts: **do not connect the 12 V line to “slave” indoor units** (only signal+GND) or you can lose comms. This is a strong hint the system doesn’t like multiple power sources tied together. 
* Your BOM intent: thin PCB (0.508 mm FR-4), CN-REMO conformant connector, **TLIN14313-Q1**, and **nRF54L10** + Abracon AANI-CH-0070. 

## 2) The optimal architecture (high level)

### Key design choice: **act as a true second “wired controller” node**, not an inline “man-in-the-middle”

Since LG already supports “two wired remotes” (master+slave) , the safest architecture is:

**Your module sits in parallel on Yellow/Black (and uses Red for power), identifies itself as a “slave controller,” and injects only the minimum frames needed to request changes.**

That means:

* The existing PREMTA000 continues working normally as Master.
* Your module can be powered from the same 12 V feed but must **never back-feed** anything onto Red.
* If your module crashes/unpowers, the HVAC still works (because the Master is untouched).

## 3) Hardware design I’d build (based on your parts)

### Block diagram

**CN-REMO (Red/Yellow/Black) → TLIN14313-Q1 (12 V single-wire physical layer + 3.3 V LDO) → nRF54L10 (logic + wireless) → 2.4 GHz chip antenna**

### 3.1 CN-REMO connection / mechanical

* Use the **CN-REMO conformant female connector** on the PCB edge, opposite the antenna, as you noted. 
* Inside the PREMTA000 enclosure, I’d wire it so you’re effectively “tapping” the same three conductors (Red/Yellow/Black). Wire colors/roles are consistent in LG docs.  

### 3.2 Power: use TLIN14313-Q1 as your front-end + 3.3 V source

Why this is optimal here:

* It’s built for 12 V single-wire buses and has strong protection (e.g., LIN pin fault tolerance). 
* The TLIN14313 variant provides a **3.3 V LDO (up to ~125 mA)** from the 12 V supply, perfect for the nRF54L10 + radio bursts. 

What I’d implement:

* **Red(12 V) → TLIN VBAT/VSUP**
* Add a **series diode (or ideal diode) on the Red input** so you *cannot* ever source current back onto the cable. This aligns with LG’s “don’t tie power into slave wiring” warning patterns. 
* Decouple VBAT/VSUP and VCC per TLIN’s typical wiring (you already have the canonical cap set shown in TI’s simplified schematics: 100 nF / 10 nF / 10 µF around the supply rails). 

### 3.3 Bus physical layer: TLIN14313-Q1 on the Yellow wire

Even though the “LG wall controller protocol” is UART-like (not full LIN frames), the **physical layer problem is the same**: single wire, 12 V domain, dominant-low behavior.

* **Yellow(SIG) → TLIN LIN pin**, **Black(GND) → TLIN GND**
* Add the EMC parts shown in TI’s simplified diagram: **220 pF from LIN to GND** and **~1 k series element** on the bus connection (as depicted). 
* TLIN has an internal LIN pull-up (tens of kΩ typical), which is usually fine since you’re just adding one more node to an already short cable. 

### 3.4 TLIN control mode: SPI is the right call (matches your COMPONENTS.md)

You specified **SPI control**. 
That’s what I’d do too, because it lets you:

* Configure/disable watchdog behavior cleanly (rather than relying on strapping only)
* Get diagnostics/interrupts (nINT) if you want them

Also: TLIN “self-determines” whether it’s SPI or pin-controlled at power-up. 
So you’d strap it so it reliably boots into SPI mode, then the nRF54 configures it early.

Watchdog detail: If you *do* strap the WDT pin, TI gives typical timing windows (e.g., floating gives ~seconds-scale windows). 
In practice, I’d still configure watchdog via SPI so you’re not fighting defaults.

### 3.5 nRF54L10 core circuitry (use Nordic’s reference values)

Your choices match Nordic’s recommended approach: crystals, DC/DC inductor, decoupling, ferrite bead, reset RC, etc. 

From the nRF54 reference circuit/BOM:

* **DCDC inductor:** 4.7 µH 
* **Ferrite bead:** 120 Ω @ 100 MHz (200 mA class) 
* **Reset network:** 1 k + 2.2 nF  
* **Crystals:** 32 MHz (CL=8 pF, 2016) and 32.768 kHz (CL=9 pF, 2012) 
* The nRF54 family supports **BLE + 802.15.4**, and has a **single-ended antenna output (on-chip balun)**.  

So: copy the reference power + reset + crystal layout as closely as your form factor allows.

### 3.6 RF: use Nordic’s “known good” matching + keep the antenna tuning flexible

You selected the Abracon AANI-CH-0070 and its example matching (5.1 pF + 2.2 nH).  

Important practical point (especially since you’re inside a plastic wall-controller enclosure):

* Abracon explicitly warns the resonant frequency can shift in the final device and plastic nearby can shift it downward; they recommend measuring/tuning in the final assembly and using a matching network.  

So the “optimal” RF plan is:

1. Implement Nordic’s reference **RF filter/match from the nRF54 ANT pin to a 50 Ω feed** (their values are provided and they note these can change).  
2. Then implement the Abracon antenna footprint at the PCB edge with the required keepout/copper cutout + via fence. 
3. Place the Abracon “X1/X2/X3” matching pads right at the antenna feed, and expect to adjust values for the enclosure. 

## 4) Firmware behavior that will keep you “non-disruptive” on the bus

### 4.1 Treat the HVAC bus as shared media (polite talker)

* Always listen and decode the 13-byte frames, maintain a state mirror.
* Only transmit when the line has been recessive/high for **≥500 ms**. 
* Always verify your own echo and retry/backoff if corrupted. 

### 4.2 Identify as a slave controller and only “inject” on command

* Use a slave source ID pattern (e.g., **0x28/0x2A**). 
* When wireless clients request a change, generate the relevant “settings” frame(s) and send them (optionally twice, since LG often repeats frames, but it’s not required). 
* Don’t spam: send a change frame, then return to listening. Let the Master keep doing its periodic status traffic.

### 4.3 Wireless interface recommendation

Given you’re embedding inside a wall controller enclosure, I’d default to:

* **BLE GATT service** (simple commissioning via phone + local gateway support)
* Optional: if your ecosystem target is Matter/Thread, nRF54 supports 802.15.4 (Thread/Zigbee-class) , but it increases software complexity.

## 5) Why this design is “optimal” for your goal

* **Compatibility-first:** it leverages LG’s own supported topology (two wired remotes, Master+Slave). 
* **Low brick-risk:** no inline dependency; if your module dies, the master PREMTA000 still controls the unit.
* **Electrical safety:** TLIN14313-Q1 is purpose-built for 12 V single-wire buses and gives you a clean 3.3 V rail. 
* **RF realism:** you have a credible antenna + documented matching, with explicit warning that enclosure plastics require final tuning.  

If you want, I can turn this into a concrete “first-pass schematic checklist” (pin-to-pin nets + the missing resistor/cap list for TLIN14313-Q1 and nRF54L10) using the exact reference values you already pulled into your docs.

---

Got it — if you want **Thread/Matter**, the “optimal” design is still *parallel, non-intrusive slave-on-the-LG-bus*, but with the wireless stack choices and product-variant choices tuned for Matter.

## 1) What changes when you pick Thread/Matter

### Your device becomes a **Matter-over-Thread End Device**

* It joins a Thread mesh (as an end device; optionally a router).
* It exposes a **Matter endpoint** (or multiple endpoints) that represent “an HVAC controller.”
* It still talks to the LG indoor unit over **CN-REMO (12V / SIG / GND)**, decoding and injecting the same 13-byte frames at 104 bps. 

### Implication: you’ll need a **Thread Border Router** somewhere

Matter-over-Thread devices don’t speak Wi-Fi directly; they need a border router on the network. Your embedded device does *not* need to be that border router.

## 2) Silicon choice: use nRF54L10 (selected)

From the nRF54L datasheet:

* **nRF54L10**: **1012 KB NVM**, **192 KB RAM** (selected) 
* **nRF54L15**: **1524 KB NVM**, **256 KB RAM** (not selected; fallback if L10 headroom proves tight) 
* Radio supports **802.15.4-2020** and explicitly notes “Enables Matter, Thread.” 
* Security features include TrustZone isolation + crypto engine with side-channel leakage protection. 

Because we are using **L10**, plan early for:

* aggressive logging limits
* careful feature selection in the Matter stack
* likely OTA constraints (see §6)

## 3) Wireless stack architecture that tends to be best in practice

### Commissioning: **BLE for onboarding**, Thread for normal operation

Even though your product goal is Thread/Matter, it’s still common to use BLE only for commissioning because it makes first-time setup simpler. Your SoC is multiprotocol (BLE + 802.15.4). 

So the clean flow is:

1. Device boots advertising a **Matter commissioning BLE** service
2. A commissioner (phone/app/home hub) provisions Thread credentials
3. Device switches to steady-state **Matter-over-Thread**

### Thread role: Router vs Sleepy End Device

You have continuous 12 V power available on CN-REMO. 
So the optimal choice is usually:

* **Minimal Thread Device (MTD)** or **Sleepy End Device (SED)** if you want minimal RF chatter
* **Router-capable** only if you explicitly want it to strengthen the mesh

Most of the time: **SED/MTD is best** (less complexity, fewer “why is my wall controller a mesh router?” surprises).

## 4) Matter data model: how to expose an “LG wired controller” cleanly

Your firmware already needs to maintain a state mirror of the LG bus. The best Matter mapping is:

### Endpoint design (recommended)

* **Endpoint 1: Thermostat-like control**

  * Modes ↔ LG mode (cool/heat/dry/fan/auto where supported)
  * OccupiedCoolingSetpoint / OccupiedHeatingSetpoint ↔ LG target temp
  * SystemMode ↔ LG power + mode
* **Endpoint 2 (optional): Fan Control**

  * FanMode / FanSpeed ↔ LG fan level options (where supported)
* **Endpoint 3 (optional): Temperature sensor**

  * If you can trust/read ambient temp from the bus (or add your own sensor)

Your `protocol.md` already shows you’re decoding lots of capability bits and settings payload structure — that’s exactly what you’ll want for exposing correct feature support and readback to Matter clients. 

### Command policy (important to avoid bus disruption)

* Matter write → translate into *minimal LG “settings change” frames* (send once or a short burst)
* Then go quiet and confirm by observing the bus update (don’t assume your write “took”)

This matches the shared-bus reality (collisions exist; you only talk when safe).

## 5) Hardware stays basically the same — but add 3 “Matter-friendly” features

You already have the right core blocks:

* TLIN14313-Q1 front-end + 3.3 V rail 
* nRF54L radio that supports 802.15.4 and Matter/Thread 
* A tiny 2.4 GHz antenna that explicitly targets Thread/Matter use cases 

To make it “optimal” for Matter lifecycle:

### (A) A way to do **factory reset + commissioning mode** without opening the enclosure

* a hidden tactile switch accessible through a pinhole, **or**
* capacitive pad, **or**
* a reed switch/magnet gesture

### (B) A robust **unique identity** strategy

nRF54L exposes a unique device identifier. 
Use that to seed:

* your device serial number / discriminator derivation (development-time)
* stable Matter node identity logic

### (C) Plan for **OTA update storage**

This is the big one. Matter OTA is a “product reality” even for DIY-ish deployments.

Options:

* If internal NVM + your image strategy supports it, great.
* Otherwise, consider adding external QSPI storage. The datasheet even hints at serial QSPI being available as a SoftPeripheral (“sQSPI”). 

(If you stay on nRF54L10, this is where you may feel constrained first.)

## 6) Firmware structure that scales well for Thread/Matter

I’d split into 4 layers:

1. **LG Bus HAL**

   * RX decode (104 bps, 13-byte frames)
   * TX arbiter (idle-detect/backoff/echo-verify)

2. **LG State Model**

   * canonical internal representation (power, mode, setpoints, fan, flags)
   * capability detection (from your parsed capability bits)

3. **Matter Bridge Layer**

   * Matter attributes reflect LG State Model
   * Matter writes enqueue “intent” (change setpoint, change mode, etc.)
   * A single command serializer generates LG frames

4. **Thread/Matter Platform**

   * Thread attach + keepalive
   * BLE commissioning mode
   * OTA handler

## 7) One more “gotcha” to keep front-of-mind

LG explicitly warns that in some topologies, tying power to “slave” paths can break comms. 
Even though you’re embedding inside the master controller enclosure (so you *do* want to use the 12 V line for power), the spirit of that warning is:

**Never let your module back-feed the bus power rail.**
(So keep your input diode/ideal-diode and don’t ever present yourself as a second “source” on Red.)

---

If you want, I can propose an exact “first Matter device definition” (endpoint list + clusters + which LG fields map to which attributes) based on the message types you’ve decoded so far, and a concrete strategy for OTA given **nRF54L10** memory limits.

---

Here’s how I’d optimize the **hardware** for a tiny “slave” node that lives inside the **PREMTA000 master controller** enclosure, taps the 3-wire bus, and bridges to **Thread/Matter** (so you’ll be doing **802.15.4 @ 2.4 GHz**).

---

## 1) Physical + electrical constraints to design around

* The wall controller bus is a **3-wire cable: Red=12V, Yellow=Signal, Black=GND**  and the reverse-engineered doc describes it as a **slow 104 bps 8N1 serial link** on that single signal wire .
* Your mechanical target is explicitly a **very thin PCB stack**: 0.115 mm Cu / 0.508 mm FR-4 / 0.115 mm Cu  and an **edge/horizontal CN-REMO connector opposite the antenna** .
* Thread means you care about **2.4 GHz efficiency** more than peak BLE range; the nRF54 family supports **802.15.4** (receiver sensitivity is specified for it) .

---

## 2) “Best” hardware architecture (block-level)

### A) Power entry (12 V rail → protected VSUP)

Even though you’re inside a plastic wall controller, the *cable* can be long and noisy (LG warns about long runs and uses shielded cable)  , so treat it like an automotive-ish supply.

**Recommended power front-end:**

1. **Reverse blocking diode** into TLIN14313 VSUP (TI explicitly expects VSUP fed through an external reverse battery-blocking diode) 

   * Use a **Schottky** if you want low drop; size it for your peak current.
2. **TVS diode on the 12 V input** (after the connector, before/around the diode depending on your protection philosophy).
3. **Input filtering + bulk**:

   * Place the TI-required **100 nF right at VSUP**  
   * Add **1–4.7 µF** close (helps radio bursts), and a **10–47 µF** bulk nearby if you have space.
4. Optional but nice: **polyfuse/series resistor** if you want to current-limit faults inside the master controller enclosure.

### B) “Bus interface + 3.3 V rail” (TLIN14313-Q1 as your analog front door)

Your COMPONENTS.md choice here is solid: **TLIN14313-Q1** as a responder node and 3.3 V source . It’s also explicitly meant for 12 V systems and has strong bus fault protection (LIN bus fault protection ±58 V) , with **VLIN absolute max −58 to +58 V** .

**Key wiring choices:**

* **VSUP operating range**: designed for **5.5–28 V**  (so the LG 12 V rail is in-family).
* Use its integrated **3.3 V LDO (125 mA)**  to power the nRF54 + RF network.

  * Watch thermals: LDO dissipation is (12V–3.3V)*I. Keep average current low and give the TLIN exposed pad a real copper heatsink area (TI calls out soldering the thermal pad for best performance) .

**LIN/SIG pin conditioning (do this even at 104 bps):**

* Follow TI’s responder-node conditioning idea (example shows a **series resistor** and **small cap** at the bus) :

  * Add **~1 kΩ series** between your transceiver LIN pin and the Yellow “SIG” net (limits contention energy + helps ESD).
  * Add a **small shunt cap (~100–470 pF)** to GND *on your side* if you need edge taming (don’t go big; you don’t want to load the bus).
* Note the TLIN already presents an internal pull-up in normal/standby (typical **45 kΩ** to VSUP with a diode path)  , so you generally don’t need an external pull-up.

**Mode control (SPI control as you planned):**

* Strap **PIN/nCS** for SPI mode (internal pull-up defaults to SPI; TI explicitly notes floating/pulled-up = SPI control) .
* Provide a clean **reset strategy**: TLIN has **nRST** and EN/nINT etc.  — route TLIN nRST to nRF reset *or* let TLIN supervise the nRF (nice for brownouts).

### C) Thread radio SoC (nRF54L10) power + clocks + programming

Nordic explicitly recommends using their **reference circuitry + layouts + values** for RF performance . Practically, that means:

* Use the **DCDC + inductor + decoupling** exactly per the reference design you already pulled (your earlier nRF54 ref-circuit excerpt with a 4.7 µH inductor + local caps is the right pattern).
* Keep the **32 MHz crystal** and **32.768 kHz crystal** footprints tight and symmetric (your COMPONENTS.md specifies both) , and Nordic’s LFXO load capacitance window is **6–9 pF** .

**Debug/programming (don’t skip this):**

* Put Tag-Connect pads or tiny test pads for **SWDIO/SWDCLK/RESET/GND/Vref**. Even in a sealed enclosure, you’ll want “manufacturing mode” access without cracking the whole controller every time.

---

## 3) Antenna + RF layout: what will make or break Thread reliability

You picked the **Abracon AANI-CH-0070** loop chip antenna . For Thread, antenna implementation matters a lot because mesh links can be marginal indoors.

### A) Placement rules you should follow literally

Abracon’s guidance is very direct:

* The antenna **must be on the PCB edge** .
* The **copper cutout must extend through all PCB layers**, and they recommend a **robust via structure** around the cutout/ground edge .
* Nearby plastic affects tuning (often shifts resonance downward)  — and you’re *inside plastic*, so assume you’ll need to re-tune the match.

Also note their stated **recommended ground clearance** (keepout) for this antenna is **4.6 x 3.5 mm**, and it’s intended for **PCB edge mounting** .

### B) Matching network strategy (two-stage reality)

You effectively have two matching problems:

1. **Nordic RF output matching** (the SoC-side L/C network Nordic specifies—follow their ref design) 
2. **Antenna-side tuning match** (Abracon’s suggested parts are a starting point: **5.1 pF + 2.2 nH** in their eval board) 

Because the enclosure detunes things, build in:

* A **pi or “shunt/series” footprint option** near the antenna so you can swap values during bring-up.
* Space for **DNP parts** (stuff only what you need).

### C) Controlled impedance trace on a 0.508 mm board

Use a **CPWG (coplanar waveguide with ground)** from the nRF RF pin/matching to the antenna feed, keep it **short**, and keep the ground continuous. Abracon specifically calls out CPWG and keeping it short as possible in their implementation guidance .

Your ultra-thin stackup actually helps you get 50 Ω on a small geometry, but it also makes the antenna region more sensitive to *any* nearby copper. Be disciplined with the keepout.

---

## 4) PCB layout priorities (in order)

1. **Antenna edge + keepout + via fence** (per Abracon) 
2. **nRF54 RF path**: matching parts tight, shortest possible, ground references clean 
3. **DCDC loop area** (inductor/caps close, keep away from antenna)
4. **TLIN VSUP decoupling**: the **100 nF at VSUP** must be right at the pin 
5. **Thermal pad + vias** under TLIN VQFN (and follow TI’s via/land-pattern guidance—e.g., tent/plug vias under paste) 

---

## 5) Minimal “hardware BOM skeleton” to flesh out COMPONENTS.md

Based on your chosen parts list , this is what I’d lock in early:

### Power/protection

* Reverse blocking diode (VSUP feed) 
* TVS on 12 V input
* VSUP decoupling: **100 nF at pin**  + 1–4.7 µF nearby + optional bulk

### Bus/SIG conditioning

* Series resistor ~**1 kΩ** between SIG(Yellow) and TLIN LIN pin (TI example style) 
* Optional small cap (100–470 pF) to GND on TLIN side (tune by scope)

### TLIN14313 essentials

* SPI strap: PIN/nCS floating/pulled-up for SPI 
* Exposed pad solder + copper for heat/mechanical 

### nRF54 essentials

* Follow Nordic ref circuitry/layout guidance 
* 32 MHz crystal + caps; 32.768 kHz crystal + caps (respect LFXO load range) 
* SWD pads

### Antenna

* AANI-CH-0070 at PCB edge, keepout, via fence 
* Start match at **5.1 pF + 2.2 nH** (Abracon EVB baseline) 
* Expect to re-tune due to plastic enclosure effects 

---

## If you want the “most robust” variant

If you can tolerate a slightly bigger PCB, the single biggest hardware upgrade for Thread reliability is: **use a physically larger 2.4 GHz antenna** (still internal), or at least ensure you can preserve Abracon’s clearance and keep metal away. The tiny loop can work, but Thread benefits disproportionately from antenna efficiency and stable tuning.

---

If you share a photo or internal dimensions of the PREMTA000 enclosure (especially where plastic ribs/screws sit relative to the connector area), I can propose a concrete **placement + keepout map** (what goes on which end of the PCB, where ground pours must stop, where to route SWD pads so you can still reach them).

---

Below is the *hardware-centric* way I’d interconnect **TLIN14313-Q1 (SBC/LIN PHY + LDO + watchdog)** and **nRF54L10 (Thread/Matter SoC)**, with emphasis on **exact pins, shared rails, and the “between-them” passives**.

---

## 1) The “shared backbone”: power + ground

### 12 V in → TLIN → 3.3 V out (feeds nRF54)

Your LG bus is explicitly **RED=12V, BLACK=GND, YELLOW=SIG**. 
So the clean topology is:

* **LG 12V (RED)** → **TLIN VSUP**
* **LG GND (BLACK)** → **TLIN GND** and **nRF VSS/GND**
* **TLIN VCC (3.3 V LDO output)** → **nRF VDD rail**

TLIN’s LDO output pin **VCC** is intended to power external devices and is rated **up to 125 mA** (depending on system implementation). 

### The key “shared” capacitors here

TLIN explicitly calls out required/expected decoupling:

* **C(VSUP) = 100 nF** 
* **C(VCC) = 10 µF** with ESR constraint **0.001 Ω to 2 Ω** 

On the nRF54 side, Nordic’s reference “VDD bulk” is also **10 µF + 100 nF** on the VDD rail. 

**Practical “shared component” insight:**
You *can* have one 10 µF that satisfies TLIN’s VCC requirement and also serves as nRF’s bulk—**but only if it’s placed right at TLIN VCC**. In practice I’d do:

* **10 µF at TLIN VCC pin** (LDO stability + bulk)
* **another local 10 µF + 100 nF at nRF VDD pins** (radio burst currents / local HF loop)

If you want extra isolation between “noisy LIN/12V” and RF domain, put any bead/impedance **after** the TLIN’s required VCC capacitor (so the LDO still “sees” its stability cap directly).

---

## 2) The primary chip-to-chip interfaces (what to connect, and why)

### A) UART-style LIN data: nRF ↔ TLIN TXD/RXD

Even if you’re doing SPI control, the *actual bus data stream* still uses TXD/RXD:

* TLIN takes the protocol stream on **TXD** and drives the **LIN** pin. 
* TLIN presents the received bus state back on **RXD**. 

Pins (TLIN package):

* **Pin 12 = TXD** 
* **Pin 13 = RXD** 

TI’s layout/app guidance explicitly notes **RXD is push-pull** and can connect directly to the processor (no pullup). 
They also mention an *optional* **series resistor** and/or **small cap to GND** on TXD for robustness/noise filtering (often not needed). 

**Recommended wiring**

* nRF **UARTE_TX** → TLIN **TXD** (optionally 22–100 Ω series at the nRF pin if you want edge damping)
* nRF **UARTE_RX** ← TLIN **RXD** (direct)

---

### B) SPI control/config: nRF ↔ TLIN (4 wires)

TLIN’s SPI pins in SPI-control mode are:

* **Pin 5 = WDT/CLK** (SPI clock input) 
* **Pin 6 = WDI/SDI** (SPI MOSI into TLIN) 
* **Pin 4 = nWDR/SDO** (SPI MISO out of TLIN) 
* **Pin 7 = PIN/nCS** (SPI chip select) 

SPI timing: TLIN samples on rising edge, changes on falling edge (**Mode 0: CPOL=0, CPHA=0**).  

**“Shared component” note (important): internal pullups**
In SPI mode, TLIN enables weak pullups (~240 kΩ typical) on these lines (CLK, SDI, nCS).  
That means you usually **don’t need external pullups**, and it helps keep TLIN in a sane state while the nRF is booting.

**Recommended wiring**

* nRF **SPIM_SCK** → TLIN **CLK (Pin5)**
* nRF **SPIM_MOSI** → TLIN **SDI (Pin6)**
* nRF **SPIM_MISO** ← TLIN **SDO (Pin4)**
* nRF **GPIO (CS)** → TLIN **nCS (Pin7)**

Optional: 22–47 Ω series resistors near the nRF on SCK/MOSI can help if you get ringing in a tiny enclosure with awkward return paths.

---

### C) Interrupt/wake signalling: TLIN nINT → nRF GPIO

* **Pin 8 = EN/nINT** becomes **nINT output** in SPI control mode. 
  TI also explicitly states in the SPI-control layout example: “Pin 8 … becomes an output interrupt pin that is provided to the processor.” 

**Recommended wiring**

* TLIN **nINT** → nRF **GPIO with sense/interrupt**
  nRF GPIOs support wake/interrupt sensing broadly. 

---

### D) Reset/watchdog interaction: TLIN nRST ↔ nRF NRESET (do this carefully)

TLIN:

* **Pin 2 = nRST** is **reset input/output (active low)**. 
  Also: in SPI configuration, TLIN can be programmed so that this pin becomes the watchdog reset trigger (but then the pure reset function is lost). 

nRF54 reference hardware shows **a series resistor on RESET** (1 kΩ) and a small capacitor to GND on the chip side (shown as 3.9 pF in that reference schematic).  (schematic context)

**Recommended wiring pattern (robust + debug-friendly)**

* TLIN **nRST** ties to the **chip-side reset node** (the node that goes directly to nRF RESET pin)
* Put **~1 kΩ series** between that node and any external/reset/debug pad/header node (Nordic-style)
* Add a **small C to GND** on the chip-side node if you need EMI hardening (value is layout-dependent; Nordic uses a very small cap in their example)

This arrangement lets TLIN pull the nRF reset low without fighting external tools, and the series resistor protects against contention/ESD on exposed pads.

---

## 3) Other TLIN ↔ nRF “shared” functions worth wiring in (because they’re cheap and useful)

### A) WKRQ as a clean “wake output” into the nRF

TLIN can make **Pin 16** be either **WKRQ (digital wake output)** or **INH (high-voltage inhibit)** based on a strap resistor:

* **100 kΩ pulldown → WKRQ enabled** 
* Floating / 1 MΩ pulldown → INH 

When WKRQ is selected it’s **active high digital output** (referenced to VINT/VCC selection rules). 
So you can use it as a very clean “SBC says wake up” line into a low-power nRF GPIO.

**Recommended wiring**

* TLIN **WKRQ (Pin16)** → nRF **GPIO sense/wake**
* Add the **100 kΩ to GND** at TLIN Pin16 to select WKRQ. 

*(If you instead accidentally end up in INH mode, that pin can be high-voltage—so the 100 kΩ strap matters.)*

---

### B) TLIN battery monitor PV → nRF ADC (nice for diagnostics)

TLIN provides:

* **PV (Pin10)** = divided VBAT value, intended to go straight into MCU ADC. 
* **DIV_ON (Pin11)** enables the divider. 

TI even shows the recommended connection networks:

* Either **470 Ω + 10 nF** RC into the ADC, or **just a small capacitor (20 pF)** depending on your needs. 

**Recommended wiring**

* nRF **GPIO** → TLIN **DIV_ON (Pin11)** (so you only enable the divider when measuring)
* TLIN **PV (Pin10)** → nRF **ADC input**, with either:

  * **470 Ω series + 10 nF to GND** at the ADC pin, *or*
  * **20 pF to GND** at the ADC pin 

This is another “shared component” network (it literally straddles TLIN output + nRF ADC).

---

## 4) Logic-level compatibility (why TLIN14313 + nRF54 is a good pairing)

* TLIN’s SPI-related inputs have VIH ≈ **2.19 V**, VIL ≈ **0.8 V**. 
* nRF54 GPIO input-high is **0.7×VDD** (so at 3.3 V, ~2.31 V). 
* TLIN RXD output is push-pull and (per TI) meant to connect directly. 

So: **run everything at 3.3 V**, and you don’t need level shifting.

One cautionary detail: TLIN has an internal rail **VINT** that “can be 3.3 V or 5 V and may not be the same as VCC” in general. 
With **TLIN14313 (3.3 V LDO variant)** you’re naturally aligned to nRF’s 3.3 V world, but it’s still worth keeping in mind when you choose modes/straps (WKRQ, SPI IO level selection on other TLIN variants, etc.). 

---

## 5) A concrete “netlist-style” hookup summary (TLIN ↔ nRF)

**Must-have**

* TLIN **VCC** → nRF **VDD** (shared 3.3 V rail) 

  * C_VCC **10 µF** at TLIN 
  * plus local nRF VDD caps (10 µF + 100 nF) 
* TLIN **TXD** ← nRF **UART TX** 
* TLIN **RXD** → nRF **UART RX** 
* TLIN **CLK/SDI/SDO/nCS** ↔ nRF **SPIM** (Mode 0) 
* TLIN **nINT** → nRF **GPIO interrupt** 

**Strongly recommended**

* TLIN **nRST** ↔ nRF **RESET** with a Nordic-style series R + small C arrangement  
* TLIN **WKRQ** (strap 100 kΩ to GND) → nRF **GPIO wake** 

**Nice to have**

* TLIN **PV** → nRF **ADC**, TLIN **DIV_ON** ← nRF **GPIO**, with RC/Cap per TI 

---

If you want, I can take your **COMPONENTS.md** “Resistors: ? / Capacitors: ? / Diodes: ?” sections and fill them with a *tight, minimal BOM* specifically for the **TLIN↔nRF coupling networks** (power, reset, SPI/UART conditioning, WKRQ strap, PV filter), using exactly the values TI/Nordic show in their reference guidance.

---

### TLIN14313 ↔ nRF54: the “clean” hardware partition

Think of TLIN14313 as **the rugged front-end + power + supervisor**, and the nRF54 as **the radio + application MCU**. The “optimal” wiring is basically:

1. **12 V (RED) + GND (BLACK) → TLIN VSUP/GND**

* TI explicitly expects **VSUP connected to the battery through an external reverse battery-blocking diode**. 
* TI also recommends a **100 nF decoupling capacitor close to VSUP**. 

2. **TLIN VCC (3.3 V) → nRF54 VDD (shared 3.3 V rail)**

* TLIN14313 is the **fixed 3.3 V LDO variant**. 
* nRF54L10 runs from **VDD = 1.7 V to 3.6 V**, so 3.3 V from TLIN is directly compatible. 
* TI calls out **C(VCC)=10 µF** with **ESR between 0.001 Ω and 2 Ω**. 
* Nordic’s reference circuit shows a local **10 µF bulk** plus multiple small decouplers on the nRF supply network. 

**Shared components here:** the 3.3 V rail bulk/decoupling is “shared” in the sense that TLIN *must* have its output cap, and nRF *must* have its local caps—don’t try to “use only one set.”

---

### The two most important shared “glue” nets

#### A) Reset: TLIN nRST → nRF NRESET (shared RC network)

* TLIN nRST is **bi-directional, open-drain**, with an internal pull-up; TI **recommends an external 10 kΩ pull-up to the processor IO rail**. 
* Nordic’s reference reset network uses **R = 1 kΩ** and **C = 2.2 nF** on NRESET. 

**Practical “merge” that works well:**

* Make a net called `RESET_N`.
* TLIN `nRST` ties to `RESET_N`.
* Put **10 kΩ pull-up** from `RESET_N` to **3V3** (meets TI rec). 
* Put **1 kΩ series** between `RESET_N` and **nRF `NRESET` pin**, and **2.2 nF to GND** on the nRF side (matches Nordic ref). 

That gives you:

* TLIN can hold the MCU in reset on UV/faults.
* nRF gets Nordic’s recommended edge-shaping/noise immunity.
* The pull-up guarantees a defined level (handy because nRF GPIOs can be high-Z during reset). 

#### B) Interrupt: TLIN nINT → nRF GPIO (needs a pull-up)

In SPI control mode, TLIN’s EN/nINT pin becomes an interrupt output; TI describes it as **“pulled low” when attention is required**. 
That strongly implies you should treat it as **active-low, low-side assert**, and add a **pull-up (e.g., 10 kΩ to 3V3)** on the net.

---

### Digital links (no level shifting needed at 3.3 V)

#### SPI (TLIN config/status)

TLIN pins become SPI in SPI mode (CLK/SDI/SDO/nCS). 
TI also documents internal biasing on these pins (pull-ups on CLK/SDI/nCS) which helps keep them in sane states if the MCU is briefly high-Z at boot. 

**Recommended hardware “extras”:**

* Optional **22–47 Ω series resistors** on SCK/MOSI/MISO/CS close to the nRF if you see ringing/EMI on a tiny dense board. (Not required by the datasheet; just a common layout knob.)

#### UART-like link (actual bus data): TLIN TXD/RXD ↔ nRF UARTE

TLIN TXD/RXD are the logic-side view of the LIN single-wire bus. 
Again, optional **22–47 Ω series** on TXD/RXD is a nice “cheap insurance” for edge control.

Logic thresholds are compatible:

* TLIN SPI inputs have VIH ≈ **2.19 V** (so a 3.3 V nRF output is fine). 
* nRF GPIO VIH is **0.7×VDD** (≈2.31 V at 3.3 V), so TLIN 3.3 V outputs are fine. 

---

### Bus-side “shared” analog bits (optional but very useful)

#### LIN pin conditioning

For a **responder node**, TI says no external pull-up is required (internal pull-up + diode exists). 
And TI’s guidance calls out a **220 pF capacitor on LIN for responder nodes** (EMI / edge shaping). 

#### VBAT / bus voltage measurement (PV + DIV_ON) to nRF ADC

If you want to measure the 12 V rail (handy for brownout logging, power diagnostics, etc.):

* TI’s PV linearity spec references **RLOAD = 470 Ω** and **CLOAD = 10 nF**, or **20 pF if only capacitive load**. 
* Their example circuit shows PV with **20 pF** and a **470 Ω** element in the chain. 

A practical ADC filter is:

* PV → **470 Ω** → nRF AIN
* At nRF AIN: **10 nF to GND**
* At PV pin: **20 pF to GND** (tight to TLIN)

Those are “shared” components in the sense they exist **only** because TLIN’s PV is feeding the nRF ADC.

---

## What I would paste into `COMPONENTS.md` (hardware-focused fill)

```md
  - LIN SBC
    - Chip: Texas Instruments TLIN14313-Q1
      - SPI control
      - Responder node
      - VQFN package
    - Resistors:
      - R_VSUP_REV (series diode, see Diodes) – optional 0Ω placeholder for layout variants
      - R_nRST_PULLUP: 10 kΩ (RESET_N pull-up to 3V3)
      - R_nINT_PULLUP: 10 kΩ (nINT pull-up to 3V3)
      - R_PV_SER: 470 Ω (PV -> nRF ADC series / load)
      - (Optional) R_SPI_SER: 22–47 Ω (x4: SCK/MOSI/MISO/CS, near nRF)
      - (Optional) R_UART_SER: 22–47 Ω (x2: TXD/RXD, near nRF)
    - Capacitors:
      - C_VSUP: 100 nF (close to VSUP pin)
      - C_VCC_BULK: 10 µF (close to VCC pin, ESR 0.001–2 Ω)
      - C_VCC_HF: 100 nF (close to VCC pin)
      - C_LIN: 220 pF (LIN to GND, responder-node EMI cap, close to TLIN)
      - C_PV: 20 pF (PV to GND, close to TLIN)
      - C_ADC: 10 nF (nRF AIN to GND, close to nRF)
    - Diodes:
      - D_VSUP_REV: Reverse-battery blocking diode in series with VSUP (Schottky or ideal-diode solution)
      - (Optional) D_VSUP_TVS: TVS from VSUP-to-GND sized for the cable/transient environment
      - (Optional) D_LIN_ESD: ESD/TVS clamp for LIN-to-GND if the signal wire is exposed/long

  - Wireless SoC
    - Chip: Nordic Semiconductor nRF54L10
      - QFN package
    - Regulator Interface (per Nordic reference circuit family):
      - Capacitors:
        - 10 µF bulk on VDD rail (close to VDD entry)
        - 2.2 µF decouplers as required by reference configuration
        - 100 nF high-frequency decouplers
        - 10 nF where shown in reference configuration
      - Inductors:
        - 4.7 µH (DC/DC inductor per reference configuration)
      - Ferrite Bead: 120 Ohm @ 100MHz, 200mA, 500 mOhm Max
    - Reset Interface:
      - Resistor: 1 kΩ (series into NRESET per reference configuration)
      - Capacitor: 2.2 nF (NRESET to GND per reference configuration)
```

If you want, I can also propose **a concrete netlist-style pin mapping** (exact TLIN pin → exact nRF pin suggestions for SPIM/UARTE/GPIO/AIN), but the above is the “meat” of the shared hardware and the missing passives.

---

Below is how I’d wire **CN-REMO → TLIN14313 (LIN SBC)** and then the **nRF54 clock + RF/antenna** circuits, with concrete component values that match your documents.

---

## 1) CN-REMO connector → TLIN14313 (the “front end”)

### CN-REMO pin meaning (what each conductor is)

LG’s docs consistently show the 3-wire bus as:

* **RED = 12 V**
* **YELLOW = SIG**
* **BLACK = GND**  

*(Order on the plastic connector housing may differ—verify with continuity before committing copper.)*

### Recommended placement/partitioning

TI explicitly recommends starting PCB design with **protection/filtering at the connector** so ESD/EFT doesn’t propagate further into the board. 
Given your layout goal (CN-REMO on one end, antenna on the other) , keep a clear “dirty side” near CN-REMO and a “clean RF side” near the antenna.

---

### Power (CN-REMO 12V) → TLIN VBAT/VSUP (and 3V3 rail)

TLIN wants:

* **VBAT** connected **before** the reverse diode (so it can monitor the raw bus voltage) 
* **VSUP** connected **through** an external reverse blocking diode 
* **100 nF** close to VSUP for transient performance  and also reiterated in supply/layout guidance 

**Implement it like this (nets):**

* J1.RED (12V) → `VBAT_RAW`
* `VBAT_RAW` → TLIN **VBAT** pin 
* `VBAT_RAW` → **D1** (reverse-block diode) → `VSUP_PROT` → TLIN **VSUP** pin 
* `VSUP_PROT` → **C_VSUP 100 nF** to GND at TLIN pin 
* Add bulk near VSUP (your call; TI says “consider other bulk decoupling”) 
* TLIN **VCC** is your 3.3 V rail (TLIN14313 variant is 3.3 V) 

**Connector-side protection I’d add (strongly recommended):**

* **TVS diode** from `VBAT_RAW` to GND right at CN-REMO (fits TI’s “protect at connector” guidance) 
* If space allows: small **series impedance** (fuse/PP polyfuse or a few ohms resistor) before the diode/VSUP node.

---

### Signal (CN-REMO SIG) → TLIN LIN pin (conditioning)

TLIN as a **responder node** has internal pull-up/diode termination; TI says **no external pull-up is required** for responder nodes. 

TI’s own responder-node sketch shows:

* **1 kΩ series**
* **220 pF to GND** 

**Implement it like this (nets):**

* J1.YELLOW (SIG) → `BUS_SIG`
* `BUS_SIG` → (optional ESD clamp to GND at connector)
* `BUS_SIG` → **R_LIN_SER = 1 kΩ** → `LIN_LOCAL` 
* `LIN_LOCAL` → TLIN **LIN** pin
* `LIN_LOCAL` → **C_LIN = 220 pF** → GND (place this close to TLIN LIN pin) 

That R/C does two things: it reduces how much your added node disturbs the existing bus, and it hardens against fast transients without “slowing” a 104-bps line in any meaningful way.

---

### Ground (CN-REMO GND)

* J1.BLACK (GND) → solid ground plane.
* Stitch ground heavily around the connector/protection components (again: keep noise local). 

---

## 2) nRF54 clock circuits (32 MHz + 32.768 kHz)

Your COMPONENTS.md calls for:

* **32 MHz XTAL (2016) with CL=8 pF**
* **32.768 kHz XTAL (2012) with CL=9 pF** 

### Best-practice choice: use nRF54 internal load capacitors

Nordic’s nRF54 supports **internal capacitors** for both oscillators (HFXO and LFXO), or you can disable them and use external caps.  
Nordic’s own reference circuitry (QFN48 config 1) lists the crystals but does **not** list external load caps, which is consistent with using internal caps. 

**Hardware implementation:**

* Place **X2 (32 MHz)** directly between **XC1 and XC2**. 
* Place **X1 (32.768 kHz)** directly between **XL1 and XL2**. 
* Keep both crystal loops *tiny* and symmetric; keep them away from the LIN/12 V “dirty side”.

**Why this is ideal here:** it saves two caps per crystal (area), and the internal tuning gives you flexibility if the enclosure/PCB stray capacitance isn’t what you expected. (You’re already pushing a very small board.)

### If you want external load caps footprints anyway (recommended insurance)

The datasheet explicitly allows external caps after disabling internal caps.  
So: add **DNP footprints for C1/C2** at XC1/XC2 and XL1/XL2, and only populate if bring-up shows issues.

Also note: LFXO load capacitance spec is **6–9 pF** in the nRF54 electrical spec excerpt. 

---

## 3) nRF54 RF output → 50 Ω line → Abracon antenna + tuning

### A) The nRF54 “front matching” (copy Nordic’s reference values)

Nordic explicitly recommends using their **reference layouts and component values** for good RF performance. 

In the QFN48 reference circuitry snippet you have, Nordic provides a concrete RF network around the ANT pin (these are the values shown in that reference table):

* **L2 = 2.7 nH**
* **L3 = 3.5 nH**
* **L4 = 3.5 nH**
* **C6 = 1.5 pF**
* **C9 = 2.0 pF**
* **C11 = 0.3 pF**
* **C13 = 3.9 pF** 

**Do not improvise this section.** Put these parts as close as physically possible to the nRF ANT/VSS_PA/DECRF region, then route out as a 50 Ω feed.

### B) The transmission line to the antenna (must be CPWG 50 Ω and short)

Abracon recommends:

* a **50 Ω** transmission line
* keep it **as short as possible**
* use **CPWG** 

### C) The antenna placement + keepout (the “don’t mess this up” rules)

Abracon’s key constraints:

* Antenna must be **on the PCB edge** 
* The copper **cutout must extend through all PCB layers** and a **robust via structure** is recommended around the cutout/ground edge 
* They specify **recommended ground clearance 4.6 × 3.5 mm** and **PCB edge mounting** 
* Plastic near the antenna can shift resonance downward; measure/tune in the final enclosure 

Also, they explicitly warn to keep nearby components “low” near the keepout (their “topographical slope” guidance). 

### D) The antenna tuning network (put it at the antenna feed, not at the SoC)

Abracon’s EVB uses a small matching network right next to the antenna:

* X2 = **5.1 pF**
* X3 = **2.2 nH**
* X1 = DNP 

**How to integrate with the Nordic RF network:**

* Treat Nordic’s RF output network as producing a “nominal 50 Ω” feed.
* Route CPWG 50 Ω to the antenna region.
* Place a **PI footprint** (3-part) right before the antenna pad:

  * Start with Abracon’s values (5.1 pF + 2.2 nH, one pad DNP). 
  * Expect to change values once you test inside the PREMTA000 plastic enclosure. 

---

## 4) Concrete “fill-ins” for your BOM sections (connector + clocks + antenna)

### CN-REMO / TLIN “connector side”

* **D1** reverse-blocking diode between `VBAT_RAW` and `VSUP_PROT` (required conceptually by TI) 
* **C_VSUP** 100 nF at TLIN VSUP 
* **R_LIN_SER** 1 kΩ (SIG → TLIN LIN) 
* **C_LIN** 220 pF (TLIN LIN → GND) 
* (Recommended) **TVS** on 12 V at connector; (optional) **ESD clamp** on SIG at connector 

### Clocks

* **X2 32 MHz** between XC1/XC2 
* **X1 32.768 kHz** between XL1/XL2 
* Default: use **internal load caps**; add **DNP footprints** for external caps in case you need them 

### RF + antenna

* Nordic RF network values (L2/L3/L4/C6/C9/C11/C13) 
* CPWG 50 Ω short feed 
* Antenna edge placement + all-layer cutout + via fence 
* Antenna match starting point: **5.1 pF + 2.2 nH** 

---

If you want, I can turn this into a single “schematic-level” connection list (J1 → protection → TLIN pins, and nRF clock/RF pin blocks) that you can drop straight into KiCad/Altium as net names—using the exact values above and leaving only the diode/TVS part-number choices open.

---

Below is how I’d wire **CN-REMO ↔ TLIN14313**, plus what I’d implement for the **nRF54 clocks** and **2.4 GHz antenna/RF chain** (with the specific “fill in the ?” values your `COMPONENTS.md` is missing).

---

## 1) CN-REMO connector → TLIN14313 (LIN SBC) front end

### CN-REMO pinout / cable semantics

Your LG bus is the 3-wire harness:

* **RED = 12 V**
* **YELLOW = SIG**
* **BLACK = GND** 

Important nuance from the LG docs: **if you ever deploy this as a “slave” node on a group cable, don’t connect RED (power) — use only SIG+GND** or you can lose comms. 
(Inside the *master* remote enclosure, you’re already on the master harness, so you can safely power your add-on from the existing RED feed.)

### Recommended “connector → transceiver” schematic block

TI’s layout guidance is basically: put protection/filtering **right at the connector** so junk doesn’t get onto your board. 

**J1 (CN-REMO mating)**

* J1-RED  → `VBUS_12V_RAW`
* J1-BLACK → `GND`
* J1-YELLOW → `BUS_SIG_RAW`

**Power into TLIN14313**

* `VBUS_12V_RAW` → **D_REV (reverse battery blocking diode)** → `VSUP`
  TI explicitly expects VSUP to be fed through an **external reverse battery-blocking diode**, and wants **100 nF decoupling close to VSUP**. 
* At **VSUP pin**: **C_VSUP = 100 nF** (place as close as possible). 
* TLIN supply range: **5.5–28 V** on VSUP/VBAT and LIN bus input up to 28 V. 

**TLIN VCC output decoupling**

* At **VCC pin**: **C_VCC_BULK = 10 µF** (and meet ESR constraints)
  TI calls out **C(VCC)=10 µF** and an allowed output-cap ESR range. 
  (Your earlier TLIN decoupling plan of “10 µF + small MLCC” aligns with TI’s own simplified schematics. )

**BUS signal (YELLOW) into TLIN LIN pin**

* `BUS_SIG_RAW` → (optional low-cap **ESD diode to GND** right at connector) → **R_SER = 1 kΩ (series)** → `LIN` pin
* `LIN` pin → **C_LIN = 220 pF to GND** (right by TLIN / LIN entry)

Those exact “1 kΩ + 220 pF” values appear in TI’s simplified schematics for a LIN bus interface.  

**Do you need an external pull-up on the bus?**
No (in “responder” style): TLIN has an **internal pull-up to VSUP on LIN** (20–60 kΩ) and a defined “serial diode” drop in that pull-up path. 
So treat your node as **a listener/responder** and avoid adding “strong” external pull-ups unless you discover the LG bus requires something special.

### Optional: VBAT sense / PV / DIV_ON footprints (nice to have)

If you want to *measure* the raw red wire (VBUS) using TLIN’s VBAT/PV features, TI’s recommended operating conditions mention VBAT sense using a **470 Ω series resistor with a 100 nF cap to ground**. 
Even if you don’t populate it at first spin, I’d keep pads for it.

---

## 2) Clock circuits (nRF54)

Your `COMPONENTS.md` lists:

* **32 MHz crystal (2016, CL=8 pF, ±40 ppm)**
* **32.768 kHz crystal (2012, CL=9 pF, ±20 ppm)** 

Nordic’s own reference BOM for nRF54L15 QFN-48 config 1 matches those exact specs (CL=9 pF for 32.768k, CL=8 pF for 32 MHz). 

### Do you need external load capacitors?

Often **no**, because the nRF54 oscillators are designed to work with **internal (integrated) capacitors** and you select/tune the effective load in registers. Nordic explicitly states the HFXO “supports integrated capacitors” (Pierce oscillator). 
For LFXO, Nordic gives the load capacitance range (6–9 pF) and even specifies **Cpin when the internal capacitor is disabled (INTCAP=0)**. 

**Practical recommendation for your tiny board:**

* Route crystals **tight/short/symmetric** to XC1/XC2 and XL1/XL2.
* Start with **no external load caps populated**.
* Add **DNP footprints** for 2× tiny caps on each crystal only if you want a “plan B” for bring-up/tuning in the enclosure.

---

## 3) Antenna + RF chain (nRF54 → matching → Abracon AANI-CH-0070)

Your `COMPONENTS.md` calls for:

* **Abracon AANI-CH-0070 chip antenna**
* With a **5.1 pF** cap and **2.2 nH** inductor (Murata part numbers listed). 

Abracon confirms the EVB is **pre-tuned** for 2.4–2.5 GHz using:

* X2 = **5.1 pF**
* X3 = **2.2 nH**
* X1 = not mounted 

### The nRF54 side: implement Nordic’s RF network first

Nordic is very explicit that for good RF performance you should use **their PCB layouts and component values**. 
In the QFN-48 “Circuit configuration 1”, the RF/antenna filtering/matching components are (0201 parts):

* **L2 = 2.7 nH**
* **L3 = 3.5 nH**
* **L4 = 3.5 nH**
* **C6 = 1.5 pF**
* **C9 = 2.0 pF**
* **C11 = 0.3 pF**
* **C13 = 3.9 pF**  

Also note the **two “gotchas”** Nordic calls out:

* **C6 ground** must connect **only** to VSS_PA (top layer) and VSS_PA must only connect to the center pad under the package. 
* **C9 ground** must be isolated from all ground layers **except the bottom ground layer**. 

That grounding discipline is *not optional* if you want the reference RF performance.

### Then the antenna side: follow Abracon’s footprint + keepout rules

Key antenna layout constraints:

* Recommended ground clearance: **4.6 × 3.5 mm**
* Mounting: **PCB edge**
* The copper cutout must extend through **all PCB layers**, and use a robust via fence around the cutout/edge ground.  

And Abracon warns that **plastic housings near the antenna often shift resonance downward** — which is *exactly* your use case (embedded inside a plastic remote). 
So you should expect to retune the matching network (values may change). 

### How to combine Nordic’s RF network with Abracon’s matching network (without “double matching” mistakes)

Think in blocks:

1. **nRF54 RF pin → Nordic’s required filter/match network** (the L2/L3/L4/C6/C9/C11/C13 set)
2. A short **50 Ω controlled-impedance feed** to the antenna region (your 2-layer stack is 0.508 mm FR-4 core). 
3. **Antenna tuning network (placeholders)** right next to the antenna footprint:

   * Implement the **same topology Abracon uses (X1/X2/X3 footprints)** and start with their pre-tuned values (5.1 pF and 2.2 nH). 
   * But expect to change them after you measure S11/in-enclosure behavior (because plastic + nearby wiring will detune it). 

Finally, your mechanical placement intention in `COMPONENTS.md` is already correct: put the **CN-REMO connector on the opposite edge from the antenna** to keep the cable/wiring from becoming part of the antenna system. 

---

### Quick “fill the ?” summary for `COMPONENTS.md`

**LIN SBC (TLIN14313)**

* **D_REV**: reverse battery blocking diode in series with VSUP 
* **C_VSUP**: 100 nF at VSUP 
* **C_VCC**: 10 µF at VCC (meet ESR spec) 
* **R_SER (SIG)**: 1 kΩ series 
* **C_LIN**: 220 pF to GND 
* Optional VBAT/PV sense conditioning: 470 Ω + 100 nF 

**nRF54 antenna interface (Nordic ref network)**

* L2 2.7 nH; L3/L4 3.5 nH; C6 1.5 pF; C9 2.0 pF; C11 0.3 pF; C13 3.9 pF 
* Follow the special C6/C9 grounding notes 

**Antenna tuning network (Abracon)**

* Start values: 5.1 pF + 2.2 nH (+ one DNP) 
* Keepout/cutout/via fence rules  

---

If you want, I can turn the above into a concrete **schematic page list** (exact nets + refdes suggestions, e.g., J1/D1/C1/R1/C2…) that matches your physical constraints (“tiny board inside the PREMTA000 housing”) and keeps the RF and bus domains from fighting each other.

---

Below is how I’d wire **CN-REMO ↔ TLIN14313-Q1**, plus the **clock** and **antenna/RF** blocks, with an emphasis on *what to actually place on the PCB and how to connect it*.

---

## 1) CN-REMO connector → TLIN14313-Q1 (power + bus front-end)

### CN-REMO wiring (what you’re interfacing to)

LG’s wired wall controller interface is a **3-wire link** at the indoor unit CN-REMO port: **Red = 12V, Yellow = Signal, Black = GND**.  

> Note: LG’s group-control docs warn that *slave* indoor units should only get **SIG+GND** (no 12V), or comms can fail. 
> That doesn’t prevent *your board* (inside the master wall controller) from using the **red 12V** rail, but it’s a good “don’t backfeed power” reminder if you ever prototype across group-control harnesses.

### Recommended “connector → TLIN” schematic block

Think of this as three sub-blocks:

#### A) Power entry (RED/BLACK → VSUP/GND)

* **CN-REMO_RED (12V)** → (optional fuse/PTC) → **reverse protection** → **TLIN VSUP**

  * TI explicitly references a “blocking diode” concept because TLIN’s **VBAT monitor input is intended to come from the battery prior to the blocking diode**. 
  * If you implement reverse protection with a diode/ideal-diode, that aligns with the intended VBAT vs VSUP partitioning.

* **Decoupling at TLIN VSUP (Pin 1):** **100 nF placed as close as possible** to VSUP. 

* **TLIN VCC (Pin 2) decoupling:** **10 µF to GND as close as possible**. 

* Layout note from TI: keep power/ground loops short and use multiple vias to reduce inductance. 

**Practical add-ons (strongly recommended at the connector):**

* **TVS diode** from CN-REMO_RED to GND (supply surge/ESD).
* Small **series impedance** (ferrite bead or a few ohms) between connector 12V and your local VSUP node to keep cable transients out of the board.
* A local **bulk cap** near the connector (in addition to TLIN’s close-in caps) if space allows.

#### B) LIN pin to CN-REMO_YELLOW (your “signal” entry)

Even though LG’s link is “slow UART over one wire”, TLIN’s physical layer behavior (dominant ≈ low, recessive ≈ high) matches the general electrical idea.

* **CN-REMO_YELLOW (SIG)** → **R_LIN (≈ 1 kΩ)** → **TLIN LIN pin**
* **C_LIN (≈ 220 pF)** from **LIN pin to GND** (responder node guidance)

  * TI’s responder-node layout guidance calls out **220 pF to ground on LIN**. 
  * TI’s simplified responder schematic also shows **~1 kΩ** and **220 pF** on LIN. 

**Why this matters:** the series R limits surge/ESD current into the pin and, together with the 220 pF, helps tame edge noise and cable “ring.”

Also, don’t add an external pull-up: TLIN already pulls the bus recessive with an **internal pull-up (~45 kΩ) and diode**.  

#### C) CN-REMO_BLACK to ground

* **CN-REMO_BLACK (GND)** → solid ground plane.
* Treat this as “cable ground”: bring it in at the connector, then stitch to your board ground with a short, low-inductance path.

---

## 2) TLIN14313-Q1 ↔ nRF54L10: what they share / how to connect

On the hardware side, the *main* shared resources are:

### Shared power rail (recommended)

Use TLIN’s integrated LDO output **VCC = 3.3 V version** to power the nRF54 and all 3.3 V logic. TLIN provides a **3.3 V or 5 V LDO** and describes up to ~125 mA depending on implementation. 

Also: TLIN’s digital I/O voltage behavior depends on the variant/mode at power-up; if you’re interfacing to a 3.3 V MCU, keep TLIN I/O at 3.3 V levels. 

### Shared digital interface

* TLIN **TXD/RXD** connect to nRF54 GPIOs (UART-style use) *or* TLIN SPI pins to nRF54 SPIM pins (if you’re actually using TLIN’s SPI control mode).
* TI notes RXD is push-pull and can connect directly to the processor. 

### Reset relationship

Keep resets independent unless you *intend* TLIN faults to reset nRF. If you do use TLIN nRST as a “supervisor” signal, TI shows nRST pulled up with **10 kΩ to the processor I/O rail**. 

---

## 3) nRF54 clocks (32 MHz + 32.768 kHz)

Your COMPONENTS.md calls out:

* **32 MHz crystal (2016), CL=8 pF, ±40 ppm**
* **32.768 kHz crystal (2012), CL=9 pF, ±20 ppm** 

Nordic’s reference “circuit configuration 1” BOM also explicitly lists those crystal types/specs (and notably does **not** list external load capacitors in that BOM). 

### Pin mapping (important for layout)

For QFN52 (your nRF54L10 package family), Nordic labels:

* **XL1 / XL2** are the **32.768 kHz crystal** connections. 
* The reference schematic shows the two crystals on **(XL1/XL2)** and **(XC1/XC2)**.  

### Layout rules of thumb (practical)

* Place both crystals as close as physically possible to their pins.
* Keep the two traces of each crystal pair the same length and tightly coupled.
* Don’t run fast digital traces under/near the crystals.
* If you later find startup margin issues, you can add optional DNP footprints for tiny shunt caps, but start by following Nordic’s reference approach (since their BOM omits discrete load caps). 

---

## 4) Antenna + RF: Nordic front-end + Abracon chip antenna

You effectively have **two matching layers**:

1. **Nordic “radio front-end” network** (balun/match/filter from ANT pin to a 50 Ω-ish feed)
2. **Antenna-specific tuning network** right at the chip antenna (because plastic enclosure + nearby parts will detune)

### A) Nordic reference RF network (start here)

Nordic’s circuit configuration reference shows the RF component set and values (example: L2 2.7 nH, L3/L4 3.5 nH, C6 1.5 pF, C9 2.0 pF, C11 0.3 pF, C13 3.9 pF, etc.).   
Nordic also flags that “antenna filtering components are subject to change,” so treat their ref as authoritative for your exact silicon/doc rev. 

**Critical grounding constraints (don’t ignore):**
Nordic includes explicit notes for C6 and C9 grounding isolation/connection to VSS_PA. 
This is one of those “layout is part of the circuit” requirements.

### B) Abracon AANI-CH-0070 placement + matching

Abracon specifies:

* **Edge-mount only**, with **recommended ground clearance 4.6 × 3.5 mm** 
* A **50 Ω feedline** kept short, and they recommend **CPWG** 
* The antenna footprint’s **rectangular copper cutout must extend through all PCB layers**, and a **via fence/robust via structure** around the cutout/ground edge is recommended. 
* Plastic/metal nearby can shift tuning; **plastic above often shifts resonance downward**, so measure in final enclosure and tune with a matching network. 

Abracon’s eval board “pre-tuned” matching values:

* **X2 = 5.1 pF**, **X3 = 2.2 nH**, **X1 = DNP** 

### How to combine Nordic + Abracon without fighting yourself

* Implement **Nordic’s RF network exactly** from the ANT pin outward to a defined **“RF_50”** node.
* From **RF_50 → chip antenna**, place **a second, tiny tuning network footprint** (e.g., a Pi or series+shunt arrangement) right at the antenna feed.

  * Populate initially with Abracon’s “pre-tuned” parts (5.1 pF, 2.2 nH) as a starting point. 
  * Expect to adjust once the PCB is inside the plastic enclosure (since that alone can detune). 

---

## 5) A compact “what goes where” checklist (for your PCB)

**Connector side (noise lives here):**

* CN-REMO connector
* TVS + reverse protection + bulk cap
* TLIN VSUP 100 nF right at pin 
* TLIN LIN R/C right at LIN pin (keep the “dirty cable” away from the rest of the board) 

**Center (logic/power):**

* TLIN VCC 10 µF right at pin 
* nRF54 supply decoupling and DC/DC parts per Nordic circuit config (FB1/L1/Cx) 

**Antenna side (keep-out):**

* nRF54 RF network placed per Nordic with strict C6/C9 grounding rules 
* Short 50 Ω CPWG feedline 
* Abracon antenna at PCB edge + all-layer copper cutout + via fence 
* Abracon matching network right at antenna 

---

If you want, paste (or upload) any sketch of your intended board outline/connector position, and I’ll turn the above into a concrete **page-by-page schematic partition** with proposed reference designators (R_LIN, C_LIN, TVS1, etc.) and a layout placement order that minimizes re-spins.
