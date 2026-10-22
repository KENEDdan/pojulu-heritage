from django.views.generic import FormView, TemplateView
from django.urls import reverse_lazy
from django.core.cache import cache
from .forms import SubmissionForm

SUBMIT_LIMIT = 5
SUBMIT_WINDOW_SECONDS = 3600


class SubmissionView(FormView):
    template_name = 'submissions/form.html'
    form_class = SubmissionForm
    success_url = reverse_lazy('submissions:success')

    def _client_ip(self):
        forwarded = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded:
            return forwarded.split(',')[0].strip()
        return self.request.META.get('REMOTE_ADDR', 'unknown')

    def post(self, request, *args, **kwargs):
        key = f'submission_count:{self._client_ip()}'
        if cache.get(key, 0) >= SUBMIT_LIMIT:
            form = self.get_form()
            form.add_error(None, 'Too many submissions from this location. Please try again later.')
            return self.form_invalid(form)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        form.save()
        key = f'submission_count:{self._client_ip()}'
        cache.set(key, cache.get(key, 0) + 1, SUBMIT_WINDOW_SECONDS)
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.clans.models import Clan
        ctx['clans'] = Clan.objects.filter(is_verified=True).values('name','slug')
        return ctx

class SuccessView(TemplateView):
    template_name = 'submissions/success.html'
