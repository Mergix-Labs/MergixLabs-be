# MergixLabs Django Template

## Overview
Django template that will be used by the backend team as a base structure for upcoming projects


## Features
- Enhanced Admin Panel (better version of the default admin panel)
- Django REST Framework setup
- Simple JWT token authentication using DRF
- APIs for login, signup, and token refresh
- Configuration for environment variables
- Setup for S3 with CloudFront and a custom client using Boto3


## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/MergixLabs/django-template
   cd MergixLabs-django-template
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Celery Setup

### Start the Celery Worker
To start the Celery worker, use the following command:

```bash
celery -A core worker --loglevel=info -P eventlet
```

### Why Use Eventlet with Celery?
Eventlet provides greater concurrency compared to the prefork method, allowing you to manage multiple tasks simultaneously without the need for non-blocking code.

## Example of Running a Celery Task

You can run a Celery task within a Django view as follows:

```python
from django.http import JsonResponse
from .tasks import myprint  # Ensure to import your task

def run_celery_task(request):
    # 1st method: Using delay
    myprint.delay()  # args can be passed as well, but not objects
    # Syntax: task_name.delay(arg1, arg2, ...)

    # 2nd method: Using apply_async
    myprint.apply_async()  # args can be passed as well, but not objects
    # Syntax: task_name.apply_async(args=[arg1, arg2], kwargs={'key': value}, options={})

    return JsonResponse({'status': 'success'})
```
## CI/CD Setup
To setup CI/CD follow these steps:
- **Generate SSH-KEY**: Create a SSH-Key to set into your Github SSH and GPG sections.
  ```bash
   ssh-keygen -t ed25519 -C "your_email@gmail.com"
   ```
  
- **Make SSH Agent Run**: To make ssh agent run & function properly.
   ```bash
   eval "$(ssh-agent -s)"
   ```
   
- **Adding SSH-Key**: Adding the key is cruscial step.
   ```bash
   ssh-add ~/.ssh/id_ed25519
   ```
   
- **Pull through SSH**: To set the origin to pull from ssh-key instead asking for tokens
   ```bash
   git remote set-url origin git@github.com:MergixLabs/django-template.git
   ```
   
- **Authorizing Key**: Regestering the SSH-KEY as authorized is a crucial step.
   ```bash
   cat ~/.ssh/id_ed25519.pub >> ~/.ssh/authorized_keys
   ```
   
- **Executable Permission**: Adding the right permission.
   ```bash
   chmod 600 ~/.ssh/authorized_keys
   ```

## Github-Action & Workflow Setup
  1. Go to the repo settings.
  2. Go to the Secrets & Variable section and click on Actions.
  3. Click on New Repository Secret.
  4. There are going to be 3 required secrets:
     - **HOST**: The Ip of your EC2 Instance.
     - **USER**: ubuntu (This is used as default username).
     - **SSH_PRIVATE_KEY**: This is going to be the same private key of the SSH-KEY that you created while setting up CI/CD steps.
          To see this use this command.
          ```bash
           cat ~/.ssh/id_ed25519
          ```
   - There are certain files that are responsible here.
     - **deploy.yaml**: The file should be located in the root directiory where your **manage.py** is inside **.github/worflows** directory.
     - **install-docker.sh**: 
          - This is one time runner only runs if the EC2 instance does not have docker installed.
          - The file should be located in the root directiory where your **manage.py** is inside **.scripts** directory.
          - Used for installing docker on the Ec2 instance.
            
     - **start-docker.sh**
         - This is responsible for removing all the conatiners and then starting up them again.
         - The file should be located in the root directiory where your **manage.py** is inside **.scripts** directory.
         - It also starts the gunicorn & nginx.
           
     - **start.sh**
        - The file should be located in the root directiory where your **manage.py** is inside **.scripts** directory.
        - Mainly responsible for running the migrations if exists and bind the port with Gunicorn.
          
     - **dockerfile**
        - The file should be located in the root directiory where your **manage.py**.
          
     - **docker-compose.yaml**
        - The file should be located in the root directiory where your **manage.py**.

## APIs
This template includes APIs for:
- **Login**: Authenticate users and issue JWT tokens.
- **Signup**: Register new users.
- **Refresh Token**: Obtain new tokens using refresh tokens.
- **Meeting Scheduling** (`/api/v1/meetings/`): Google Calendar-backed slot lookup, booking, reschedule, and cancellation. See [apps/meeting/README.md](apps/meeting/README.md) for setup and API details.

## Environment Variables
Make sure to set up the required environment variables for your project. Use a `settings.ini` file for configuration.

## S3 Setup
This template is configured to work with AWS S3 and CloudFront using Boto3. Ensure you have your AWS credentials set up.

## Contributing
Feel free to contribute to this project by forking the repository and submitting a pull request.


## Contact
For any questions or feedback, please reach out to [aman@mergixlabs-.com].
