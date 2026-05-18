import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .services import GOOGLE_API_KEY, predict_route


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

        if not payload.get('to_lat') or not payload.get('to_lon'):
            return JsonResponse({
                'ok': False,
                'message': "I need a destination before I can predict the route.",
            }, status=400)

        result = predict_route(payload, include_map=False)
        return JsonResponse({
            'ok': True,
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
