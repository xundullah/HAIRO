class HFS:
    """
    Hydrogen Fuel System (HFS) model.

    ✅ Default Equipment:
    - Tank: Hexagon Type IV Composite 150 kg (350 bar)
    - Fuel Cell: Ballard FCwave 30–50 kW PEM
    - Electrolyzer: Nel M Series (max ~100 kW)

    🛠️ Auto-tracks:
    - H2 kg (SoF)
    - Temperature (°C)
    - Pressure (bar)

    🚨 Auto-safety:
    - Temp >45°C triggers cool-down.
    - Pressure >350 bar triggers venting.
    """

    def __init__(self, initial_sof=28.0, initial_temperature_c=25.0, initial_pressure_bar = 314):
        # System specifications
        self.tank_capacity_kg           = 150   
        self.tank_volume_liters         = 2250 
        self.electrolyzer_efficiency    = 0.65   
        self.fuelcell_efficiency        = 0.53  
        self.h2_energy_kwh_per_kg       = 39.4
        self.electrolyzer_max_kw        = 100
        self.fuelcell_max_kw            = 30
        self.nominal_pressure_bar       = 600


        # Initial dynamic states
        self.h2_kg                      = (initial_sof / 100) * self.tank_capacity_kg
        self.temperature_c              = initial_temperature_c
        self.pressure_bar               = initial_pressure_bar 


    def _update_pressure(self):
        """
        Updates self.pressure_bar using the ideal gas law: P = nRT / V.
        """
        R                               = 0.08314       # bar·L/(mol·K)
        molar_mass_h2                   = 2.016         # grams/mol
        n_moles                         = (self.h2_kg * 1000) / molar_mass_h2
        V                               = self.tank_volume_liters
        T_k                             = self.temperature_c + 273.15
        self.pressure_bar               = round((n_moles * R * T_k) / V, 1)


    def _update_temperature(self, action, power_kw, max_kw, delta_t_hr):
        """
        Updates temperature based on 'produce', 'consume', or 'idle'.
        """
        alpha_prod                 = 1.5  # °C per hr per full-load (produce)
        alpha_cons                 = 1.2  # °C per hr per full-load (consume)
        beta_cooldown              = 0.5  # °C/hr (cooling effect)
        if action == 'produce':
            self.temperature_c += alpha_prod * (power_kw / max_kw) * delta_t_hr
        elif action == 'consume':
            self.temperature_c += alpha_cons * (power_kw / max_kw) * delta_t_hr
        elif action == 'idle':
            self.temperature_c -= beta_cooldown * delta_t_hr
        self.temperature_c = max(0, self.temperature_c)

    def produce(self, h2_production_power_kw, delta_t_hr):
        """
        Produces hydrogen and auto-updates temp/pressure.

        Returns: (h2_kg, sof_percent, status_msg)
        """
        status = "OK"

        # Safety: overheat
        if self.temperature_c > 45:
            self._update_temperature('idle', 0, 1, delta_t_hr)
            status = "Paused: Cooling (Temp >45°C)"
            return self._report(status)
        
         # Safety: over-pressure
        if self.pressure_bar > self.nominal_pressure_bar:
            self.pressure_bar = 314 
            status = "Paused: Venting (Over-Pressure)"
            return self._report(status)

        # Cap power if above max
        actual_power_kw = min(h2_production_power_kw, self.electrolyzer_max_kw)
        if h2_production_power_kw > self.electrolyzer_max_kw:
            status = f"Limited: Electrolyzer {self.electrolyzer_max_kw} kW max"

        # Produce H2
        h2_produced_kg = (actual_power_kw * self.electrolyzer_efficiency) / self.h2_energy_kwh_per_kg * delta_t_hr
        self.h2_kg += h2_produced_kg
        if self.h2_kg > self.tank_capacity_kg:
            self.h2_kg = self.tank_capacity_kg
            status += " | Tank Full"

        # Update temperature and pressure
        self._update_temperature('produce', actual_power_kw, self.electrolyzer_max_kw, delta_t_hr)
        self._update_pressure()


        return self._report(status)

    def consume(self, h2_consumption_power_kw, delta_t_hr):
        """
        Consumes hydrogen and auto-updates temp/pressure.

        Returns: (h2_kg, sof_percent, status_msg)
        """
        status = "OK"

        # Safety: overheat
        if self.temperature_c > 45:
            self._update_temperature('idle', 0, 1, delta_t_hr)
            status = "Paused: Cooling (Temp >45°C)"
            return self._report(status)

        # Cap power if above max
        actual_power_kw = min(h2_consumption_power_kw, self.fuelcell_max_kw)
        if h2_consumption_power_kw > self.fuelcell_max_kw:
            status = f"Limited: Fuel Cell {self.fuelcell_max_kw} kW max"

        # Consume H2
        h2_needed_kg = (actual_power_kw / (self.fuelcell_efficiency * self.h2_energy_kwh_per_kg)) * delta_t_hr
        self.h2_kg -= h2_needed_kg
        if self.h2_kg < 0:
            self.h2_kg = 0
            status += " | Tank Empty"

        # Update temperature and pressure
        self._update_temperature('consume', actual_power_kw, self.fuelcell_max_kw, delta_t_hr)
        self._update_pressure()

        return self._report(status)

    def idle(self, delta_t_hr):
        """
        Cooling naturally when idle.
        """
        self._update_temperature('idle', 0, 1, delta_t_hr)
        self._update_pressure()
        return self._report("Idle: Cooling")

    def _report(self, status_msg):
        sof_percent = (self.h2_kg / self.tank_capacity_kg) * 100
        return (
            round(self.h2_kg, 2),
            round(sof_percent, 1),
            f"{status_msg} | Temp: {round(self.temperature_c, 1)}°C | Pressure: {self.pressure_bar} bar"
        )



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