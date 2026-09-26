import io
import os
from datetime import date, datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

app = Flask(__name__)
CORS(app)

DEFAULT_MANDI = os.getenv('DEFAULT_MANDI', 'Dhamnod')
DEFAULT_LOCATION = os.getenv('DEFAULT_LOCATION', 'Khalghat, Madhya Pradesh, India')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-3.8-flash')


def supabase_client():
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_KEY')
    if not url or not key:
        return None
    from supabase import create_client
    return create_client(url, key)


def gemini_client():
    key = os.getenv('GEMINI_API_KEY')
    if not key:
        return None
    from google import genai
    return genai.Client(api_key=key)


def crop_age_days(sowing_date):
    sow = datetime.strptime(sowing_date, '%Y-%m-%d').date()
    return max((date.today() - sow).days, 0)


def geocode_location(location):
    r = requests.get(
        'https://geocoding-api.open-meteo.com/v1/search',
        params={'name': location, 'count': 1, 'language': 'en', 'format': 'json'},
        timeout=12,
    )
    r.raise_for_status()
    rows = r.json().get('results') or []
    if not rows:
        raise ValueError('Location not found')
    return rows[0]['latitude'], rows[0]['longitude'], rows[0].get('name', location)


@app.get('/api/health')
def health():
    return jsonify({'success': True, 'service': 'JaiKisaan AI'})


@app.get('/api/weather')
def weather():
    location = request.args.get('location', DEFAULT_LOCATION)
    try:
        lat, lon, resolved = geocode_location(location)
        r = requests.get(
            'https://api.open-meteo.com/v1/forecast',
            params={
                'latitude': lat,
                'longitude': lon,
                'current': 'temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m',
                'daily': 'precipitation_probability_max,temperature_2m_max,temperature_2m_min',
                'forecast_days': 3,
                'timezone': 'auto',
            },
            timeout=12,
        )
        r.raise_for_status()
        data = r.json()
        current = data.get('current', {})
        daily = data.get('daily', {})
        return jsonify({
            'success': True,
            'location': resolved,
            'current': current,
            'daily': daily,
        })
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 502


@app.get('/api/mandi')
def mandi():
    market = request.args.get('location', DEFAULT_MANDI)
    api_url = os.getenv('DATA_GOV_API_URL')
    api_key = os.getenv('DATA_GOV_API_KEY')
    if not api_url:
        return jsonify({
            'success': False,
            'market': market,
            'records': [],
            'notice': None,
            'error': 'Official mandi API is not configured yet.'
        }), 503

    try:
        params = {'format': 'json', 'limit': 100}
        if api_key:
            params['api-key'] = api_key
        params['filters[market]'] = market
        r = requests.get(api_url, params=params, timeout=15)
        r.raise_for_status()
        payload = r.json()
        records = payload.get('records') or payload.get('data') or []
        cleaned = []
        for row in records:
            cleaned.append({
                'commodity': row.get('commodity') or row.get('Commodity'),
                'variety': row.get('variety') or row.get('Variety'),
                'min_price': row.get('min_price') or row.get('Min_x0020_Price') or row.get('minimum_price'),
                'max_price': row.get('max_price') or row.get('Max_x0020_Price') or row.get('maximum_price'),
                'modal_price': row.get('modal_price') or row.get('Modal_x0020_Price') or row.get('model_price'),
                'date': row.get('arrival_date') or row.get('Arrival_Date') or row.get('date'),
            })
        return jsonify({'success': True, 'market': market, 'records': cleaned, 'notice': None})
    except Exception as exc:
        return jsonify({'success': False, 'market': market, 'records': [], 'notice': None, 'error': str(exc)}), 502


@app.post('/api/register')
def register():
    body = request.get_json(force=True)
    mobile = ''.join(ch for ch in str(body.get('mobile', '')) if ch.isdigit())
    if len(mobile) < 10:
        return jsonify({'success': False, 'error': 'Valid mobile number required'}), 400
    sb = supabase_client()
    if not sb:
        return jsonify({'success': False, 'error': 'Supabase not configured'}), 503
    try:
        existing = sb.table('farmers').select('*').eq('mobile', mobile).execute().data
        if existing:
            farmer = existing[0]
        else:
            farmer = sb.table('farmers').insert({
                'mobile': mobile,
                'name': body.get('name'),
                'village': body.get('village') or 'Khalghat',
            }).execute().data[0]
        return jsonify({'success': True, 'farmer': farmer})
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.post('/api/fields')
def add_field():
    body = request.get_json(force=True)
    sb = supabase_client()
    if not sb:
        return jsonify({'success': False, 'error': 'Supabase not configured'}), 503
    try:
        field = sb.table('fields').insert({
            'farmer_id': body['farmer_id'],
            'name': body['name'],
            'area_bigha': body['area_bigha'],
            'soil_type': body.get('soil_type') or 'Heavy Black Soil',
        }).execute().data[0]
        return jsonify({'success': True, 'field': field})
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400


@app.post('/api/crops')
def add_crop():
    body = request.get_json(force=True)
    sb = supabase_client()
    if not sb:
        return jsonify({'success': False, 'error': 'Supabase not configured'}), 503
    try:
        current = sb.table('crop_cycles').select('id').eq('field_id', body['field_id']).eq('status', 'active').execute().data
        if current:
            return jsonify({'success': False, 'error': 'Is khet me ek active crop already hai. Pehle harvest/complete karein.'}), 409
        crop = sb.table('crop_cycles').insert({
            'field_id': body['field_id'],
            'crop': body['crop'],
            'variety': body.get('variety'),
            'sowing_date': body['sowing_date'],
        }).execute().data[0]
        return jsonify({'success': True, 'crop': crop, 'age_days': crop_age_days(body['sowing_date'])})
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400


@app.post('/api/crops/<crop_id>/complete')
def complete_crop(crop_id):
    sb = supabase_client()
    if not sb:
        return jsonify({'success': False, 'error': 'Supabase not configured'}), 503
    try:
        rows = sb.table('crop_cycles').update({'status': 'harvested', 'harvested_at': datetime.utcnow().isoformat()}).eq('id', crop_id).execute().data
        return jsonify({'success': True, 'crop': rows[0] if rows else None})
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400


@app.get('/api/farmer/<farmer_id>/dashboard')
def dashboard(farmer_id):
    sb = supabase_client()
    if not sb:
        return jsonify({'success': False, 'error': 'Supabase not configured'}), 503
    try:
        fields = sb.table('fields').select('*').eq('farmer_id', farmer_id).execute().data
        out = []
        for field in fields:
            crops = sb.table('crop_cycles').select('*').eq('field_id', field['id']).order('created_at', desc=True).execute().data
            for c in crops:
                if c['status'] == 'active':
                    c['age_days'] = crop_age_days(c['sowing_date'])
            out.append({'field': field, 'crops': crops})
        return jsonify({'success': True, 'fields': out})
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.post('/api/events')
def add_event():
    body = request.get_json(force=True)
    sb = supabase_client()
    if not sb:
        return jsonify({'success': False, 'error': 'Supabase not configured'}), 503
    try:
        row = sb.table('farm_events').insert({
            'crop_cycle_id': body['crop_cycle_id'],
            'event_type': body['event_type'],
            'event_date': body.get('event_date') or date.today().isoformat(),
            'note': body.get('note'),
        }).execute().data[0]
        return jsonify({'success': True, 'event': row})
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400


def build_context(sb, crop_cycle_id):
    crop = sb.table('crop_cycles').select('*').eq('id', crop_cycle_id).execute().data[0]
    field = sb.table('fields').select('*').eq('id', crop['field_id']).execute().data[0]
    events = sb.table('farm_events').select('*').eq('crop_cycle_id', crop_cycle_id).order('event_date', desc=True).limit(15).execute().data
    return crop, field, events


@app.post('/api/ai/plan')
def ai_plan():
    body = request.get_json(force=True)
    sb = supabase_client()
    client = gemini_client()
    if not sb:
        return jsonify({'success': False, 'error': 'Supabase not configured'}), 503
    if not client:
        return jsonify({'success': False, 'error': 'Gemini API not configured'}), 503
    try:
        crop, field, events = build_context(sb, body['crop_cycle_id'])
        age = crop_age_days(crop['sowing_date'])
        weather_data = body.get('weather') or {}
        prompt = f"""
You are a cautious digital agronomy assistant for a farmer in Khalghat, Madhya Pradesh.
Give a short Hinglish crop-stage plan. Do not invent pesticide/fertilizer brand names or doses when uncertain.
Prefer active ingredient / nutrient and only give a brand example when you are confident it is commonly registered for the stated use; clearly label it as an example and advise label/local expert verification.
Never force a treatment. If crop appears at maturity and no problem is reported, say no routine spray is needed.
Explain WHY each suggested action matters so the farmer remembers it.
If weather makes spray unsuitable, postpone/adjust timing.

Field: {field['name']}, area: {field['area_bigha']} bigha, soil: {field.get('soil_type')}
Crop: {crop['crop']}, variety: {crop.get('variety') or 'not given'}
Sowing date: {crop['sowing_date']}, age: {age} days
Recent farm events: {events}
Weather context: {weather_data}

Return concise JSON only with keys:
stage, risk_level, summary, actions (array of objects: title, product_or_nutrient, dose, timing, reason, caution), questions_to_farmer (array), maturity_status.
"""
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        return jsonify({'success': True, 'raw': response.text, 'age_days': age})
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.post('/api/ai/chat')
def ai_chat():
    body = request.get_json(force=True)
    sb = supabase_client()
    client = gemini_client()
    if not sb:
        return jsonify({'success': False, 'error': 'Supabase not configured'}), 503
    if not client:
        return jsonify({'success': False, 'error': 'Gemini API not configured'}), 503
    question = (body.get('message') or '').strip()
    if not question:
        return jsonify({'success': False, 'error': 'Question required'}), 400
    try:
        crop, field, events = build_context(sb, body['crop_cycle_id'])
        age = crop_age_days(crop['sowing_date'])
        prompt = f"""
You are a cautious agriculture scientist assistant speaking simple Hinglish.
Use the farmer's actual crop context below. Ask follow-up questions when symptoms/details are insufficient.
If recommending a pesticide/fungicide/nutrient, state purpose, active ingredient/nutrient, dose only when confident, timing, and key precautions. Brand can be shown only as an example, never as a guarantee; ask farmer to verify label/local authorized dealer/agriculture expert.
Do not invent a treatment. Do not recommend routine spray only because crop reached a certain day count.

Crop={crop['crop']}; variety={crop.get('variety')}; age={age} days; sowing={crop['sowing_date']}
Field={field['name']}; area={field['area_bigha']} bigha; soil={field.get('soil_type')}
Recent events={events}
Farmer question={question}
"""
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        answer = response.text
        sb.table('ai_chats').insert([
            {'crop_cycle_id': crop['id'], 'farmer_id': field['farmer_id'], 'role': 'user', 'message': question},
            {'crop_cycle_id': crop['id'], 'farmer_id': field['farmer_id'], 'role': 'assistant', 'message': answer},
        ]).execute()
        return jsonify({'success': True, 'answer': answer})
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.post('/api/ai/photo')
def ai_photo():
    sb = supabase_client()
    client = gemini_client()
    if not sb:
        return jsonify({'success': False, 'error': 'Supabase not configured'}), 503
    if not client:
        return jsonify({'success': False, 'error': 'Gemini API not configured'}), 503
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'Photo required'}), 400
    crop_cycle_id = request.form.get('crop_cycle_id')
    if not crop_cycle_id:
        return jsonify({'success': False, 'error': 'crop_cycle_id required'}), 400
    try:
        crop, field, events = build_context(sb, crop_cycle_id)
        age = crop_age_days(crop['sowing_date'])
        img = Image.open(io.BytesIO(request.files['file'].read()))
        prompt = f"""
Analyze this crop photo cautiously. Crop={crop['crop']}, age={age} days, soil={field.get('soil_type')}.
Give Hinglish response: likely issue(s), what visual signs support it, what extra info is needed, immediate low-risk action, and treatment only if reasonably confident. Product brand names are examples only; verify label/local expert. Do not pretend certainty from photo alone.
"""
        response = client.models.generate_content(model=GEMINI_MODEL, contents=[prompt, img])
        return jsonify({'success': True, 'answer': response.text})
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=8000)
