from django.db import models
from django.db.models import JSONField
from django.utils.translation import gettext_lazy as _ 

from auditlog.registry import auditlog
from auditlog.models import AuditlogHistoryField

from base import mods
from base.models import Auth, Key


class Question(models.Model):
    desc = models.TextField()
    history = AuditlogHistoryField()

    VOTE_TYPE = (
        ('MULTIPLE','Multiple'),
        ('YESNO',"Yes/No"),
    )

    type = models.CharField(max_length=8,choices=VOTE_TYPE,default='IDENTITY',verbose_name=_("type"))

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.type == 'YESNO':
            # Eliminar todas las QuestionOptions asociadas
            self.options.all().delete()

            # Crear dos nuevas QuestionOptions
            optYes = QuestionOption(
                question_id=self.id,
                number=0,
                option='Yes',
            )
            optYes.save()

            optNo = QuestionOption(
                question_id=self.id,
                number=1,
                option='No',
            )
            optNo.save()
        if self.type == 'MULTIPLE':
            option = QuestionOption.objects.filter(number=2, option='No')
            option.delete()
            option = QuestionOption.objects.filter(number=3, option='Yes')
            option.delete()

        return super().save(*args, **kwargs)

    def __str__(self):
        return self.desc
    class Meta:
        verbose_name=_("Question")


class QuestionOption(models.Model):
    question = models.ForeignKey(Question, related_name='options', on_delete=models.CASCADE,verbose_name=_("question"))
    number = models.PositiveIntegerField(blank=True, null=True,verbose_name=_("number"))
    option = models.TextField(verbose_name=_("option"))
    history = AuditlogHistoryField()
    class Meta:
        verbose_name=_("QuestionOption")

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = self.question.options.count() + 2
        return super().save(*args, **kwargs)

    def __str__(self):
        return '{} ({})'.format(self.option, self.number)
    


class Voting(models.Model):
    name = models.CharField(max_length=200,verbose_name=_("name"))
    desc = models.TextField(blank=True, null=True)
    question = models.ForeignKey(Question, related_name='voting', on_delete=models.CASCADE,verbose_name=_("question"))

    start_date = models.DateTimeField(blank=True, null=True,verbose_name=_("start_date"))
    end_date = models.DateTimeField(blank=True, null=True,verbose_name=_("end_date"))

    pub_key = models.OneToOneField(Key, related_name='voting', blank=True, null=True, on_delete=models.SET_NULL)
    auths = models.ManyToManyField(Auth, related_name='votings')

    tally = JSONField(blank=True, null=True,verbose_name=_("tally"))
    postproc = JSONField(blank=True, null=True)
    history = AuditlogHistoryField()

    VOTE_METHODS = (
        ('IDENTITY','Identity'),
        ('DHONDT',"D'Hondt"),
        ('WEBSTER',"Webster"),
    )

    method = models.CharField(max_length=8,choices=VOTE_METHODS,default='IDENTITY',verbose_name=_("method"))

    seats = models.PositiveIntegerField(blank=True, null=True,verbose_name=_("seats"))
    
    class Meta:
        verbose_name=_("Voting")

    def create_pubkey(self):
        if self.pub_key or not self.auths.count():
            return

        auth = self.auths.first()
        data = {
            "voting": self.id,
            "auths": [ {"name": a.name, "url": a.url} for a in self.auths.all() ],
        }
        key = mods.post('mixnet', baseurl=auth.url, json=data)
        pk = Key(p=key["p"], g=key["g"], y=key["y"])
        pk.save()
        self.pub_key = pk
        self.save()

    def get_votes(self, token=''):
        # gettings votes from store
        votes = mods.get('store', params={'voting_id': self.id}, HTTP_AUTHORIZATION='Token ' + token)
        # anon votes
        votes_format = []
        vote_list = []
        for vote in votes:
            for info in vote:
                if info == 'a':
                    votes_format.append(vote[info])
                if info == 'b':
                    votes_format.append(vote[info])
            vote_list.append(votes_format)
            votes_format = []
        return vote_list
    
    def live_tally(self, token=''):
        votes = self.get_votes(token)

        auth = self.auths.first()
        shuffle_url = "/shuffle/{}/".format(self.id)
        decrypt_url = "/decrypt/{}/".format(self.id)
        auths = [{"name": a.name, "url": a.url} for a in self.auths.all()]
        data = { "msgs": votes }
        response = mods.post('mixnet', entry_point=shuffle_url, baseurl=auth.url, json=data,
                response=True)
        data = {"msgs": response.json()}
        response = mods.post('mixnet', entry_point=decrypt_url, baseurl=auth.url, json=data,
                response=True)

        tally = response.json()
        if(type(tally) is list):
            options = self.question.options.all()
            opts = []
            for opt in options:
                if self.method == 'IDENTITY':
                    votes = tally.count(opt.number)
                elif self.method == 'DHONDT':
                    votes = tally.count(opt.number)
                elif self.method == 'WEBSTER':
                    votes = tally.count(opt.number)
                else:
                    votes = 0
                opts.append({
                    'option': opt.option,
                    'number': opt.number,
                    'votes': votes
                })
            data = { 'method': self.method, 'options': opts, 'seats': self.seats }
            postp = mods.post('postproc', json=data)
        return postp

    def tally_votes(self, token=''):
        '''
        The tally is a shuffle and then a decrypt
        '''

        votes = self.get_votes(token)

        auth = self.auths.first()
        shuffle_url = "/shuffle/{}/".format(self.id)
        decrypt_url = "/decrypt/{}/".format(self.id)
        auths = [{"name": a.name, "url": a.url} for a in self.auths.all()]
        # first, we do the shuffle
        data = { "msgs": votes }
        response = mods.post('mixnet', entry_point=shuffle_url, baseurl=auth.url, json=data,
                response=True)
        if response.status_code != 200:
            # TODO: manage error
            pass
        # then, we can decrypt that
        data = {"msgs": response.json()}
        response = mods.post('mixnet', entry_point=decrypt_url, baseurl=auth.url, json=data,
                response=True)

        if response.status_code != 200:
            # TODO: manage error
            pass
        self.tally = response.json()
        self.save()

        self.do_postproc()


    def do_postproc(self):
        tally = self.tally
        if(type(tally) is list):
            options = self.question.options.all()
            opts = []
            for opt in options:
                if self.method == 'IDENTITY':
                    votes = tally.count(opt.number)
                elif self.method == 'DHONDT':
                    votes = tally.count(opt.number)
                elif self.method == 'WEBSTER':
                    votes = tally.count(opt.number)    
                else:
                    votes = 0
                opts.append({
                    'option': opt.option,
                    'number': opt.number,
                    'votes': votes
                })
            data = { 'method': self.method, 'options': opts, 'seats': self.seats }
            postp = mods.post('postproc', json=data)
            self.postproc = postp
            self.save()
        

    def __str__(self):
        return self.name


auditlog.register(Question, serialize_data=True,)
auditlog.register(QuestionOption, serialize_data=True,)
auditlog.register(Voting, serialize_data=True,)