from django.views.generic import TemplateView


class AppDownloadView(TemplateView):
    template_name = "app/download.html"
