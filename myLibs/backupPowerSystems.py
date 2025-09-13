"""
===========================================================================
Parametric Li-ion ESS Model — Based on Sungrow SBR128 Modules
===========================================================================

Data-driven context
-------------------
• Module dataset            :  “SBR128” (LiFePO₄), **12.8 kWh** name-plate capacity  
• Reference design in study :  16 stacks sized for **3 day** of average CBS demand  
• Extended autonomy option  :  Caller may scale the bank to N days (e.g., 3-day buffer)  
• Design rule               :  Battery is cycled to **70 % Depth-of-Discharge**  
                               ⇒  SOCₘᵢₙ = 1 – DoD = 0.30  

Theoretical foundation
----------------------
Hourly energy balance (Eq. 4 of the manuscript):

    SOC_B(t) = SOC_B(t–1)
               + [ P_BC · η_BC  –  P_BD / η_BD ] · Δt / E_B

    P_BC : charge power into the cells  [kW]  
    P_BD : discharge power to the load  [kW]  
    η_BC, η_BD : charge / discharge efficiencies (incl. PCS losses)  
    Δt : simulation step supplied by user (h, may be fractional)  
    E_B : *nominal* bank capacity = 12.8 kWh × stacks × autonomy_days  

Class overview
--------------
EnergyStorageSystem(stacks=16, autonomy_days=1, soc=1.00)

    • charge(P_in, Δt)     —— applies  +P_BC·η_BC term  
    • discharge(P_out, Δt) —— applies  –P_BD/η_BD term  
    • observe()            —— returns last status string  

All public returns (SOC, energy) are rounded to **two decimals**.
"""
from dataclasses import dataclass, field
from typing import Tuple


@dataclass
class EnergyStorageSystem:
    # ─────────────── caller-configurable design settings ───────────────
    stacks: int = 16              # number of SBR128 modules ordered
    autonomy_days: float = 3.0    # days of average load to be covered
    unit_kwh: float = 12.8        # capacity per SBR128 [kWh]

    # ─────────────── performance / lifetime assumptions ────────────────
    eta_c: float = 0.96           # charge efficiency  η_BC
    eta_d: float = 0.96           # discharge efficiency η_BD

    # ─────────────── recommended SoC operating window ────────────────
    # Lithium-ion packs are typically cycled between 20 % and 90 % SoC
    # (see Eq. 10 and Ref. 42 in the cited paper) to prolong calendar life.
    soc_min: float = 0.20   # lower bound  → avoid deep‐discharge stress
    soc_max: float = 0.90   # upper bound  → avoid prolonged 100 % float

    # ─────────────── mutable run-time state variables ──────────────────
    soc: float = 1.00             # initial state-of-charge (1 → 100 %)
    status: str = "Battery Full"  # initial status message
    energy_kwh: float = field(init=False)  # stored energy [kWh]

    # ───────────────────────── initialisation -- Eq. 4 inputs ───────────
    def __post_init__(self) -> None:
        # Nominal capacity scaled by stack-count × autonomy buffer
        self.E_B: float = self.unit_kwh * self.stacks * self.autonomy_days
        self.energy_kwh = self.soc * self.E_B

    # ───────────────────────────── charging path ───────────────────────
    def charge(self, p_in_kw: float, dt_hr: float = 1.0) \
            -> Tuple[float, float, str]:
        """
        Apply +P_BC term of Eq. 4.
        Stores *p_in_kw* for *dt_hr* hours, limited by η_BC and SOCₘₐₓ.
        """
        if dt_hr <= 0:
            raise ValueError("Δt must be positive (hours)")

        # Reject if bank already full
        if self.soc >= self.soc_max:
            self.status = "Charge-rejected: full"
            return round(self.soc, 2), round(self.energy_kwh, 2), self.status

        # Net energy that survives charge losses
        ΔE_kwh = p_in_kw * self.eta_c * dt_hr
        ΔE_kwh = min(ΔE_kwh, self.soc_max * self.E_B - self.energy_kwh)

        # Update state
        self.energy_kwh += ΔE_kwh
        self.soc = self.energy_kwh / self.E_B
        self.status = "Charging" if ΔE_kwh else "Idle"

        return round(self.soc, 2), round(self.energy_kwh, 2), self.status

    # ─────────────────────────── discharging path ──────────────────────
    def discharge(self, load_kw: float, dt_hr: float = 1.0) \
            -> Tuple[float, float, str]:
        """
        Apply −P_BD/η_BD term of Eq. 4.
        Supplies *load_kw* for *dt_hr* hours, limited by SOCₘᵢₙ.
        """
        if dt_hr <= 0:
            raise ValueError("Δt must be positive (hours)")

        # Reject if bank already at minimum SOC
        if self.soc <= self.soc_min:
            self.status = "Discharge-rejected: low"
            return round(self.soc, 2), round(self.energy_kwh, 2), self.status

        # Energy that must be withdrawn (includes η losses)
        ΔE_kwh = load_kw / self.eta_d * dt_hr
        ΔE_kwh = min(ΔE_kwh, self.energy_kwh - self.soc_min * self.E_B)

        # Update state
        self.energy_kwh -= ΔE_kwh
        self.soc = self.energy_kwh / self.E_B
        self.status = "Discharging" if ΔE_kwh else "Idle"

        return round(self.soc, 2), round(self.energy_kwh, 2), self.status

    # ───────────────────────────── observation ─────────────────────────
    def observe(self) -> str:
        """Return last status string for dashboards or logs."""
        return self.status