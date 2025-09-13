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


class HFS:
    """
    Hydrogen Fuel System (HFS) model.

    ⚙️ Example Equipment:
    - Tank: Hexagon Type IV Composite 150 kg H₂ tank (350 bar)
    - Fuel Cell: Ballard FCwave 30–50 kW PEM fuel cell
    - Electrolyzer: Nel M Series (30–60 kg/day)

    🛠️ Key Specs:
    - Capacity: 150 kg hydrogen (can be customized)
    - Initial SoF: ~28% (realistic starting point for preparedness)
    - Efficiencies:
        - Electrolyzer ~65% (default)
        - Fuel Cell ~50% (default)
    - Energy content: 1 kg H₂ ≈ 39.4 kWh (HHV)

    📝 Usage:
    Use `produce()` for generating hydrogen (electrolyzer) and `consume()` for using hydrogen (fuel cell).
    """

    def __init__(self, tank_capacity_kg=150, initial_sof=28.0,
                 electrolyzer_efficiency=0.65, fuelcell_efficiency=0.5,
                 h2_energy_kwh_per_kg=39.4):
        self.tank_capacity_kg = tank_capacity_kg
        self.h2_kg = (initial_sof / 100) * tank_capacity_kg
        self.electrolyzer_efficiency = electrolyzer_efficiency
        self.fuelcell_efficiency = fuelcell_efficiency
        self.h2_energy_kwh_per_kg = h2_energy_kwh_per_kg

    def produce(self, h2_production_power_kw, delta_t_hr):
        """
        Produces hydrogen (stores into tank).

        Args:
            h2_production_power_kw: Input power to electrolyzer (kW)
            delta_t_hr: Time interval (hours)

        Returns:
            (h2_kg, sof_percent)
        """
        h2_produced_kg = (h2_production_power_kw * self.electrolyzer_efficiency) / self.h2_energy_kwh_per_kg * delta_t_hr
        self.h2_kg += h2_produced_kg
        self.h2_kg = min(self.h2_kg, self.tank_capacity_kg)
        sof_percent = (self.h2_kg / self.tank_capacity_kg) * 100
        return self.h2_kg, sof_percent

    def consume(self, h2_consumption_power_kw, delta_t_hr):
        """
        Consumes hydrogen (from tank to produce power).

        Args:
            h2_consumption_power_kw: Power demand (kW)
            delta_t_hr: Time interval (hours)

        Returns:
            (h2_kg, sof_percent)
        """
        h2_needed_kg = (h2_consumption_power_kw / (self.fuelcell_efficiency * self.h2_energy_kwh_per_kg)) * delta_t_hr
        self.h2_kg -= h2_needed_kg
        self.h2_kg = max(0, self.h2_kg)
        sof_percent = (self.h2_kg / self.tank_capacity_kg) * 100
        return self.h2_kg, sof_percent
