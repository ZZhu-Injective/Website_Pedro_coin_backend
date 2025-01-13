from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

@csrf_exempt
def save_addresses(request):
    if request.method == 'POST':
        print(request)
        data = json.loads(request.body)
        addresses = data.get('addresses', [])
        return JsonResponse({'status': 'success', 'addresses': addresses})
    return JsonResponse({'error': 'Invalid request'}, status=400)
