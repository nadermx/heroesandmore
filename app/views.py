import json
import logging
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger('frontend')


def sell_landing(request):
    if request.user.is_authenticated:
        return redirect('marketplace:listing_create')
    return render(request, 'pages/sell.html')


@csrf_exempt
@require_POST
def log_frontend_error(request):
    """
    Endpoint for logging frontend JavaScript errors.
    POST /api/log-error/

    Expected payload:
    {
        "message": "Error message",
        "source": "script URL",
        "lineno": 123,
        "colno": 45,
        "error": "Error stack trace",
        "url": "Page URL where error occurred",
        "userAgent": "Browser user agent"
    }
    """
    try:
        data = json.loads(request.body)

        error_info = {
            'message': data.get('message', 'Unknown error'),
            'source': data.get('source', 'unknown'),
            'line': data.get('lineno', 0),
            'column': data.get('colno', 0),
            'stack': data.get('error', ''),
            'url': data.get('url', ''),
            'user_agent': data.get('userAgent', ''),
            'user_id': request.user.id if request.user.is_authenticated else None,
        }

        logger.error(
            f"Frontend error: {error_info['message']} | "
            f"Source: {error_info['source']}:{error_info['line']}:{error_info['column']} | "
            f"URL: {error_info['url']} | "
            f"User: {error_info['user_id']} | "
            f"Stack: {error_info['stack']}"
        )

        return JsonResponse({'status': 'logged'})
    except Exception as e:
        logger.error(f"Failed to log frontend error: {e}")
        return JsonResponse({'status': 'error'}, status=400)
