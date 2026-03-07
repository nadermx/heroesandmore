from affiliates.models import Affiliate


class AffiliateMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == 'GET':
            ref_code = request.GET.get('ref')
            if ref_code:
                if Affiliate.objects.filter(referral_code=ref_code, is_active=True).exists():
                    request.session['ham_ref'] = ref_code
                    request._set_affiliate_cookie = ref_code

        response = self.get_response(request)

        if hasattr(request, '_set_affiliate_cookie'):
            response.set_cookie(
                'ham_ref',
                request._set_affiliate_cookie,
                max_age=30 * 24 * 60 * 60,  # 30 days
                httponly=True,
                secure=not request.META.get('SERVER_NAME', '').startswith('localhost'),
                samesite='Lax',
            )

        return response
