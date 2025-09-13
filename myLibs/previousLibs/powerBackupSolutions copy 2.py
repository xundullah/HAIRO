# === UDL.powerBackupSolutions.py ===

class ESS:
    """
    Energy Storage System (ESS) model.

    ⚙️ Example Equipment:
    - CATL EnerOne 372 kWh (LFP battery)
    - Powin 750E LFP battery (750 kWh)

    🛠️ Key Specs:
    - Capacity: default 372 kWh (can be customized)
    - Initial SoC: recommended ~49% before storm preparation
    - Charge/Discharge: Use separate methods to reflect real-world limitations.
    - Chemistry: LiFePO4 (LFP) ensures long cycle life and thermal stability.
    """

    def __init__(self, capacity_kwh=372, initial_soc=49.0):
        self.capacity_kwh = capacity_kwh
        self.energy_kwh = (initial_soc / 100) * capacity_kwh

    def charge(self, charge_power_kw, delta_t_hr):
        """
        Charges the ESS.

        Args:
            charge_power_kw: Power input (kW)
            delta_t_hr: Time interval (hours)

        Returns:
            (energy_kwh, soc_percent)
        """
        self.energy_kwh += charge_power_kw * delta_t_hr
        self.energy_kwh = min(self.energy_kwh, self.capacity_kwh)
        soc_percent = (self.energy_kwh / self.capacity_kwh) * 100
        return self.energy_kwh, soc_percent

    def discharge(self, discharge_power_kw, delta_t_hr):
        """
        Discharges the ESS.

        Args:
            discharge_power_kw: Power output (kW)
            delta_t_hr: Time interval (hours)

        Returns:
            (energy_kwh, soc_percent)
        """
        self.energy_kwh -= discharge_power_kw * delta_t_hr
        self.energy_kwh = max(0, self.energy_kwh)
        soc_percent = (self.energy_kwh / self.capacity_kwh) * 100
        return self.energy_kwh, soc_percent


import numpy as np

class HFS:
    """
    Hydrogen Fuel System (HFS) model.

    ⚙️ Example Equipment:
    - Tank: Hexagon Type IV Composite 150 kg H₂ tank (350 bar)
    - Fuel Cell: Ballard FCwave 30–50 kW PEM fuel cell
    - Electrolyzer: Nel M Series (30–60 kg/day)

    🛠️ Key Specs:
    - Capacity: 150 kg hydrogen (default)
    - Electrolyzer: 100 kW rated limit
    - Fuel Cell: 50 kW rated limit
    - Efficiencies:
        - Electrolyzer ~65%
        - Fuel Cell ~50%
    - Energy content: 39.4 kWh/kg (HHV)

    🔬 Thermal Modeling:
    - Temperature estimated internally (°C)
    - Heating rate: +1.5°C/hr (prod), +1.2°C/hr (consume)
    - Cool-down: -0.5°C/hr when idle


    📈 Pressure model:
    Uses ideal gas law approximation: P ~ (n * R * T) / V
    """

    def __init__(self,
                 tank_capacity_kg=150,
                 initial_sof=28.0,
                 electrolyzer_efficiency=0.65,
                 fuelcell_efficiency=0.5,
                 h2_energy_kwh_per_kg=39.4,
                 electrolyzer_max_kw=100,
                 fuelcell_max_kw=50,
                 nominal_pressure_bar=350,
                 initial_temperature_c=25.0):

        self.tank_capacity_kg = tank_capacity_kg
        self.h2_kg = (initial_sof / 100) * tank_capacity_kg

        self.electrolyzer_efficiency = electrolyzer_efficiency
        self.fuelcell_efficiency = fuelcell_efficiency
        self.h2_energy_kwh_per_kg = h2_energy_kwh_per_kg

        self.electrolyzer_max_kw = electrolyzer_max_kw
        self.fuelcell_max_kw = fuelcell_max_kw

        self.nominal_pressure_bar = nominal_pressure_bar

        self.temperature_c = initial_temperature_c

        # Constants for pressure estimation
        self.molar_mass_h2 = 2.016  # grams/mol
        self.tank_volume_liters = self._estimate_tank_volume()

        # Thermal model constants
        self.alpha_prod = 1.5  # °C per hr per full-load
        self.alpha_cons = 1.2
        self.beta_cooldown = 0.5

    def _estimate_tank_volume(self):
        """
        Estimate: ~11 liters per 1 kg of H₂ at 350 bar.
        """
        return self.tank_capacity_kg * 11

    def _compute_pressure(self):
        """
        Uses ideal gas law: P = nRT / V.
        """
        R = 0.08314  # bar·L/(mol·K)
        n_moles = (self.h2_kg * 1000) / self.molar_mass_h2
        V = self.tank_volume_liters
        T_k = self.temperature_c + 273.15
        P = (n_moles * R * T_k) / V
        return round(P, 1)

    def _update_temperature(self, action, power_kw, max_kw, delta_t_hr):
        """
        Updates temperature based on action: 'produce', 'consume', or 'idle'
        """
        if action == 'produce':
            rise = self.alpha_prod * (power_kw / max_kw) * delta_t_hr
            self.temperature_c += rise
        elif action == 'consume':
            rise = self.alpha_cons * (power_kw / max_kw) * delta_t_hr
            self.temperature_c += rise
        elif action == 'idle':
            self.temperature_c -= self.beta_cooldown * delta_t_hr

        # Clamp: realistic bounds (0°C min to avoid unrealistic)
        self.temperature_c = max(0, self.temperature_c)

    def produce_(self, h2_production_power_kw, delta_t_hr):
        """
        Produces hydrogen and updates temperature/pressure.

        Returns:
            (h2_kg, sof_percent, status_msg, pressure_bar, temperature_c)
        """
        if h2_production_power_kw > self.electrolyzer_max_kw:
            status = f"⚠️ Electrolyzer limited to {self.electrolyzer_max_kw} kW (was {h2_production_power_kw} kW)"
            h2_production_power_kw = self.electrolyzer_max_kw
        else:
            status = "✅ Electrolyzer within rated power limit."

        h2_produced_kg = (h2_production_power_kw * self.electrolyzer_efficiency) / self.h2_energy_kwh_per_kg * delta_t_hr
        self.h2_kg += h2_produced_kg

        if self.h2_kg > self.tank_capacity_kg:
            self.h2_kg = self.tank_capacity_kg
            status += " | Tank full: limited to max capacity."

        sof_percent = (self.h2_kg / self.tank_capacity_kg) * 100

        self._update_temperature('produce', h2_production_power_kw, self.electrolyzer_max_kw, delta_t_hr)
        pressure_bar = self._compute_pressure()

        if self.temperature_c > 45:
            status += " ⚠️ High temperature detected (>45°C)."

        return self.h2_kg, sof_percent, status, pressure_bar, round(self.temperature_c, 1)
    
    def produce(self, h2_production_power_kw, delta_t_hr):
        """
        Produces hydrogen (electrolyzer charging the tank).

        Returns:
            (h2_kg, sof_percent, status_msg, pressure_bar, temperature_c)
        """
        # --- Check max capacity ---
        if h2_production_power_kw > self.electrolyzer_max_kw:
            status = f"⚠️ Electrolyzer limited to {self.electrolyzer_max_kw} kW (was {h2_production_power_kw} kW)"
            h2_production_power_kw = self.electrolyzer_max_kw
        else:
            status = "✅ Electrolyzer OK"

        # --- H2 Production ---
        h2_produced_kg = (h2_production_power_kw * self.electrolyzer_efficiency) / self.h2_energy_kwh_per_kg * delta_t_hr
        self.h2_kg += h2_produced_kg
        if self.h2_kg > self.tank_capacity_kg:
            self.h2_kg = self.tank_capacity_kg
            status += " | Tank full."

        sof_percent = (self.h2_kg / self.tank_capacity_kg) * 100

        # --- Update temperature ---
        self.temperature_c += 0.05 * h2_production_power_kw * delta_t_hr
        if self.temperature_c > 45:
            status += " ⚠️ High temp warning (>45°C)"

        # --- Estimate pressure ---
        pressure_bar = (self.h2_kg / self.tank_capacity_kg) * self.nominal_pressure_bar

        return self.h2_kg, sof_percent, status, pressure_bar, self.temperature_c


    def consume(self, h2_consumption_power_kw, delta_t_hr):
        """
        Consumes hydrogen and updates temperature/pressure.

        Returns:
            (h2_kg, sof_percent, status_msg, pressure_bar, temperature_c)
        """
        if h2_consumption_power_kw > self.fuelcell_max_kw:
            status = f"⚠️ Fuel Cell limited to {self.fuelcell_max_kw} kW (was {h2_consumption_power_kw} kW)"
            h2_consumption_power_kw = self.fuelcell_max_kw
        else:
            status = "✅ Fuel Cell within rated power limit."

        h2_needed_kg = (h2_consumption_power_kw / (self.fuelcell_efficiency * self.h2_energy_kwh_per_kg)) * delta_t_hr
        self.h2_kg -= h2_needed_kg

        if self.h2_kg < 0:
            self.h2_kg = 0
            status += " | Tank empty: no more H₂ available."

        sof_percent = (self.h2_kg / self.tank_capacity_kg) * 100

        self._update_temperature('consume', h2_consumption_power_kw, self.fuelcell_max_kw, delta_t_hr)
        pressure_bar = self._compute_pressure()

        if self.temperature_c > 45:
            status += " ⚠️ High temperature detected (>45°C)."

        return self.h2_kg, sof_percent, status, pressure_bar, round(self.temperature_c, 1)

    def idle(self, delta_t_hr):
        """
        Natural cooling when idle.
        """
        self._update_temperature('idle', 0, 1, delta_t_hr)
        pressure_bar = self._compute_pressure()
        return round(self.temperature_c, 1), pressure_bar

    def status_report(self):
        sof_percent = (self.h2_kg / self.tank_capacity_kg) * 100
        pressure_bar = self._compute_pressure()
        return {
            'H2_kg': round(self.h2_kg, 2),
            'SoF_%': round(sof_percent, 1),
            'Pressure_bar': pressure_bar,
            'Temperature_C': round(self.temperature_c, 1)
        }


