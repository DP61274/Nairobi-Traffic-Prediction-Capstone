import datetime
import os

import folium
import joblib
import pandas as pd
import polyline
import requests
from django.conf import settings
from dotenv import load_dotenv


load_dotenv()

MODEL_PATH = os.path.join(settings.BASE_DIR, 'traffic_model.pkl')
SCALER_PATH = os.path.join(settings.BASE_DIR, 'scaler.pkl')

try:
    model = joblib.load(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)
except Exception as e:
    print(f"Model Loading Error: {e}")
    model = None
    scaler = None

GOOGLE_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY', '')
OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY', '')

LABELS = {0: 'Clear', 1: 'Moderate', 2: 'Heavy', 3: 'Severe'}
COLORS = {0: '#10b981', 1: '#f59e0b', 2: '#f97316', 3: '#ef4444'}
WEATHER_OPTIONS = {
    '0.0': 'Dry/Sunny',
    '5.0': 'Light Rain',
    '15.0': 'Heavy Downpour',
}


def get_smart_advice(prediction):
    if prediction == 'Clear':
        return "Roads are exceptionally clear. It's a great time to hit the road and enjoy a smooth drive!"
    if prediction == 'Moderate':
        return "Standard traffic volume. You'll hit a few slow patches, but nothing out of the ordinary for Nairobi."
    if prediction == 'Heavy':
        return "Significant slowdowns detected. Leave early or look at the alternative routes on the map."
    return "Severe gridlock. Avoid this route right now if possible, or consider the Expressway to bypass the worst delays."


def _as_bool(value):
    return value is True or str(value).lower() in ['1', 'true', 'yes', 'on']


def geocode_location(location_text):
    query = (location_text or '').strip()
    if not query:
        raise ValueError("Please enter a location.")

    geocode_url = "https://maps.googleapis.com/maps/api/geocode/json"
    try:
        response = requests.get(geocode_url, params={
            'address': query,
            'components': 'country:KE',
            'key': GOOGLE_API_KEY,
        }, timeout=5).json()
    except Exception:
        raise ValueError("I could not reach the location service. Please try again.")

    if response.get('status') != 'OK' or not response.get('results'):
        raise ValueError("I couldn't find that location. Please try another landmark or area.")

    result = response['results'][0]
    location = result['geometry']['location']
    return {
        'label': result.get('formatted_address', query),
        'lat': float(location['lat']),
        'lon': float(location['lng']),
    }


def normalize_location(location):
    if not location:
        raise ValueError("Please provide a location.")

    if isinstance(location, str):
        return geocode_location(location)

    if location.get('lat') is not None and location.get('lon') is not None:
        return {
            'label': location.get('label') or location.get('text') or 'Selected location',
            'lat': float(location['lat']),
            'lon': float(location['lon']),
        }

    return geocode_location(location.get('text') or location.get('label'))


def _get_weather(from_lat, from_lon):
    temp_c = 22.0
    rain_mm = 0.0

    if OPENWEATHER_API_KEY:
        weather_url = (
            "https://api.openweathermap.org/data/2.5/weather"
            f"?lat={from_lat}&lon={from_lon}&appid={OPENWEATHER_API_KEY}&units=metric"
        )
        try:
            w_res = requests.get(weather_url, timeout=3).json()
            temp_c = w_res.get('main', {}).get('temp', 22.0)
            rain_mm = w_res.get('rain', {}).get('1h', 0.0)
        except Exception:
            pass

    return temp_c, rain_mm


def _get_matatu_stop_count(to_lat, to_lon):
    matatu_stop_count = 5
    places_url = (
        "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        f"?location={to_lat},{to_lon}&radius=2000&type=transit_station&key={GOOGLE_API_KEY}"
    )

    try:
        p_res = requests.get(places_url, timeout=3).json()
        if p_res.get('status') == 'OK':
            found_stops = len(p_res.get('results', []))
            if found_stops > 0:
                matatu_stop_count = found_stops
    except Exception:
        pass

    return matatu_stop_count


def _get_route_response(from_lat, from_lon, to_lat, to_lon, timing_mode, avoid_expressway):
    directions_url = (
        "https://maps.googleapis.com/maps/api/directions/json"
        f"?origin={from_lat},{from_lon}&destination={to_lat},{to_lon}&alternatives=true&key={GOOGLE_API_KEY}"
    )

    if avoid_expressway:
        directions_url += "&avoid=tolls"

    if timing_mode == 'now':
        directions_url += "&departure_time=now"

    try:
        return requests.get(directions_url, timeout=5).json()
    except Exception:
        return {}


def _get_eta(route_response, fallback="Calculating..."):
    if route_response.get('status') != 'OK':
        return fallback

    leg = route_response['routes'][0]['legs'][0]
    return leg.get('duration_in_traffic', leg.get('duration', {})).get('text', fallback)


def _build_map(from_lat, from_lon, to_lat, to_lon, prediction_text, line_color, eta_text, route_response):
    m = folium.Map(
        location=[(from_lat + to_lat) / 2, (from_lon + to_lon) / 2],
        zoom_start=13,
        zoom_control=False,
        tiles=None,
    )

    folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=m@221097413,traffic&x={x}&y={y}&z={z}',
        attr='Google Maps Live Traffic',
        name='Google Traffic',
        overlay=False,
        control=True,
    ).add_to(m)

    if route_response.get('status') == 'OK':
        routes = route_response['routes']
        primary_route = routes[0]
        eta_text = _get_eta(route_response, eta_text)

        if len(routes) > 1:
            for alt_route in routes[1:]:
                alt_coords = polyline.decode(alt_route['overview_polyline']['points'])
                folium.PolyLine(
                    alt_coords,
                    color='#64748b',
                    weight=5,
                    opacity=0.6,
                    dash_array='10',
                    tooltip="Alternative Route",
                ).add_to(m)

        main_coords = polyline.decode(primary_route['overview_polyline']['points'])
        folium.PolyLine(
            main_coords,
            color=line_color,
            weight=8,
            opacity=0.9,
            tooltip=f"Predicted Flow: {prediction_text} ({eta_text})",
        ).add_to(m)

        folium.Marker([from_lat, from_lon], popup="Start", icon=folium.Icon(color='darkblue', icon='circle')).add_to(m)
        folium.Marker([to_lat, to_lon], popup="Destination", icon=folium.Icon(color='red', icon='flag')).add_to(m)
        m.fit_bounds([
            [min(p[0] for p in main_coords), min(p[1] for p in main_coords)],
            [max(p[0] for p in main_coords), max(p[1] for p in main_coords)],
        ])
    else:
        folium.PolyLine([(from_lat, from_lon), (to_lat, to_lon)], color=line_color, weight=5).add_to(m)

    return m.get_root().render(), eta_text


def predict_route(params, include_map=True):
    if model is None or scaler is None:
        raise RuntimeError("Traffic model is not available.")

    from_lat = float(params.get('from_lat', -1.279))
    from_lon = float(params.get('from_lon', 36.817))
    to_lat = float(params['to_lat'])
    to_lon = float(params['to_lon'])
    school_impact = 1 if _as_bool(params.get('school_impact')) else 0
    avoid_expressway = _as_bool(params.get('avoid_expressway'))
    timing_mode = params.get('timing_mode', 'now')

    if timing_mode == 'now':
        now = datetime.datetime.now()
        hour = now.hour
        day = now.weekday()
        temp_c, rain_mm = _get_weather(from_lat, from_lon)
    else:
        hour = int(params.get('hour', 8))
        day = int(params.get('day', 0))
        rain_mm = float(params.get('rain', 0.0))
        temp_c = 22.0

    matatu_stop_count = _get_matatu_stop_count(to_lat, to_lon)
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
        'avg_temp_c': temp_c,
    }

    input_df = pd.DataFrame([data])
    scaled_data = scaler.transform(input_df)
    scaled_df = pd.DataFrame(scaled_data, columns=input_df.columns)

    prediction_num = model.predict(scaled_df)[0]
    probabilities = model.predict_proba(scaled_df)[0]
    confidence_score = max(probabilities) * 100
    prediction_text = LABELS.get(prediction_num, 'Unknown')
    line_color = COLORS.get(prediction_num, '#3b82f6')

    eta_text = "Calculating..."
    route_response = _get_route_response(from_lat, from_lon, to_lat, to_lon, timing_mode, avoid_expressway)
    eta_text = _get_eta(route_response, eta_text)

    map_html = ""
    if include_map:
        map_html, eta_text = _build_map(
            from_lat,
            from_lon,
            to_lat,
            to_lon,
            prediction_text,
            line_color,
            eta_text,
            route_response,
        )

    return {
        'prediction': prediction_text,
        'confidence': round(confidence_score, 1),
        'eta': eta_text,
        'map_html': map_html,
        'google_key': GOOGLE_API_KEY,
        'advice': get_smart_advice(prediction_text),
    }
