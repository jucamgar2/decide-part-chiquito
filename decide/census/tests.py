import random
from django.contrib.auth.models import User
from django.test import override_settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core import mail

from selenium import webdriver
from selenium.webdriver.common.by import By

from .models import Census, Voting
from voting.models import Question
from base.tests import BaseTestCase

from django.contrib.admin.sites import AdminSite
from voting.admin import VotingAdmin
from voting.models import Voting
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test.client import RequestFactory
from django.utils import timezone



class CensusTestCase(BaseTestCase):
    @override_settings(USE_TZ=False)
    def setUp(self):
        super().setUp()
        self.user = User.objects.create(id=51, email='test@test.com', username='test', password='test')
        self.user.save()
        question = Question(desc="What is your question?")
        question.save()
        self.voting = Voting(id=100, name="Test Voting", question=question)
        self.voting.save()
        self.census = Census(voting_id=1, voter_id=1)
        self.census.save()

    def tearDown(self):
        super().tearDown()
        self.census = None
        self.user = None
        self.voting = None

    def test_check_vote_permissions(self):
        response = self.client.get('/census/{}/?voter_id={}'.format(1, 2), format='json')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), 'Invalid voter')

        response = self.client.get('/census/{}/?voter_id={}'.format(1, 1), format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), 'Valid voter')

    def test_list_voting(self):
        response = self.client.get('/census/?voting_id={}'.format(1), format='json')
        self.assertEqual(response.status_code, 401)

        self.login(user='noadmin')
        response = self.client.get('/census/?voting_id={}'.format(1), format='json')
        self.assertEqual(response.status_code, 403)

        self.login()
        response = self.client.get('/census/?voting_id={}'.format(1), format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'voters': [1]})

    def test_add_new_voters_conflict(self):
        data = {'voting_id': 1, 'voters': [1]}
        response = self.client.post('/census/', data, format='json')
        self.assertEqual(response.status_code, 401)

        self.login(user='noadmin')
        response = self.client.post('/census/', data, format='json')
        self.assertEqual(response.status_code, 403)

        self.login()
        response = self.client.post('/census/', data, format='json')
        self.assertEqual(response.status_code, 409)

    def test_add_new_voters(self):
        data = {'voting_id': 2, 'voters': [1,2,3,4]}
        response = self.client.post('/census/', data, format='json')
        self.assertEqual(response.status_code, 401)

        self.login(user='noadmin')
        response = self.client.post('/census/', data, format='json')
        self.assertEqual(response.status_code, 403)

        self.login()
        response = self.client.post('/census/', data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(data.get('voters')), Census.objects.count() - 1)
    
    def test_send_email_on_census_creation(self):
        data = {'voting_id': 1, 'voters': [51]}
        self.login()
        response = self.client.post('/census/', data, format='json')
        self.assertEqual(response.status_code, 201)
        voter = User.objects.get(pk=51)
        self.assertEqual(mail.outbox[0].to, [voter.email])
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'New voting available')
        self.assertEqual(mail.outbox[0].body, 'You have been added to a new census. You could vote in the voting with id: 1 when the voting is open.')

    def test_send_without_email(self):
        data = {'voting_id': 2, 'voters': [1,2,3,4]}
        response = self.client.post('/census/', data, format='json')
        self.assertEqual(response.status_code, 401)

        self.login(user='noadmin')
        response = self.client.post('/census/', data, format='json')
        self.assertEqual(response.status_code, 403)

        self.login()
        response = self.client.post('/census/', data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(data.get('voters')), Census.objects.count() - 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_send_email_on_census_creation_with_voting(self):
        data = {'voting_id': 100, 'voters': [51]}
        self.login()
        response = self.client.post('/census/', data, format='json')
        self.assertEqual(response.status_code, 201)

        voter = User.objects.get(pk=51)
        voting = Voting.objects.get(pk=100)
        self.assertEqual(voting.name, 'Test Voting')
        self.assertEqual(mail.outbox[0].to, [voter.email])
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'New voting available')
        self.assertEqual(mail.outbox[0].body, 'You have been added to a new census called Test Voting. You could vote in the voting with id: 100 when the voting is open.')


    def test_destroy_voter(self):
        data = {'voters': [1]}
        response = self.client.delete('/census/{}/'.format(1), data, format='json')
        self.assertEqual(response.status_code, 204)
        self.assertEqual(0, Census.objects.count())

    def test_update_census(self):
        self.login()
        data = {'voters': [2]}
        response = self.client.put('/census/{}/'.format(1), data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual("Census updated", response.json())

    def test_import_census(self):
        self.login()
        admin_instance = VotingAdmin(model=Voting, admin_site=AdminSite())

        csv_content = "votingID,voterID,center,tags...\n1,2,ETSII,tag1\n2,2,ETSA,tag1,tag2"
        csv_file = SimpleUploadedFile("census.csv", csv_content.encode("utf-8"), content_type="text/csv")

        request = RequestFactory().post('/admin/voting/voting/upload-csv/', {'csv_upload': csv_file})
        user = User.objects.get(username='admin')
        self.assertTrue(user.check_password('qwerty'))
        request.user = user


        response = admin_instance.upload_csv(request)

        self.assertEqual(response.status_code, 302)

        census1 = Census.objects.get(voting_id=1, voter_id=2)
        self.assertEqual(census1.voting_id, 1)
        self.assertEqual(census1.voter_id, 2)
        self.assertEqual(census1.adscription_center, 'ETSII')
        self.assertTrue(census1.tags.filter(name='tag1').exists())

        census2 = Census.objects.get(voting_id=2, voter_id=2)
        self.assertEqual(census2.voting_id, 2)
        self.assertEqual(census2.voter_id, 2)
        self.assertEqual(census2.adscription_center, 'ETSA')
        self.assertTrue(census2.tags.filter(name='tag1').exists())
        self.assertTrue(census2.tags.filter(name='tag2').exists())



class CensusTest(StaticLiveServerTestCase):
    def setUp(self):
        #Load base test functionality for decide
        self.base = BaseTestCase()
        self.base.setUp()

        options = webdriver.ChromeOptions()
        options.headless = True
        self.driver = webdriver.Chrome(options=options)

        super().setUp()

    def tearDown(self):
        super().tearDown()
        self.driver.quit()

        self.base.tearDown()
    
    def createCensusSuccess(self):
        self.cleaner.get(self.live_server_url+"/admin/login/?next=/admin/")
        self.cleaner.set_window_size(1280, 720)

        self.cleaner.find_element(By.ID, "id_username").click()
        self.cleaner.find_element(By.ID, "id_username").send_keys("decide")

        self.cleaner.find_element(By.ID, "id_password").click()
        self.cleaner.find_element(By.ID, "id_password").send_keys("decide")

        self.cleaner.find_element(By.ID, "id_password").send_keys("Keys.ENTER")

        self.cleaner.get(self.live_server_url+"/admin/census/census/add")
        now = timezone.now()
        self.cleaner.find_element(By.ID, "id_voting_id").click()
        self.cleaner.find_element(By.ID, "id_voting_id").send_keys(now.strftime("%m%d%M%S"))
        self.cleaner.find_element(By.ID, "id_voter_id").click()
        self.cleaner.find_element(By.ID, "id_voter_id").send_keys(now.strftime("%m%d%M%S"))
        self.cleaner.find_element(By.NAME, "_save").click()

        self.assertTrue(self.cleaner.current_url == self.live_server_url+"/admin/census/census")

    def createCensusEmptyError(self):
        self.cleaner.get(self.live_server_url+"/admin/login/?next=/admin/")
        self.cleaner.set_window_size(1280, 720)

        self.cleaner.find_element(By.ID, "id_username").click()
        self.cleaner.find_element(By.ID, "id_username").send_keys("decide")

        self.cleaner.find_element(By.ID, "id_password").click()
        self.cleaner.find_element(By.ID, "id_password").send_keys("decide")

        self.cleaner.find_element(By.ID, "id_password").send_keys("Keys.ENTER")

        self.cleaner.get(self.live_server_url+"/admin/census/census/add")

        self.cleaner.find_element(By.NAME, "_save").click()

        self.assertTrue(self.cleaner.find_element_by_xpath('/html/body/div/div[3]/div/div[1]/div/form/div/p').text == 'Please correct the errors below.')
        self.assertTrue(self.cleaner.current_url == self.live_server_url+"/admin/census/census/add")

    def createCensusValueError(self):
        self.cleaner.get(self.live_server_url+"/admin/login/?next=/admin/")
        self.cleaner.set_window_size(1280, 720)

        self.cleaner.find_element(By.ID, "id_username").click()
        self.cleaner.find_element(By.ID, "id_username").send_keys("decide")

        self.cleaner.find_element(By.ID, "id_password").click()
        self.cleaner.find_element(By.ID, "id_password").send_keys("decide")

        self.cleaner.find_element(By.ID, "id_password").send_keys("Keys.ENTER")

        self.cleaner.get(self.live_server_url+"/admin/census/census/add")
        now = timezone.now()
        self.cleaner.find_element(By.ID, "id_voting_id").click()
        self.cleaner.find_element(By.ID, "id_voting_id").send_keys('64654654654654')
        self.cleaner.find_element(By.ID, "id_voter_id").click()
        self.cleaner.find_element(By.ID, "id_voter_id").send_keys('64654654654654')
        self.cleaner.find_element(By.NAME, "_save").click()

        self.assertTrue(self.cleaner.find_element_by_xpath('/html/body/div/div[3]/div/div[1]/div/form/div/p').text == 'Please correct the errors below.')
        self.assertTrue(self.cleaner.current_url == self.live_server_url+"/admin/census/census/add")