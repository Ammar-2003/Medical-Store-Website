import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .predictor import engine


@csrf_exempt
@require_POST
def analyze_symptoms(request):
    try:
        data = json.loads(request.body)
        symptoms = data.get("symptoms", "").strip()

        if not symptoms:
            return JsonResponse({"error": "Symptoms are required"}, status=400)

        result = engine.predict(symptoms)
        return JsonResponse(result, safe=False)

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)