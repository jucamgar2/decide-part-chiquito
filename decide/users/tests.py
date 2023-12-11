from base.tests import BaseTestCase
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import TestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APIClient
from selenium import webdriver
from selenium.webdriver.common.by import By
from django.core.files.uploadedfile import SimpleUploadedFile


class RegisterViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()

    def test_get_register_view(self):
        response = self.client.get(reverse('users:register'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/register.html')

    def test_successful_registration(self):
        data = {
            'username': 'testuser',
            'password': 'testpassword',
            'confirm_password': 'testpassword',
            'email': 'test@example.com',
        }
        response = self.client.post(reverse('users:register'), data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/register_success.html')

    def test_password_mismatch(self):
        data = {
            'username': 'testuser',
            'password': 'testpassword',
            'confirm_password': 'mismatchedpassword',
            'email': 'test@example.com',
        }
        response = self.client.post(reverse('users:register'), data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/register_fail.html')
        self.assertContains(response, 'The passwords do not match.')

    def test_username_already_in_use(self):
        User.objects.create_user(username='existinguser', password='testpassword', email='existing@example.com')
        data = {
            'username': 'existinguser',
            'password': 'testpassword',
            'confirm_password': 'testpassword',
            'email': 'test@example.com',
        }
        response = self.client.post(reverse('users:register'), data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/register_fail.html')
        self.assertContains(response, 'The username is already in use.')



class LoginLogoutViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        self.login_url = reverse('users:login')

    def test_get_login_view(self):
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/login.html')

    def test_login_success(self):
        data = {'username': 'testuser', 'password': 'testpassword'}
        response = self.client.post(self.login_url, data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')

    def test_login_failure(self):
        data = {'username': 'testuser', 'password': 'wrongpassword'}
        response = self.client.post(self.login_url, data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/login.html')
        self.assertIn('error', response.context)
        self.assertEqual(response.context['error'], 'invalid credentials')

    def test_logout(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('users:logout'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')

    def test_mail_login(self):
        response = self.client.get(reverse('social:begin', args=['google-oauth2']))
        assert response.status_code == 302

class RequestPasswordResetViewTests(StaticLiveServerTestCase):
    def setUp(self):
        self.base = BaseTestCase()
        self.base.setUp()
        options = webdriver.ChromeOptions()
        options.headless = True
        self.driver = webdriver.Chrome(options=options)
        super().setUp()

        self.password = "Hola$1234"
        self.noadmin = User.objects.filter(username="noadmin").first()
        self.noadmin.set_password('1234')
        self.noadmin.email = 'noadmin@gmail.com'
        self.noadmin.save()

    def tearDown(self):
        super().tearDown()
        self.driver.quit()
        self.base.tearDown()

    def test_request_password_reset(self):
        self.driver.get(f"{self.live_server_url}/users/login/")
        self.driver.set_window_size(1850, 1016)
        self.driver.find_element(By.LINK_TEXT, "¿Olvidó su contraseña?").click()
        self.driver.find_element(By.ID, "id_email").click()
        self.driver.find_element(By.ID, "id_email").send_keys(self.noadmin.email)
        self.driver.find_element(By.CSS_SELECTOR, ".btn").click()
        self.assertTrue(self.driver.current_url == f"{self.live_server_url}/")

    def test_change_password(self):
        token = default_token_generator.make_token(self.noadmin)
        uid = urlsafe_base64_encode(force_bytes(self.noadmin.pk))
        self.driver.get(f"{self.live_server_url}/users/change-password/{uid}/{token}/")
        self.driver.set_window_size(1850, 1016)
        self.driver.find_element(By.ID, "id_password").click()
        self.driver.find_element(By.ID, "id_password").send_keys(self.password)
        self.driver.find_element(By.ID, "id_confirm_password").click()
        self.driver.find_element(By.ID, "id_confirm_password").send_keys(self.password)
        self.driver.find_element(By.CSS_SELECTOR, ".btn").click()
        self.noadmin = User.objects.filter(username="noadmin").first()
        self.assertTrue(self.noadmin.check_password(self.password))
        self.assertTrue(self.driver.current_url == f"{self.live_server_url}/")


class MailLoginTest(StaticLiveServerTestCase):

    def setUp(self):
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

    def test_mail_login_fail(self):
        self.driver.get(f"{self.live_server_url}/users/login/")
        self.driver.find_element(By.LINK_TEXT, "Iniciar sesión con Google").click()
        self.assertTrue("https://accounts.google.com/" in self.driver.current_url)
        

class CertLoginViewTest(TestCase):
    def test_get_cert_login_view(self):
        response = self.client.get('/users/cert-login/')
        self.assertEqual(response.status_code,200)
        self.assertTemplateUsed(response,'registration/cert_login.html')

    def test_post_cert_login_view_filure(self):
        data={'cert_file':'','cert_password':''}
        response = self.client.post('/users/cert-login/',data)
        self.assertEqual(response.status_code,200)
        self.assertTemplateUsed(response, 'registration/cert_fail.html')

    def test_post_cert_login_view_invalid_cert(self):
        invalid_file = SimpleUploadedFile("invalid_file.txt", 
            b"soy un archivo que no es un certificado digital, por lo tanto no debe funcionar el login")
        data = {'cert_file': invalid_file, 'cert_password': 'testpassword'}
        response = self.client.post('/users/cert-login/', data, format='multipart')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/cert_fail.html')

    ''' El archivo cert.pfx es un certificado digital ficticio que sirve para hacer pruebas, la contraseña es 1111'''
    def test_post_cert_login_view_succes(self):
        with open('cert.pfx', 'rb') as cert_file:
            cert_content = cert_file.read()
        cert_uploaded = SimpleUploadedFile("cert.pfx", cert_content, content_type="application/x-pkcs12")
        data = {'cert_file': cert_uploaded, 'cert_password': '1111'}
        response = self.client.post('/users/cert-login/', data, format='multipart')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/cert_success.html')

    def test_post_cert_login_view_invalid_password(self):
        with open('cert.pfx', 'rb') as cert_file:
            cert_content = cert_file.read()
        cert_uploaded = SimpleUploadedFile("cert.pfx", cert_content, content_type="application/x-pkcs12")
        data = {'cert_file': cert_uploaded, 'cert_password': 'invalid_pasword'}
        response = self.client.post('/users/cert-login/', data, format='multipart')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/cert_fail.html')

