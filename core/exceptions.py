from rest_framework.views import exception_handler
from rest_framework.exceptions import APIException
## Will be used to send exception for all the apis
class CustomApiException(APIException):

    #public fields
    detail = None
    status_code = None

    # create constructor
    def __init__(self, status_code, message):
        #override public fields
        CustomApiException.status_code = status_code
        CustomApiException.detail = message