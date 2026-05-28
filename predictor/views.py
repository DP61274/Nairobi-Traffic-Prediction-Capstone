import os
import joblib
import pandas as pd
import folium
import requests
import polyline
import datetime
import africastalking
from dotenv import load_dotenv
from django.shortcuts import render
from django.conf import settings

# 1. LOAD Environment Variables
load_dotenv()

# Africa's Talking setup
AT_USERNAME = os.getenv('AT_USERNAME', 'sandbox')
AT_API_KEY = os.getenv('AT_API_KEY', '')

def send_traffic_sms(phone, name, route_name, windows):
    try:
        import requests as req
        
        best = next((w for w in windows if w['level'] == 0), None)
        worst = [w for w in windows if w['level'] >= 2]
        
        message = f"Hi {name}! 🚦 SmartTraffic AI Update\n"
        message += f"Route: {route_name}\n"
        if best:
            message += f"✅ Best time: {best['range']}\n"
        if worst:
            message += f"🔴 Avoid: {worst[0]['range']} ({worst[0]['label']})\n"
        message += "Powered by Nairobi SmartTraffic AI"

        response = req.post(
            'https://api.sandbox.africastalking.com/version1/messaging',
            headers={
                'Accept': 'application/json',
                'apiKey': AT_API_KEY,
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            data={
                'username': AT_USERNAME,
                'to': phone,
                'message': message
            },
            verify=False  # bypasses SSL issue on Windows
        )
        print(f"SMS Response: {response.text}")
        return True
    except Exception as e:
        print(f"SMS Error: {e}")
        return False

def subscribe(request):
    from .models import Subscriber
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        phone = request.POST.get('phone', '').strip()
        route = request.POST.get('route', '').strip()
        
        if name and phone and route:
            # Save subscriber
            sub, created = Subscriber.objects.get_or_create(
                phone=phone,
                defaults={'name': name, 'route': route}
            )
            
            # Route coordinates for prediction
            route_coords = {
                'thika':   {'to_lat': -1.0332, 'to_lon': 37.0693, 'name': 'Thika Road'},
                'mombasa': {'to_lat': -1.3192, 'to_lon': 36.8275, 'name': 'Mombasa Road'},
                'waiyaki': {'to_lat': -1.2676, 'to_lon': 36.7615, 'name': 'Waiyaki Way'},
                'ngong':   {'to_lat': -1.3548, 'to_lon': 36.7517, 'name': 'Ngong Road'},
                'langata': {'to_lat': -1.3317, 'to_lon': 36.7477, 'name': "Lang'ata Road"},
            }
            
            coords = route_coords.get(route, route_coords['thika'])
            now = datetime.datetime.now()
            
            # Generate windows for their route
            windows = get_departure_windows(
                -1.279, 36.817,
                coords['to_lat'], coords['to_lon'],
                now.weekday(), 0, 0.0, 22.0, 5,
                current_hour=now.hour
            )
            
            print(f"Using key: {AT_API_KEY[:20]}...")
            # Send welcome SMS immediately
            send_traffic_sms(phone, name, coords['name'], windows)
            
            return render(request, 'predictor/index.html', {
                'google_key': GOOGLE_API_KEY,
                'success': f"✅ Subscribed! Check your phone {phone} for your first traffic update."
            })
    
    return render(request, 'predictor/index.html', {'google_key': GOOGLE_API_KEY})

# 2. LOAD trained model and scaler
MODEL_PATH = os.path.join(settings.BASE_DIR, 'traffic_model.pkl')
SCALER_PATH = os.path.join(settings.BASE_DIR, 'scaler.pkl')

try:
    model = joblib.load(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)
except Exception as e:
    print(f"⚠️ Model Loading Error: {e}")

# 3. API KEYS
GOOGLE_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY', '')
OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY', '')

def get_departure_windows(from_lat, from_lon, to_lat, to_lon, day, school_impact, rain_mm, temp_c, matatu_stop_count, current_hour):
    windows = []
    labels = {0: 'Clear', 1: 'Moderate', 2: 'Heavy', 3: 'Severe'}
    icons = {0: '✅', 1: '⚠️', 2: '🔴', 3: '🚨'}
    
    check_hours = [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
    
    for h in check_hours:
        is_weekend = 1 if day >= 5 else 0
        is_peak = 1 if h in [7, 8, 9, 16, 17, 18, 19] else 0
        data = {
            'from_lat': from_lat, 'from_lon': from_lon,
            'to_lat': to_lat, 'to_lon': to_lon,
            'matatu_stop_count': matatu_stop_count,
            'is_inbound': 1, 'hour': h,
            'day_of_week_enc': day,
            'is_weekend': is_weekend,
            'is_peak_hour': is_peak,
            'school_impact': school_impact,
            'avg_rain_mm': rain_mm,
            'avg_temp_c': temp_c
        }
        input_df = pd.DataFrame([data])
        scaled = pd.DataFrame(scaler.transform(input_df), columns=input_df.columns)
        pred = model.predict(scaled)[0]
        windows.append({
            'hour': h,
            'label': labels[pred],
            'icon': icons[pred],
            'level': int(pred)
        })
    
    # Group consecutive same-level hours into ranges
    grouped = []
    i = 0
    while i < len(windows):
        start = windows[i]['hour']
        level = windows[i]['level']
        label = windows[i]['label']
        icon = windows[i]['icon']
        j = i
        while j < len(windows) and windows[j]['level'] == level:
            j += 1
        end = windows[j-1]['hour'] + 1
        grouped.append({
            'range': f"{start}:00 - {end}:00",
            'label': label,
            'icon': icon,
            'level': level,
            'is_now': start <= current_hour < end  # ← detects if you are in this window
        })
        i = j
    
    return grouped

def predict_traffic(request):
    if request.method == 'POST':
        try:
            to_lat_raw = request.POST.get('to_lat')
            to_lon_raw = request.POST.get('to_lon')

            if not to_lat_raw or not to_lon_raw:
                return render(request, 'predictor/index.html', {
                    'error': "Missing destination coordinates. Please select a valid location from the dropdown.",
                    'google_key': GOOGLE_API_KEY
                })

            from_lat = float(request.POST.get('from_lat', -1.279))
            from_lon = float(request.POST.get('from_lon', 36.817))
            to_lat = float(to_lat_raw)
            to_lon = float(to_lon_raw)
            
            school_impact = 1 if request.POST.get('school_impact') else 0
            avoid_expressway = True if request.POST.get('avoid_expressway') else False
            timing_mode = request.POST.get('timing_mode', 'now')

            if timing_mode == 'now':
                now = datetime.datetime.now()
                hour = now.hour
                day = now.weekday() 
                temp_c = 22.0 
                rain_mm = 0.0 
                
                if OPENWEATHER_API_KEY:
                    weather_url = f"https://api.openweathermap.org/data/2.5/weather?lat={from_lat}&lon={from_lon}&appid={OPENWEATHER_API_KEY}&units=metric"
                    try:
                        w_res = requests.get(weather_url, timeout=3).json()
                        temp_c = w_res.get('main', {}).get('temp', 22.0)
                        rain_dict = w_res.get('rain', {})
                        rain_mm = rain_dict.get('1h', 0.0)
                    except:
                        pass 
            else:
                hour = int(request.POST.get('hour', 8))
                day = int(request.POST.get('day', 0))
                rain_mm = float(request.POST.get('rain', 0.0))
                temp_c = 22.0 

            matatu_stop_count = 5 
            places_url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={to_lat},{to_lon}&radius=2000&type=transit_station&key={GOOGLE_API_KEY}"
            try:
                p_res = requests.get(places_url, timeout=3).json()
                if p_res.get('status') == 'OK':
                    found_stops = len(p_res.get('results', []))
                    if found_stops > 0:
                        matatu_stop_count = found_stops
            except:
                pass

            is_weekend = 1 if day >= 5 else 0
            is_peak_hour = 1 if hour in [7, 8, 9, 16, 17, 18, 19] else 0
            
            data = {
                'from_lat': from_lat,
                'from_lon': from_lon,
                'to_lat': to_lat,
                'to_lon': to_lon,
                'matatu_stop_count': matatu_stop_count, 
                'is_inbound': 1,
                'hour': hour,
                'day_of_week_enc': day,
                'is_weekend': is_weekend,
                'is_peak_hour': is_peak_hour,
                'school_impact': school_impact, 
                'avg_rain_mm': rain_mm,         
                'avg_temp_c': temp_c            
            }

            # --- AI PREDICTION LOGIC ---
            input_df = pd.DataFrame([data])
            scaled_data = scaler.transform(input_df)
            
            # (Fixing the Scikit-Learn Warning for Render)
            scaled_df = pd.DataFrame(scaled_data, columns=input_df.columns)
            
            prediction_num = model.predict(scaled_df)[0]
            probabilities = model.predict_proba(scaled_df)[0]
            confidence_score = max(probabilities) * 100 

            labels = {0: 'Clear', 1: 'Moderate', 2: 'Heavy', 3: 'Severe'}
            colors = {0: '#10b981', 1: '#f59e0b', 2: '#f97316', 3: '#ef4444'} 
            
            prediction_text = labels.get(prediction_num, 'Unknown')
            line_color = colors.get(prediction_num, '#3b82f6')

            # --- MAPPING (Folium Setup) ---
            m = folium.Map(location=[(from_lat + to_lat)/2, (from_lon + to_lon)/2], zoom_start=13, zoom_control=False, tiles=None)
            
            # THE NEW FIX: Inject Google Maps with Live Traffic Lines baked in!
            # This replaces the OpenStreetMap code entirely.
            folium.TileLayer(
                tiles='https://mt1.google.com/vt/lyrs=m@221097413,traffic&x={x}&y={y}&z={z}',
                attr='Google Maps Live Traffic',
                name='Google Traffic',
                overlay=False,
                control=True
            ).add_to(m)

            # --- GOOGLE DIRECTIONS (Live ETA & Alternative Routes) ---
            directions_url = f"https://maps.googleapis.com/maps/api/directions/json?origin={from_lat},{from_lon}&destination={to_lat},{to_lon}&alternatives=true&key={GOOGLE_API_KEY}"
            
            if avoid_expressway:
                directions_url += "&avoid=tolls"
                
            # LIVE ACCIDENT/TRAFFIC FACTOR:
            if timing_mode == 'now':
                directions_url += "&departure_time=now"

            route_response = requests.get(directions_url).json()
            
            eta_text = "Calculating..."

            if route_response.get('status') == 'OK':
                routes = route_response['routes']
                primary_route = routes[0]
                
                # Extract the Live ETA
                leg = primary_route['legs'][0]
                if 'duration_in_traffic' in leg:
                    eta_text = leg['duration_in_traffic']['text'] # Live with accidents
                else:
                    eta_text = leg['duration']['text'] # Standard historic ETA
                
                # 1. DRAW ALTERNATIVE ROUTES FIRST (Underneath)
                if len(routes) > 1:
                    for alt_route in routes[1:]:
                        alt_coords = polyline.decode(alt_route['overview_polyline']['points'])
                        folium.PolyLine(
                            alt_coords,
                            color='#64748b', # Faded Grey
                            weight=5,
                            opacity=0.6,
                            dash_array='10', # Dashed line style
                            tooltip="Alternative Route"
                        ).add_to(m)

                # 2. DRAW PRIMARY ROUTE (On Top)
                main_coords = polyline.decode(primary_route['overview_polyline']['points'])
                folium.PolyLine(
                    main_coords,
                    color=line_color,
                    weight=8,
                    opacity=0.9,
                    tooltip=f"Predicted Flow: {prediction_text} ({eta_text})"
                ).add_to(m)
                
                folium.Marker([from_lat, from_lon], popup="Start", icon=folium.Icon(color='darkblue', icon='circle')).add_to(m)
                folium.Marker([to_lat, to_lon], popup="Destination", icon=folium.Icon(color='red', icon='flag')).add_to(m)
                
                m.fit_bounds([ [min(p[0] for p in main_coords), min(p[1] for p in main_coords)], 
                               [max(p[0] for p in main_coords), max(p[1] for p in main_coords)] ])
            else:
                folium.PolyLine([(from_lat, from_lon), (to_lat, to_lon)], color=line_color, weight=5).add_to(m)

            map_html = m.get_root().render()

            departure_windows = get_departure_windows(
                from_lat, from_lon, to_lat, to_lon,
                day, school_impact, rain_mm, temp_c, matatu_stop_count,
                current_hour=datetime.datetime.now().hour if timing_mode == 'now' else hour
            )

            # --- RENDER RESULTS ---
            return render(request, 'predictor/result.html', {
                'prediction': prediction_text,
                'confidence': round(confidence_score, 1),
                'eta': eta_text,
                'map_html': map_html,
                'google_key': GOOGLE_API_KEY,
                'departure_windows': departure_windows,  # ADD THIS
                'current_hour': datetime.datetime.now().hour if timing_mode == 'now' else hour,  # ADD THIS
            })

        except Exception as e:
            return render(request, 'predictor/index.html', {
                'error': f"Prediction failed: {str(e)}",
                'google_key': GOOGLE_API_KEY
            })

    return render(request, 'predictor/index.html', {'google_key': GOOGLE_API_KEY})