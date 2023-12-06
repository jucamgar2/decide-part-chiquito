import json
from django.views.generic import TemplateView
from django.conf import settings
from django.http import Http404

from base import mods


class VisualizerView(TemplateView):
    template_name = 'visualizer/visualizer.html'


    def get_template_names(self):

        if self.request.user_agent.is_mobile:
            self.template_name = 'visualizer/visualizer_mobile.html'
        else:
            self.template_name = 'visualizer/visualizer.html'

        
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        vid = kwargs.get('voting_id', 0)

        try:
            r = mods.get('voting', params={'id': vid})
            context['voting'] = json.dumps(r[0])
            context['is_mobile'] = self.request.user_agent.is_mobile
        except:
            raise Http404

        return context
