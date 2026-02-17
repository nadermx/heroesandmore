import time
import logging
from django.contrib import messages
from django.shortcuts import redirect

logger = logging.getLogger('app')


class SignupHoneypotMiddleware:
    """
    Block spam signups using a honeypot field and timestamp check.
    Bots that fill the hidden 'website' field or submit too fast get
    silently redirected with a fake success message.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == 'POST' and request.path == '/auth/signup/':
            # Honeypot check — bots fill hidden fields
            if request.POST.get('website', ''):
                logger.warning(
                    f"Signup spam blocked (honeypot): "
                    f"{request.POST.get('email', '')} / {request.POST.get('username', '')}"
                )
                messages.success(request, 'Account created! Please check your email to verify your address.')
                return redirect('account_login')

            # Timestamp check — form submitted too fast (< 3 seconds = bot)
            form_ts = request.POST.get('_ts', '')
            if form_ts:
                try:
                    elapsed = time.time() - float(form_ts)
                    if elapsed < 3:
                        logger.warning(
                            f"Signup spam blocked (too fast: {elapsed:.1f}s): "
                            f"{request.POST.get('email', '')} / {request.POST.get('username', '')}"
                        )
                        messages.success(request, 'Account created! Please check your email to verify your address.')
                        return redirect('account_login')
                except (ValueError, TypeError):
                    pass

        return self.get_response(request)
