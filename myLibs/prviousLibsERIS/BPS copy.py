class HFS:
    """
    Hydrogen Fuel System (HFS) — final fixed version per Tatti et al.
    🚫 No h2_kg used. Only SoF (State of Fill) based on energy tracking.
    
    Equations:
    - Eq. (5): η_HG = (ṁ_H2 × HHV) / P_HG
    - Eq. (6): η_FC = P_FC / (ṁ_H2 × HHV)
    - Eq. (7): SoF(t) = SoF(t-1) + [(P_HG × η_HG – P_FC / η_FC) / E_H2] × Δt
    - Eq. (8): E_H2 capacity based on gas law
    """

    def __init__(self,
                 tank_volume_m3=2.5,
                 pressure_nom_bar=35,
                 pressure_min_bar=2,
                 temperature_c=25,
                 electrolyzer_efficiency=0.65,
                 fuelcell_efficiency=0.5,
                 HHV_MJ_per_kg=141.78,
                 electrolyzer_max_kw=100,
                 fuelcell_max_kw=50,
                 initial_sof=0.3):  # SoF in fraction (0–1)

        # Thermodynamic constants
        self.MM_H2 = 2.016  # kg/kmol
        self.R = 8.314  # J/mol.K
        self.HHV = HHV_MJ_per_kg  # MJ/kg
        self.T = 273.15 + temperature_c  # Kelvin
        self.V_HT = tank_volume_m3  # m³
        self.P_NOM = pressure_nom_bar * 1e5  # Pa
        self.P_MIN = pressure_min_bar * 1e5  # Pa

        # Maximum energy capacity based on Eq. (8)
        self.E_H2_max = self.HHV * ((self.P_NOM - self.P_MIN) * self.V_HT * self.MM_H2) / (self.R * self.T)  # MJ

        # State of Fill (SoF) = E(t)/E_max
        self.sof = initial_sof

        # Component parameters
        self.electrolyzer_efficiency = electrolyzer_efficiency
        self.fuelcell_efficiency = fuelcell_efficiency
        self.electrolyzer_max_kw = electrolyzer_max_kw
        self.fuelcell_max_kw = fuelcell_max_kw

    def produce(self, input_power_kw, delta_t_hr):
        """Electrolyzer: adds energy based on efficiency"""
        if input_power_kw > self.electrolyzer_max_kw:
            input_power_kw = self.electrolyzer_max_kw
            status = "⚠️ Electrolyzer capped"
        else:
            status = "✅ Electrolyzer OK"

        E_in = input_power_kw * delta_t_hr * 3.6  # kWh → MJ
        E_h2 = E_in * self.electrolyzer_efficiency
        self.sof += E_h2 / self.E_H2_max

        if self.sof > 1.0:
            self.sof = 1.0
            status += " | Tank full"

        return round(self.sof * 100, 2), status  # Return SoF as %

    def consume(self, output_power_kw, delta_t_hr):
        """Fuel Cell: removes energy based on efficiency"""
        if output_power_kw > self.fuelcell_max_kw:
            output_power_kw = self.fuelcell_max_kw
            status = "⚠️ Fuel Cell capped"
        else:
            status = "✅ Fuel Cell OK"

        E_out = output_power_kw * delta_t_hr * 3.6  # kWh → MJ
        E_h2_required = E_out / self.fuelcell_efficiency

        E_available = self.sof * self.E_H2_max
        if E_h2_required > E_available:
            E_h2_required = E_available
            status += " | ⚠️ Tank depleted"

        self.sof -= E_h2_required / self.E_H2_max
        if self.sof < 0:
            self.sof = 0.0

        return round(self.sof * 100, 2), status

    def check_pressure(self):
        """Estimate pressure using ideal gas law based on SoF"""
        E_current = self.sof * self.E_H2_max
        mass_kg = E_current / self.HHV
        n_kmol = mass_kg / self.MM_H2
        P = (n_kmol * 1000) * self.R * self.T / self.V_HT  # Pa
        return round(P / 1e5, 2)  # bar
