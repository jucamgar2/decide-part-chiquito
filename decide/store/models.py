from django.db import models
from base.models import BigBigField
from auditlog.registry import auditlog
from auditlog.models import AuditlogHistoryField

from django.utils.translation import gettext_lazy as _

class Vote(models.Model):
    
    voting_id = models.PositiveIntegerField(verbose_name=_("voting_id"))
    voter_id = models.PositiveIntegerField(verbose_name=_("voter_id"))
    history = AuditlogHistoryField()

    a = BigBigField()
    b = BigBigField()

    voted = models.DateTimeField(auto_now=True,verbose_name=_("voted"))

    class Meta:
        verbose_name=_("Vote")
        
    def __str__(self):
        return '{}: {}'.format(self.voting_id, self.voter_id)

auditlog.register(Vote, serialize_data=True,)

