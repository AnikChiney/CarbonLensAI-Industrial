from flask import Flask, render_template, request
import json

app = Flask(__name__)

# Emission Factors (tCO2e per unit)
FACTORS = {
    'diesel': 0.00268, 'petrol': 0.00231, 'natural_gas': 0.00202,
    'coal': 2.86, 'lpg': 0.00151, 'electricity': 0.00071,
    'refrigerant_r22': 1.810, 'refrigerant_r410a': 2.088, 'refrigerant_r134a': 1.430,
    'steel': 1.85, 'cement': 0.90, 'aluminum': 12.7,
    'plastic': 2.70, 'paper': 0.94, 'glass': 0.85,
    'logistics_truck': 0.00012, 'logistics_ship': 0.00004, 'logistics_air': 0.00060,
    'waste_landfill': 0.50, 'waste_recycled': 0.10
}

# Energy Costs (INR per unit)
ENERGY_COSTS = {
    'electricity': 8.5,  # per kWh
    'diesel': 95,        # per litre
    'petrol': 105,       # per litre
    'natural_gas': 45,   # per SCM
    'coal': 8000,        # per tonne
    'lpg': 85            # per litre
}

CARBON_PRICE = 2500  # INR per tCO2e

def safe_float(value, default=0):
    """Safely convert to float, handling empty strings and None"""
    if value is None or value == '':
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def calculate_scenarios(data, scope1, scope2, scope3, total_emissions):
    """Calculate reduction scenarios based on actual input data"""
    scenarios = []
    
    # Scenario 1: Solar PV - based on electricity consumption
    if data['electricity'] > 0:
        solar_offset_pct = 40  # 40% offset
        solar_kwh = data['electricity'] * (solar_offset_pct / 100)
        solar_emission_reduction = solar_kwh * FACTORS['electricity']  # tCO2e
        solar_energy_savings = solar_kwh * ENERGY_COSTS['electricity']  # INR
        
        # Cost: ~INR 6 per watt, assume 5kW system per 10000 kWh monthly
        system_size_kw = solar_kwh / 150  # rough estimate
        solar_investment = system_size_kw * 60000  # INR 60k per kW installed
        
        solar_roi = (solar_energy_savings * 100 / solar_investment) if solar_investment > 0 else 0
        
        scenarios.append({
            'name': f'Rooftop Solar ({solar_offset_pct}% offset)',
            'investment': round(solar_investment, 2),
            'annual_savings': round(solar_energy_savings, 2),
            'carbon_reduction': round(solar_emission_reduction, 2),
            'payback_years': round(solar_investment / solar_energy_savings, 1) if solar_energy_savings > 0 else 0,
            'roi_percent': round(solar_roi, 1),
            'priority': 'High' if solar_roi > 15 else 'Medium',
            'description': f'Install {system_size_kw:.1f} kW solar PV to offset {solar_kwh:.0f} kWh/month'
        })
    
    # Scenario 2: EV Fleet Transition - based on diesel/petrol usage
    vehicle_fuel_cost = (data['diesel'] * ENERGY_COSTS['diesel']) + (data['petrol'] * ENERGY_COSTS['petrol'])
    if data['diesel'] > 1000 or data['petrol'] > 500:
        ev_transition_pct = 30  # 30% of fleet
        ev_fuel_savings = vehicle_fuel_cost * ev_transition_pct / 100 * 0.6  # 60% cheaper electricity
        ev_emission_reduction = ((data['diesel'] * FACTORS['diesel']) + (data['petrol'] * FACTORS['petrol'])) * ev_transition_pct / 100
        
        # Assume 5 vehicles per 5000 litres diesel equivalent
        vehicles_to_replace = max(1, int((data['diesel'] + data['petrol']) / 1000))
        ev_investment = vehicles_to_replace * 1500000  # INR 15L per EV
        
        ev_roi = (ev_fuel_savings * 100 / ev_investment) if ev_investment > 0 else 0
        
        scenarios.append({
            'name': f'EV Fleet ({ev_transition_pct}% transition)',
            'investment': round(ev_investment, 2),
            'annual_savings': round(ev_fuel_savings, 2),
            'carbon_reduction': round(ev_emission_reduction, 2),
            'payback_years': round(ev_investment / ev_fuel_savings, 1) if ev_fuel_savings > 0 else 0,
            'roi_percent': round(ev_roi, 1),
            'priority': 'High' if ev_roi > 12 else 'Medium',
            'description': f'Replace {vehicles_to_replace} vehicles with EVs, save {ev_fuel_savings:.0f} INR/year'
        })
    
    # Scenario 3: Energy Efficiency (LED + Smart HVAC) - based on electricity
    if data['electricity'] > 0:
        efficiency_savings_pct = 15  # 15% reduction
        kwh_saved = data['electricity'] * efficiency_savings_pct / 100
        efficiency_emission_reduction = kwh_saved * FACTORS['electricity']
        efficiency_cost_savings = kwh_saved * ENERGY_COSTS['electricity']
        
        # Investment: ~INR 0.5 per kWh of consumption
        efficiency_investment = data['electricity'] * 0.5
        
        efficiency_roi = (efficiency_cost_savings * 100 / efficiency_investment) if efficiency_investment > 0 else 0
        
        scenarios.append({
            'name': f'Energy Efficiency ({efficiency_savings_pct}% reduction)',
            'investment': round(efficiency_investment, 2),
            'annual_savings': round(efficiency_cost_savings, 2),
            'carbon_reduction': round(efficiency_emission_reduction, 2),
            'payback_years': round(efficiency_investment / efficiency_cost_savings, 1) if efficiency_cost_savings > 0 else 0,
            'roi_percent': round(efficiency_roi, 1),
            'priority': 'High' if efficiency_roi > 20 else 'Medium',
            'description': f'LED lighting, smart HVAC to save {kwh_saved:.0f} kWh/month'
        })
    
    # Scenario 4: Waste Reduction & Recycling - based on waste data
    if data['waste_landfill'] > 0:
        waste_reduction_pct = 50  # 50% diversion from landfill
        waste_diverted = data['waste_landfill'] * waste_reduction_pct / 100
        waste_emission_reduction = waste_diverted * (FACTORS['waste_landfill'] - FACTORS['waste_recycled'])
        waste_cost_savings = waste_diverted * 2000  # INR 2000 per tonne diverted
        
        # Investment in recycling infrastructure
        waste_investment = 300000 + (data['waste_landfill'] * 10000)  # base + variable
        
        waste_roi = (waste_cost_savings * 100 / waste_investment) if waste_investment > 0 else 0
        
        scenarios.append({
            'name': f'Waste Diversion ({waste_reduction_pct}% to recycling)',
            'investment': round(waste_investment, 2),
            'annual_savings': round(waste_cost_savings, 2),
            'carbon_reduction': round(waste_emission_reduction, 2),
            'payback_years': round(waste_investment / waste_cost_savings, 1) if waste_cost_savings > 0 else 0,
            'roi_percent': round(waste_roi, 1),
            'priority': 'Medium',
            'description': f'Divert {waste_diverted:.1f} tonnes from landfill to recycling'
        })
    
    # Scenario 5: Renewable Energy Procurement - based on current renewable %
    if data['renewable'] < 50:
        target_renewable = min(50, data['renewable'] + 30)  # +30% or up to 50%
        additional_renewable_pct = target_renewable - data['renewable']
        additional_renewable_kwh = data['electricity'] * additional_renewable_pct / 100
        renewable_emission_reduction = additional_renewable_kwh * FACTORS['electricity']
        
        # Green premium: ~INR 1-2 per kWh extra
        green_premium = additional_renewable_kwh * 12 * 1.5  # monthly * 12 months * INR 1.5/kWh premium
        # But saves carbon cost
        renewable_carbon_savings = renewable_emission_reduction * CARBON_PRICE
        net_renewable_savings = renewable_carbon_savings - green_premium
        
        renewable_investment = 0  # No upfront, just premium
        
        scenarios.append({
            'name': f'Green Energy Procurement ({target_renewable:.0f}% renewable)',
            'investment': 0,
            'annual_savings': round(net_renewable_savings, 2),
            'carbon_reduction': round(renewable_emission_reduction, 2),
            'payback_years': 0,
            'roi_percent': 999 if net_renewable_savings > 0 else 0,  # Immediate if profitable
            'priority': 'High' if net_renewable_savings > 0 else 'Low',
            'description': f'Switch to green tariffs, increase renewable from {data["renewable"]:.0f}% to {target_renewable:.0f}%'
        })
    
    # Scenario 6: Material Efficiency - based on raw materials
    if scope3['Raw Materials'] > 10:  # Only if significant material emissions
        material_efficiency_pct = 10  # 10% material reduction through efficiency
        material_emission_reduction = scope3['Raw Materials'] * material_efficiency_pct / 100
        material_cost_savings = material_emission_reduction * 50000  # rough material cost
        
        # Investment in process optimization
        material_investment = 500000
        
        material_roi = (material_cost_savings * 100 / material_investment) if material_investment > 0 else 0
        
        scenarios.append({
            'name': f'Material Efficiency ({material_efficiency_pct}% reduction)',
            'investment': round(material_investment, 2),
            'annual_savings': round(material_cost_savings, 2),
            'carbon_reduction': round(material_emission_reduction, 2),
            'payback_years': round(material_investment / material_cost_savings, 1) if material_cost_savings > 0 else 0,
            'roi_percent': round(material_roi, 1),
            'priority': 'Medium',
            'description': f'Optimize material use, reduce waste in production processes'
        })
    
    # Calculate combined scenario
    total_investment = sum(s['investment'] for s in scenarios if s['investment'] > 0)
    total_savings = sum(s['annual_savings'] for s in scenarios)
    total_carbon_reduction = sum(s['carbon_reduction'] for s in scenarios)
    
    scenarios.append({
        'name': 'Combined Optimization (All Measures)',
        'investment': round(total_investment, 2),
        'annual_savings': round(total_savings, 2),
        'carbon_reduction': round(total_carbon_reduction, 2),
        'payback_years': round(total_investment / total_savings, 1) if total_savings > 0 else 0,
        'roi_percent': round((total_savings * 100 / total_investment), 1) if total_investment > 0 else 0,
        'priority': 'Recommended',
        'is_combined': True,
        'description': f'Implement all measures for maximum impact'
    })
    
    # Sort by ROI (highest first), but keep combined at end
    scenarios.sort(key=lambda x: (x.get('is_combined', False), -x['roi_percent']))
    
    return scenarios

@app.route('/', methods=['GET', 'POST'])
def index():
    result = None
    
    if request.method == 'POST':
        # Get all inputs with safe conversion
        data = {
            'diesel': safe_float(request.form.get('diesel'), 0),
            'petrol': safe_float(request.form.get('petrol'), 0),
            'natural_gas': safe_float(request.form.get('natural_gas'), 0),
            'coal': safe_float(request.form.get('coal'), 0),
            'lpg': safe_float(request.form.get('lpg'), 0),
            'electricity': safe_float(request.form.get('electricity'), 0),
            'renewable': safe_float(request.form.get('renewable'), 0),
            'refrigerant_r22': safe_float(request.form.get('refrigerant_r22'), 0),
            'refrigerant_r410a': safe_float(request.form.get('refrigerant_r410a'), 0),
            'refrigerant_r134a': safe_float(request.form.get('refrigerant_r134a'), 0),
            'steel': safe_float(request.form.get('steel'), 0),
            'cement': safe_float(request.form.get('cement'), 0),
            'aluminum': safe_float(request.form.get('aluminum'), 0),
            'plastic': safe_float(request.form.get('plastic'), 0),
            'paper': safe_float(request.form.get('paper'), 0),
            'glass': safe_float(request.form.get('glass'), 0),
            'logistics_truck': safe_float(request.form.get('logistics_truck'), 0),
            'logistics_ship': safe_float(request.form.get('logistics_ship'), 0),
            'logistics_air': safe_float(request.form.get('logistics_air'), 0),
            'waste_landfill': safe_float(request.form.get('waste_landfill'), 0),
            'waste_recycled': safe_float(request.form.get('waste_recycled'), 0),
            'production': safe_float(request.form.get('production'), 1)
        }
        
        # Calculate Scope 1
        scope1 = {
            'Diesel': data['diesel'] * FACTORS['diesel'],
            'Petrol': data['petrol'] * FACTORS['petrol'],
            'Natural Gas': data['natural_gas'] * FACTORS['natural_gas'],
            'Coal': data['coal'] * FACTORS['coal'],
            'LPG': data['lpg'] * FACTORS['lpg'],
            'Refrigerants': (data['refrigerant_r22'] * FACTORS['refrigerant_r22'] + 
                           data['refrigerant_r410a'] * FACTORS['refrigerant_r410a'] + 
                           data['refrigerant_r134a'] * FACTORS['refrigerant_r134a'])
        }
        scope1_total = sum(scope1.values())
        
        # Calculate Scope 2
        grid_electricity = data['electricity'] * (1 - data['renewable']/100)
        scope2 = {'Grid Electricity': grid_electricity * FACTORS['electricity'], 'Renewable': 0}
        scope2_total = scope2['Grid Electricity']
        
        # Calculate Scope 3
        scope3 = {
            'Raw Materials': (data['steel'] * FACTORS['steel'] + data['cement'] * FACTORS['cement'] + 
                            data['aluminum'] * FACTORS['aluminum'] + data['plastic'] * FACTORS['plastic'] + 
                            data['paper'] * FACTORS['paper'] + data['glass'] * FACTORS['glass']),
            'Logistics': (data['logistics_truck'] * FACTORS['logistics_truck'] + 
                         data['logistics_ship'] * FACTORS['logistics_ship'] + 
                         data['logistics_air'] * FACTORS['logistics_air']),
            'Waste': (data['waste_landfill'] * FACTORS['waste_landfill'] + 
                     data['waste_recycled'] * FACTORS['waste_recycled'])
        }
        scope3_total = sum(scope3.values())
        
        total = scope1_total + scope2_total + scope3_total
        
        # By source for charts
        by_source = {}
        by_source.update({k: round(v, 2) for k, v in scope1.items() if v > 0})
        by_source.update({k: round(v, 2) for k, v in scope2.items() if v > 0})
        by_source.update({k: round(v, 2) for k, v in scope3.items() if v > 0})
        
        # Calculate carbon costs for chart
        carbon_costs_by_source = {k: round(v * CARBON_PRICE, 2) for k, v in by_source.items()}
        
        # Calculate dynamic scenarios based on input data
        scenarios = calculate_scenarios(data, scope1, scope2, scope3, total)
        
        # Intensity
        intensity = total / data['production'] if data['production'] > 0 else 0
        
        # Cost analysis
        carbon_cost = total * CARBON_PRICE
        
        # Calculate 10-year projection
        combined_scenario = [s for s in scenarios if s.get('is_combined')][0]
        ten_year_savings = combined_scenario['annual_savings'] * 10
        ten_year_reduction = combined_scenario['carbon_reduction'] * 10
        
        # Hotspots
        hotspots = sorted([{'source': k, 'emission': v, 'percent': (v/total*100)} for k, v in by_source.items()], 
                         key=lambda x: x['emission'], reverse=True)[:5]
        
        result = {
            'scope1': round(scope1_total, 2),
            'scope2': round(scope2_total, 2),
            'scope3': round(scope3_total, 2),
            'total': round(total, 2),
            'intensity': round(intensity, 4),
            'renewable': data['renewable'],
            'production': data['production'],
            'by_scope': [round(scope1_total, 2), round(scope2_total, 2), round(scope3_total, 2)],
            'by_source': by_source,
            'carbon_costs_by_source': carbon_costs_by_source,
            'carbon_cost': round(carbon_cost, 2),
            'scenarios': scenarios,
            'ten_year_savings': round(ten_year_savings, 2),
            'ten_year_reduction': round(ten_year_reduction, 2),
            'hotspots': hotspots
        }
    
    return render_template('index.html', result=result)

if __name__ == '__main__':
    app.run(debug=True, port=3000)