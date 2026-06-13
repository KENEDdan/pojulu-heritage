from django.views.generic import FormView, TemplateView
from django.urls import reverse_lazy
from .forms import SubmissionForm

class SubmissionView(FormView):
    template_name = 'submissions/form.html'
    form_class = SubmissionForm
    success_url = reverse_lazy('submissions:success')

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.clans.models import Clan
        ctx['clans'] = Clan.objects.filter(is_verified=True).values('name','slug')
        return ctx

class SuccessView(TemplateView):
    template_name = 'submissions/success.html'
