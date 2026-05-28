import re


DAY_VALUES = {
    'MONDAY': '0',
    'TUESDAY': '1',
    'WEDNESDAY': '2',
    'THURSDAY': '3',
    'FRIDAY': '4',
    'SATURDAY': '5',
    'SUNDAY': '6',
}

WEATHER_VALUES = {
    'DRY': '0.0',
    'SUNNY': '0.0',
    'LIGHT': '5.0',
    'LIGHT RAIN': '5.0',
    'HEAVY': '15.0',
    'HEAVY RAIN': '15.0',
}

SMS_ADVICE = {
    'Clear': 'Good time to travel.',
    'Moderate': 'Expect some slow sections.',
    'Heavy': 'Leave early if possible.',
    'Severe': 'Avoid this route if you can.',
}


class SmsParseError(ValueError):
    pass


def onboarding_message():
    return (
        "Nairobi Traffic Predictor\n"
        "Reply with your route:\n"
        "NOW: FROM*TO*NOW\n"
        "e.g. nacico*cbd*now\n"
        "PLAN: FROM*TO*DAY*HOUR*WEATHER\n"
        "e.g. westlands*cbd*MONDAY*8*DRY\n"
        "Extras: *SCHOOL or *TOLL"
    )


def _canonical_token(value):
    return re.sub(r'\s+', ' ', value.strip()).upper()


def _split_sms(text):
    return [part.strip() for part in re.split(r'\*+', text.strip()) if part.strip()]


def _parse_flags(tokens):
    flags = {'school_impact': 0, 'avoid_expressway': 0}
    for token in tokens:
        flag = _canonical_token(token)
        if flag == 'SCHOOL':
            flags['school_impact'] = 1
        elif flag == 'TOLL':
            flags['avoid_expressway'] = 1
        else:
            raise SmsParseError("Invalid flag. Use SCHOOL or TOLL.")
    return flags


def _normalize_hour(value):
    try:
        hour = int(value.strip())
    except ValueError:
        raise SmsParseError("Invalid hour. Use 0-23, e.g. 17.")

    if hour < 0 or hour > 23:
        raise SmsParseError("Invalid hour. Use 0-23, e.g. 17.")

    return str(hour)


def parse_sms_request(text, keyword='TRAFFIC'):
    cleaned = (text or '').strip()
    if not cleaned:
        raise SmsParseError("Invalid format. Reply: FROM*TO*NOW")

    keyword = _canonical_token(keyword or 'TRAFFIC')
    parts = _split_sms(cleaned)

    if len(parts) == 1 and _canonical_token(parts[0]) in [keyword, 'HELP', 'START']:
        return {'type': 'help'}

    if parts and _canonical_token(parts[0]) == keyword:
        parts = parts[1:]

    if len(parts) < 3:
        raise SmsParseError("Invalid format. Reply: FROM*TO*NOW")

    origin_text = parts[0]
    destination_text = parts[1]
    mode_or_day = _canonical_token(parts[2])

    if mode_or_day == 'NOW':
        flags = _parse_flags(parts[3:])
        return {
            'type': 'prediction',
            'origin_text': origin_text,
            'destination_text': destination_text,
            'payload': {
                'timing_mode': 'now',
                **flags,
            },
        }

    if len(parts) < 5:
        raise SmsParseError("Invalid format. Reply: FROM*TO*DAY*HOUR*WEATHER")

    if mode_or_day not in DAY_VALUES:
        raise SmsParseError("Invalid day. Use MONDAY, TUESDAY, etc.")

    weather = _canonical_token(parts[4])
    if weather not in WEATHER_VALUES:
        raise SmsParseError("Invalid weather. Use DRY, LIGHT RAIN, or HEAVY RAIN.")

    flags = _parse_flags(parts[5:])
    return {
        'type': 'prediction',
        'origin_text': origin_text,
        'destination_text': destination_text,
        'payload': {
            'timing_mode': 'later',
            'day': DAY_VALUES[mode_or_day],
            'hour': _normalize_hour(parts[3]),
            'rain': WEATHER_VALUES[weather],
            **flags,
        },
    }


def format_prediction_sms(result):
    prediction = result['prediction']
    confidence = round(float(result['confidence']))
    advice = SMS_ADVICE.get(prediction, 'Check conditions before leaving.')
    return (
        f"Traffic: {prediction.upper()}\n"
        f"ETA: {result['eta']}\n"
        f"Confidence: {confidence}%\n"
        f"Advice: {advice}"
    )
