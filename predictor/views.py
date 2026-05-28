import json
import logging
import os

import requests
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .services import GOOGLE_API_KEY, WEATHER_OPTIONS, normalize_location, predict_route
from .sms import SmsParseError, format_prediction_sms, onboarding_message, parse_sms_request


logger = logging.getLogger(__name__)

VALID_DAYS = {str(day) for day in range(7)}
VALID_HOURS = {str(hour) for hour in range(24)}

# Sandbox defaults. For a live hackathon shortcode, change these environment
# variables only; the webhook and parser do not assume production values.
AT_USERNAME = os.getenv('AT_USERNAME', 'sandbox')
AT_API_KEY = os.getenv('AT_API_KEY', '')
AT_SHORTCODE = os.getenv('AT_SHORTCODE', '61274')
AT_SMS_KEYWORD = os.getenv('AT_SMS_KEYWORD', 'TRAFFIC')
AT_SMS_MODE = os.getenv('AT_SMS_MODE', 'premium').lower()
DEFAULT_PREMIUM_SMS_URL = 'https://content.africastalking.com/version1/messaging'
DEFAULT_LEGACY_SMS_URL = 'https://api.africastalking.com/version1/messaging'
AT_SMS_API_URL = os.getenv(
    'AT_SMS_API_URL',
    DEFAULT_LEGACY_SMS_URL if AT_SMS_MODE == 'legacy' else DEFAULT_PREMIUM_SMS_URL,
)


def _form_params(post_data):
    return {
        'from_lat': post_data.get('from_lat', -1.279),
        'from_lon': post_data.get('from_lon', 36.817),
        'to_lat': post_data.get('to_lat'),
        'to_lon': post_data.get('to_lon'),
        'school_impact': post_data.get('school_impact'),
        'avoid_expressway': post_data.get('avoid_expressway'),
        'timing_mode': post_data.get('timing_mode', 'now'),
        'hour': post_data.get('hour', 8),
        'day': post_data.get('day', 0),
        'rain': post_data.get('rain', 0.0),
    }


def predict_traffic(request):
    if request.method == 'POST':
        try:
            if not request.POST.get('to_lat') or not request.POST.get('to_lon'):
                return render(request, 'predictor/index.html', {
                    'error': "Missing destination coordinates. Please select a valid location from the dropdown.",
                    'google_key': GOOGLE_API_KEY,
                })

            context = predict_route(_form_params(request.POST), include_map=True)
            return render(request, 'predictor/result.html', context)

        except Exception as e:
            return render(request, 'predictor/index.html', {
                'error': f"Prediction failed: {str(e)}",
                'google_key': GOOGLE_API_KEY,
            })

    return render(request, 'predictor/index.html', {'google_key': GOOGLE_API_KEY})


@require_POST
def chatbot_predict(request):
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
        timing_mode = payload.get('timing_mode', 'now')

        if timing_mode not in ['now', 'later']:
            return JsonResponse({
                'ok': False,
                'field': 'timing',
                'message': "Please choose a valid travel time.",
            }, status=400)

        try:
            origin = normalize_location(payload.get('origin'))
        except ValueError as e:
            return JsonResponse({
                'ok': False,
                'field': 'origin',
                'message': str(e),
            }, status=400)

        try:
            destination = normalize_location(payload.get('destination'))
        except ValueError as e:
            return JsonResponse({
                'ok': False,
                'field': 'destination',
                'message': str(e),
            }, status=400)

        prediction_payload = {
            'from_lat': origin['lat'],
            'from_lon': origin['lon'],
            'to_lat': destination['lat'],
            'to_lon': destination['lon'],
            'timing_mode': timing_mode,
            'school_impact': payload.get('school_impact', 0),
            'avoid_expressway': payload.get('avoid_expressway', 0),
        }

        if timing_mode == 'later':
            day = str(payload.get('day', ''))
            hour = str(payload.get('hour', ''))
            rain = str(payload.get('rain', ''))

            if day not in VALID_DAYS:
                return JsonResponse({
                    'ok': False,
                    'field': 'day',
                    'message': "Please choose a valid day of week.",
                }, status=400)

            if hour not in VALID_HOURS:
                return JsonResponse({
                    'ok': False,
                    'field': 'hour',
                    'message': "Please choose a valid travel time.",
                }, status=400)

            if rain not in WEATHER_OPTIONS:
                return JsonResponse({
                    'ok': False,
                    'field': 'weather',
                    'message': "Please select one of the available weather options.",
                }, status=400)

            prediction_payload.update({
                'day': day,
                'hour': hour,
                'rain': rain,
            })

        result = predict_route(prediction_payload, include_map=False)
        return JsonResponse({
            'ok': True,
            'origin': origin,
            'destination': destination,
            'timing_mode': timing_mode,
            'prediction': result['prediction'],
            'confidence': result['confidence'],
            'eta': result['eta'],
            'advice': result['advice'],
            'message': (
                f"I predict {result['prediction'].lower()} traffic with "
                f"{result['confidence']}% confidence. {result['advice']}"
            ),
        })
    except Exception as e:
        return JsonResponse({
            'ok': False,
            'message': f"Sorry, I couldn't complete that prediction: {str(e)}",
        }, status=500)


def _sms_text(request):
    if request.content_type and 'application/json' in request.content_type:
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            payload = {}
        return payload.get('text') or payload.get('message') or ''

    return request.POST.get('text') or request.POST.get('message') or ''


def _sms_sender(request):
    if request.content_type and 'application/json' in request.content_type:
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            payload = {}
        return payload.get('from') or payload.get('phoneNumber') or ''

    return request.POST.get('from') or request.POST.get('phoneNumber') or ''


def _sms_link_id(request):
    if request.content_type and 'application/json' in request.content_type:
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            payload = {}
        return payload.get('linkId') or payload.get('link_id') or ''

    return request.POST.get('linkId') or request.POST.get('link_id') or ''


def _sms_shortcode(request):
    if request.content_type and 'application/json' in request.content_type:
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            payload = {}
        return payload.get('to') or payload.get('shortCode') or payload.get('shortcode') or ''

    return request.POST.get('to') or request.POST.get('shortCode') or request.POST.get('shortcode') or ''


def _sms_keyword(request):
    if request.content_type and 'application/json' in request.content_type:
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            payload = {}
        return payload.get('keyword') or ''

    return request.POST.get('keyword') or ''


def _sms_reply_payload(phone_number, message, link_id=None):
    payload = {
        'username': AT_USERNAME,
        'to': phone_number,
        'message': message,
    }

    if AT_SMS_MODE == 'legacy':
        # Legacy mode is useful for simple sandbox/bulk-style testing.
        # The official live API URL accepts sandbox credentials.
        payload['bulkSMSMode'] = 1
        return payload

    # Premium mode is the default for shortcode + keyword two-way SMS.
    payload.update({
        'from': AT_SHORTCODE,
        'keyword': AT_SMS_KEYWORD,
        'bulkSMSMode': 0,
    })
    if link_id:
        payload['linkId'] = link_id
    return payload


def _send_sms_reply(phone_number, message, link_id=None):
    if not AT_API_KEY or not phone_number:
        logger.warning(
            "[AT SMS] Skipping outbound reply. api_key_present=%s phone_present=%s",
            bool(AT_API_KEY),
            bool(phone_number),
        )
        return False

    payload = _sms_reply_payload(phone_number, message, link_id)
    logger.info(
        "[AT SMS] Sending %s reply endpoint=%s payload_keys=%s to=%s shortcode=%s keyword=%s linkId_present=%s",
        AT_SMS_MODE,
        AT_SMS_API_URL,
        sorted(payload.keys()),
        phone_number,
        payload.get('from', ''),
        payload.get('keyword', ''),
        bool(payload.get('linkId')),
    )

    try:
        response = requests.post(
            AT_SMS_API_URL,
            data=payload,
            headers={
                'apiKey': AT_API_KEY,
                'Accept': 'application/json',
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            timeout=8,
        )
        logger.info("[AT SMS] Response status=%s", response.status_code)
        logger.info("[AT SMS] Response body=%s", response.text)
        if response.status_code >= 400:
            logger.error(
                "[AT SMS] Outbound reply failed status=%s body=%s",
                response.status_code,
                response.text,
            )
            return False
        return True
    except Exception:
        logger.exception("[AT SMS] Exception while sending outbound reply")
        return False


@csrf_exempt
@require_POST
def africastalking_sms_webhook(request):
    incoming_text = _sms_text(request)
    sender = _sms_sender(request)
    link_id = _sms_link_id(request)
    shortcode = _sms_shortcode(request)
    inbound_keyword = _sms_keyword(request)
    parsed_type = 'unknown'

    logger.info(
        "[AT SMS] Incoming message from=%s shortcode=%s keyword=%s linkId=%s text=%s",
        sender,
        shortcode,
        inbound_keyword,
        link_id,
        incoming_text,
    )

    try:
        parsed = parse_sms_request(incoming_text, keyword=AT_SMS_KEYWORD)
        parsed_type = parsed.get('type', 'unknown')
        logger.info("[AT SMS] Parsed request type=%s parsed=%s", parsed_type, parsed)
        if parsed['type'] == 'help':
            reply = onboarding_message()
        else:
            try:
                origin = normalize_location(parsed['origin_text'])
            except ValueError:
                reply = "Could not find starting location. Try a nearby landmark or area."
            else:
                try:
                    destination = normalize_location(parsed['destination_text'])
                except ValueError:
                    reply = "Could not find destination location. Try a nearby landmark or area."
                else:
                    prediction_payload = {
                        'from_lat': origin['lat'],
                        'from_lon': origin['lon'],
                        'to_lat': destination['lat'],
                        'to_lon': destination['lon'],
                        **parsed['payload'],
                    }
                    result = predict_route(prediction_payload, include_map=False)
                    reply = format_prediction_sms(result)
    except SmsParseError as e:
        reply = str(e)
        logger.warning("[AT SMS] SMS parse error: %s", e)
    except Exception:
        reply = "Sorry, traffic prediction failed. Please try again later."
        logger.exception("[AT SMS] Exception while processing inbound SMS")

    sent = _send_sms_reply(sender, reply, link_id)
    logger.info(
        "[AT SMS] Webhook complete parsed_type=%s reply_sent=%s",
        parsed_type,
        sent,
    )
    return JsonResponse({'status': 'received'})
