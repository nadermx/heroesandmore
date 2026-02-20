import re
import time
import logging
from django.contrib import messages
from django.shortcuts import redirect

logger = logging.getLogger('app')

# Patterns that indicate a bot-generated username
_RANDOM_USERNAME_RE = re.compile(
    r'^[A-Za-z]{15,}$'  # 15+ letters with no numbers/spaces (random strings)
)
_MIXED_CASE_RE = re.compile(
    r'(?:[A-Z][a-z]){5,}|(?:[a-z][A-Z]){5,}'  # Excessive case alternation
)


def _looks_like_bot_username(username):
    """Detect random-string usernames typical of spam bots."""
    if not username:
        return False
    # Too long with no separators
    if len(username) > 20 and not re.search(r'[\d_\-. ]', username):
        return True
    # Random string: 15+ letters, mixed case, no real word patterns
    if _RANDOM_USERNAME_RE.match(username) and _MIXED_CASE_RE.search(username):
        # Count uppercase letters - real usernames rarely have 4+ uppercase
        upper_count = sum(1 for c in username if c.isupper())
        if upper_count >= 4:
            return True
    return False


class SignupHoneypotMiddleware:
    """
    Block spam signups using a honeypot field, timestamp check, and
    bot username detection. Bots get silently redirected with a fake
    success message so they think the signup worked.
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

            # Missing timestamp — JS didn't run (headless bot)
            if not form_ts:
                logger.warning(
                    f"Signup spam blocked (no timestamp): "
                    f"{request.POST.get('email', '')} / {request.POST.get('username', '')}"
                )
                messages.success(request, 'Account created! Please check your email to verify your address.')
                return redirect('account_login')

            # Bot username detection — random gibberish strings
            username = request.POST.get('username', '')
            if _looks_like_bot_username(username):
                logger.warning(
                    f"Signup spam blocked (bot username): "
                    f"{request.POST.get('email', '')} / {username}"
                )
                messages.success(request, 'Account created! Please check your email to verify your address.')
                return redirect('account_login')

        return self.get_response(request)
