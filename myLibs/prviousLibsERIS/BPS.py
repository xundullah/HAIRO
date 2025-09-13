class HFS:
    """
    Hydrogen Fuel System (HFS) — validated against equations from:
    Roberta Tatti, "Hydrogen storage integrated in off-grid power systems: a case study".

    Main Modeling:
    - Eq. (5): Electrolyzer Efficiency     η_HG = (ṁ_H2 × HHV) / P_HG
    - Eq. (6): Fuel Cell Efficiency        η_FC = P_FC / (ṁ_H2 × HHV)
    - Eq. (7): Energy-Based SoH Tracking   SoH(t) = SoH(t-1) + [(P_HG × η_HG – P_FC / η_FC) / E_H2_max] × Δt
    - Eq. (8): Hydrogen Tank Energy Capacity from Ideal Gas Law

    All energy flows are tracked in MJ, using Higher Heating Value (HHV).
    """

    def __init__(self,
                 tank_volume_m3=2.5,              # Hydrogen tank volume [m³]
                 pressure_nom_bar=35,             # Nominal pressure of H2 tank [bar]
                 pressure_min_bar=2,              # Minimum operating pressure for FC [bar]
                 temperature_c=25,                # Internal system temperature [°C]
                 electrolyzer_efficiency=0.65,    # Electrolyzer efficiency η_HG
                 fuelcell_efficiency=0.5,         # Fuel cell efficiency η_FC
                 HHV_MJ_per_kg=141.78,            # Higher Heating Value of hydrogen [MJ/kg]
                 electrolyzer_max_kw=100,         # Max electrolyzer input power [kW]
                 fuelcell_max_kw=50,              # Max fuel cell output power [kW]
                 initial_SoH=0.3):                # Initial State of Hydrogen (SoH) as a fraction (0–1)

        # Thermochemical constants
        self.MM_H2      = 2.016                         # Molar mass of hydrogen [kg/kmol]
        self.R          = 8.314                         # Ideal gas constant [J/mol·K]
        self.HHV        = HHV_MJ_per_kg                 # HHV of H2 [MJ/kg]
        self.T          = 273.15 + temperature_c        # Absolute temperature [K]

        # Tank parameters
        self.V_HT       = tank_volume_m3                # Tank volume [m³]
        self.P_NOM      = pressure_nom_bar * 1e5        # Convert bar → Pa
        self.P_MIN      = pressure_min_bar * 1e5        # Convert bar → Pa

        # Maximum energy capacity of H2 tank (Eq. 8) [MJ]
        self.E_H2_max = self.HHV * ((self.P_NOM - self.P_MIN) * self.V_HT * self.MM_H2) / (self.R * self.T)

        # Current SoH (State of Hydrogen), initialized [0–1]
        self.SoH = initial_SoH

        # Component specs
        self.electrolyzer_efficiency    = electrolyzer_efficiency
        self.fuelcell_efficiency        = fuelcell_efficiency
        self.electrolyzer_max_kw        = electrolyzer_max_kw
        self.fuelcell_max_kw            = fuelcell_max_kw



    def produce(self, input_power_kw, delta_t_hr):
        """
        Simulate H2 production by electrolyzer over a given time period.

        Args:
            input_power_kw: Power applied to electrolyzer [kW]
            delta_t_hr: Duration of operation [hours]

        Returns:
            SoH_percent: Updated SoH [%]
            status: Operation status message
        """

        # Cap input to electrolyzer maximum
        if input_power_kw > self.electrolyzer_max_kw:
            input_power_kw = self.electrolyzer_max_kw
            status = "⚠️ Electrolyzer capped"
        else:
            status = "✅ Electrolyzer OK"

        # Convert kWh to MJ (1 kWh = 3.6 MJ)
        E_input_MJ = input_power_kw * delta_t_hr * 3.6
        E_H2_produced_MJ = E_input_MJ * self.electrolyzer_efficiency

        # Update SoH using Eq. (7) positive term
        self.SoH += E_H2_produced_MJ / self.E_H2_max

        # Clip to max
        if self.SoH > 1.0:
            self.SoH = 1.0
            status += " | Tank full"

        return round(self.SoH * 100, 2), status

    def consume(self, output_power_kw, delta_t_hr):
        """
        Simulate H2 consumption by fuel cell over a given time period.

        Args:
            output_power_kw: Power demand from fuel cell [kW]
            delta_t_hr: Duration of operation [hours]

        Returns:
            SoH_percent: Updated SoH [%]
            status: Operation status message
        """

        # Cap output to fuel cell maximum
        if output_power_kw > self.fuelcell_max_kw:
            output_power_kw = self.fuelcell_max_kw
            status = "⚠️ Fuel Cell capped"
        else:
            status = "✅ Fuel Cell OK"

        # Energy demand in MJ
        E_output_MJ = output_power_kw * delta_t_hr * 3.6
        E_H2_required_MJ = E_output_MJ / self.fuelcell_efficiency

        E_available = self.SoH * self.E_H2_max

        # Clip if not enough energy
        if E_H2_required_MJ > E_available:
            E_H2_required_MJ = E_available
            status += " | ⚠️ Tank depleted"

        # Update SoH using Eq. (7) negative term
        self.SoH -= E_H2_required_MJ / self.E_H2_max
        self.SoH = max(self.SoH, 0.0)

        return round(self.SoH * 100, 2), status

    def check_pressure(self):
        """
        Estimate current tank pressure based on stored H2 energy using ideal gas law.

        Returns:
            Pressure in bar
        """
        # Current stored energy
        E_current = self.SoH * self.E_H2_max
        mass_kg = E_current / self.HHV
        n_kmol = mass_kg / self.MM_H2

        # Ideal gas law: P = (nRT)/V
        P_Pa = (n_kmol * 1000) * self.R * self.T / self.V_HT
        return round(P_Pa / 1e5, 2)  # Convert Pa → bar
