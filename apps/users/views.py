from django.http import JsonResponse
from .serializers import *
from rest_framework import generics,status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.conf import settings
from django.middleware import csrf
from .models import CustomUser
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.encoding import smart_bytes
from django.utils.http import urlsafe_base64_encode
from core.tasks import send_forgot_email

class RegistrationView(generics.GenericAPIView):
    serializer_class = RegistrationSerializer

    def post(self,request):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            user_data = serializer.data
            
            user_data['tokens'].pop('refresh')
            response = Response({'success':True,"data":user_data}, status=status.HTTP_201_CREATED)
            # Set the JWT token in the cookie
            response.set_cookie(
                key=settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH'], 
                value=user.tokens["refresh"],
                max_age=2592000,
                expires=settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'],  
                secure=settings.SIMPLE_JWT['AUTH_COOKIE_SECURE'], 
                httponly=settings.SIMPLE_JWT['AUTH_COOKIE_HTTP_ONLY'], 
                samesite=settings.SIMPLE_JWT['AUTH_COOKIE_SAMESITE'],
                domain="127.0.0.1"
            )
            # Get CSRF token
            csrf.get_token(request)
            return response
        return Response({'success':False,"data":serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

class LoginAPIView(generics.GenericAPIView):
    serializer_class = LoginSerializer
    def post(self,request):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            # return Response(serializer.data,status=status.HTTP_200_OK)
            data = serializer.data.copy()  # Create a copy to avoid modifying the original serializer.data
            tokens = data.get("tokens", {})
            refresh_token = tokens.pop("refresh", None)
            response = Response(data, status=status.HTTP_200_OK)
            
            # Set the JWT token in the cookie
            response.set_cookie(
                key=settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH'], 
                value=refresh_token,
                max_age=2592000,
                expires=settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'], 
                secure=settings.SIMPLE_JWT['AUTH_COOKIE_SECURE'], 
                httponly=settings.SIMPLE_JWT['AUTH_COOKIE_HTTP_ONLY'], 
                samesite=settings.SIMPLE_JWT['AUTH_COOKIE_SAMESITE'],
                domain="127.0.0.1"
            )

            # Get CSRF token
            csrf.get_token(request)
            
            return response
        return Response({'sucess':False,"data":serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

ERROR_TYPE = {
    'INVALID_CREDENTIALS':{'message':'email or password does mot match'},
    'INVALID_REFRESH':{'message':'invalid refresh Token, Login in Again'}
}

class CustomTokenRefreshView(APIView):
    '''
    Gets COOKIE data from request generate new token
    from the refresh token and returns an access token
    '''
    def get(self,request):
        try:
            token = request.COOKIES['refresh_token']
            token = RefreshToken(token)
            return JsonResponse({"sucess":True,"data":{"access": str(token.access_token)}}, status=status.HTTP_201_CREATED)
        except Exception:
            return JsonResponse({'success':False,'data': ERROR_TYPE['INVALID_REFRESH']}, status=status.HTTP_401_UNAUTHORIZED)


class LogoutView(APIView):
    '''
    Logout API blacklists the refresh tooken and deletes the cookies
    make sure to send cookies in request from frontend
    '''
    def post(self,request):
        try:
            token = RefreshToken(request.COOKIES['refresh_token'])
            token.blacklist()
            res=JsonResponse({"data": {'message': 'Logged-Out Sucessfully'}}, status=status.HTTP_200_OK)
            res.delete_cookie(key='refresh_token')
            return res
        except Exception:
            return JsonResponse({'data': ERROR_TYPE['INVALID_REFRESH']}, status=status.HTTP_401_UNAUTHORIZED)

class RequestPasswordResetEmail(generics.GenericAPIView):
    serializer_class = ResetPasswordEmailRequestSerializer
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=False)
        email = serializer.validated_data.get('email')
        user = CustomUser.objects.filter(email=email).first()
        if user:
            user = CustomUser.objects.get(email=email)
            uidb64 = urlsafe_base64_encode(smart_bytes(user.id))
            token = PasswordResetTokenGenerator().make_token(user)
            # Frontend URL with token as a URL parameter
            link =f"{settings.FRONTEND_URL}/create-new-password?base={uidb64}&token={token}"
            send_forgot_email.delay(user.full_name,user.email,link)
            return Response({'success': {"email":user.email,"message":'We have sent you a link to reset your password'}}, status=status.HTTP_200_OK)
        return Response({'error':{"message":'Account with this email does not exsist'}}, status=status.HTTP_400_BAD_REQUEST)

class SetNewPasswordAPIView(generics.GenericAPIView):
    serializer_class = SetNewPasswordSerializer

    def patch(self, request):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid(raise_exception=False):
            return Response({'success': True, 'message': 'Password reset success'}, status=status.HTTP_200_OK)    
        return Response({'success': False, 'message': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
