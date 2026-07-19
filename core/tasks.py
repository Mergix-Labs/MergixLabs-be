from .celery import app
from decouple import config
@app.task
def myprint():
    print('Running in Background')
    return True
'''
Mailjet is used to send emails, here it is used as a celery task, as it is a long running task
'''
from .email import forgot_password_template
from mailjet_rest import Client
from django.conf import settings

@app.task
def send_forgot_email(name,email,link):
        mailjet = Client(auth=(settings.MAILJET_API_KEY, settings.MAILJET_SECRET_KEY), version='v3.1')
        html_content = forgot_password_template(name,link)
        data = {
        'Messages': [
                        {
                                "From": {
                                        "Email": "contact@mergixlabs-.com",
                                        "Name": "MergixLabs"
                                },
                                "To": [
                                        {
                                                "Email": email,
                                                "Name": name
                                        }
                                ],
                                "Subject": "Forgot Password?",
                                "HTMLPart": html_content
                        }
                ]
        }
        result = mailjet.send.create(data=data)
        print(result.status_code)
        print(result.json())
        return True
