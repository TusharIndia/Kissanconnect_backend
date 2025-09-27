from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authtoken.models import Token
from django.contrib.auth import login
from django.utils import timezone
from django.conf import settings
import logging
from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authtoken.models import Token
from django.contrib.auth import login
from django.utils import timezone
from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from django.http import JsonResponse
import logging
import requests
import json
import secrets
import base64
import hashlib
import urllib.parse

from django.views.decorators.csrf import csrf_exempt

from ..models import CustomUser, OTP, UserSession
from .serializers_new import (
    PhoneRegistrationSerializer,
    ProfileCompletionSerializer,
    OTPRequestSerializer,
    OTPVerificationSerializer,
    PhoneLoginSerializer,
    UserProfileSerializer,
    UserListSerializer
)

logger = logging.getLogger(__name__)


# REGISTRATION FLOW
class SendOTPView(APIView):
    """Step 1: Send OTP for phone registration or login"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = OTPRequestSerializer(data=request.data)
        
        if serializer.is_valid():
            mobile_number = serializer.validated_data['mobile_number']
            otp = OTP.objects.create(mobile_number=mobile_number)
            sms_sent = self.send_sms(mobile_number, otp.otp_code)
            
            if sms_sent:
                return Response({
                    'success': True,
                    'message': f'OTP sent successfully to {mobile_number}',
                    'expires_in_minutes': getattr(settings, 'OTP_EXPIRY_MINUTES', 5)
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'message': 'Failed to send OTP. Please try again.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def send_sms(self, mobile_number, otp_code):
        try:
            logger.info(f"OTP for {mobile_number}: {otp_code}")
            print(f"📱 OTP for {mobile_number}: {otp_code}")
            return True
        except Exception as e:
            logger.error(f"SMS sending failed: {str(e)}")
            return False


class VerifyPhoneRegistrationView(APIView):
    """Step 2: Verify phone number and create basic user account"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = OTPVerificationSerializer(data=request.data)
        
        if serializer.is_valid():
            otp_instance = serializer.validated_data['otp_instance']
            mobile_number = serializer.validated_data['mobile_number']
            
            # Check if user already exists
            if CustomUser.objects.filter(mobile_number=mobile_number).exists():
                return Response({
                    'success': False,
                    'message': 'User with this mobile number already exists. Please login instead.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Mark OTP as verified
            otp_instance.is_verified = True
            otp_instance.save()
            
            # Create incomplete user account
            user = CustomUser.objects.create(
                mobile_number=mobile_number,
                registration_method='phone',
                is_mobile_verified=True,
                # These fields are empty and will be required in next step
                full_name='',
                user_type='',
                address='',
                city='',
                state='',
                pincode=''
            )
            user.set_unusable_password()
            user.save()
            
            return Response({
                'success': True,
                'message': 'Phone number verified successfully. Please complete your profile.',
                'user_id': user.id,
                'mobile_number': mobile_number,
                'next_step': 'complete_profile',
                'profile_complete': False
            }, status=status.HTTP_200_OK)
        
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class CompleteProfileView(APIView):
    """Step 3: Complete user profile after phone verification"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        mobile_number = request.data.get('mobile_number')
        
        if not mobile_number:
            return Response({
                'success': False,
                'message': 'Mobile number is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Clean and validate mobile number format
        import re
        cleaned_number = re.sub(r'[^\d+]', '', mobile_number)
        if cleaned_number.startswith('+91'):
            cleaned_number = cleaned_number[3:]
        elif cleaned_number.startswith('91'):
            cleaned_number = cleaned_number[2:]
        
        try:
            user = CustomUser.objects.get(mobile_number=cleaned_number)
        except CustomUser.DoesNotExist:
            return Response({
                'success': False,
                'message': 'User with this mobile number does not exist'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if mobile number is verified
        if not user.is_mobile_verified:
            return Response({
                'success': False,
                'message': 'Please verify your mobile number first'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if profile is already complete
        if user.is_profile_complete:
            return Response({
                'success': False,
                'message': 'Profile is already complete'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = ProfileCompletionSerializer(user, data=request.data)
        
        if serializer.is_valid():
            # No social linking during profile completion; linking happens via dedicated endpoint
            
            # Save the user profile
            serializer.save()
            
            # Generate token for the user after profile completion
            token, created = Token.objects.get_or_create(user=user)
            user_session = UserSession.objects.create(user=user)
            
            response_message = 'Profile completed successfully! You can now login.'
            return Response({
                'success': True,
                'message': response_message,
                'user': UserProfileSerializer(user).data,
                'token': token.key,
                'session_token': user_session.session_token,
                'profile_complete': user.is_profile_complete
            }, status=status.HTTP_200_OK)
        
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


# LOGIN FLOWS
class PhoneLoginView(APIView):
    """Login using phone number + OTP"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = PhoneLoginSerializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.validated_data['user']
            otp_instance = serializer.validated_data['otp_instance']
            
            # Mark OTP as verified
            otp_instance.is_verified = True
            otp_instance.save()
            
            # Update user login time
            user.last_login = timezone.now()
            user.save()
            
            # Create new session
            token, created = Token.objects.get_or_create(user=user)
            UserSession.objects.filter(user=user, is_active=True).update(is_active=False)
            user_session = UserSession.objects.create(user=user)
            
            return Response({
                'success': True,
                'message': 'Login successful',
                'user': UserProfileSerializer(user).data,
                'token': token.key,
                'session_token': user_session.session_token
            }, status=status.HTTP_200_OK)
        
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


# UTILITY VIEWS
class CheckUserExistsView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        mobile_number = request.data.get('mobile_number', '')
        email = request.data.get('email', '')
        
        if not mobile_number and not email:
            return Response({
                'success': False,
                'message': 'Mobile number or email is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        response_data = {'success': True}
        
        if mobile_number:
            import re
            cleaned_number = re.sub(r'[^\d+]', '', mobile_number)
            if cleaned_number.startswith('+91'):
                cleaned_number = cleaned_number[3:]
            elif cleaned_number.startswith('91'):
                cleaned_number = cleaned_number[2:]
            
            try:
                user = CustomUser.objects.get(mobile_number=cleaned_number)
                response_data.update({
                    'phone_user_exists': True,
                    'mobile_number': cleaned_number,
                    'profile_complete': user.is_profile_complete,
                    'can_login': user.is_profile_complete
                })
            except CustomUser.DoesNotExist:
                response_data.update({
                    'phone_user_exists': False,
                    'mobile_number': cleaned_number,
                    'can_register': True
                })
        
        if email:
            try:
                user = CustomUser.objects.get(email=email)
                response_data.update({
                    'email_user_exists': True,
                    'email': email,
                    'has_phone': bool(user.mobile_number),
                    'profile_complete': user.is_profile_complete
                })
            except CustomUser.DoesNotExist:
                response_data.update({
                    'email_user_exists': False,
                    'email': email
                })
        
        return Response(response_data, status=status.HTTP_200_OK)


class UserLogoutView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            request.user.auth_token.delete()
            UserSession.objects.filter(user=request.user, is_active=True).update(is_active=False)
            
            return Response({
                'success': True,
                'message': 'Logged out successfully'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'message': 'Logout failed'
            }, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        return self.request.user
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            'success': True,
            'user': serializer.data
        })
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        
        if serializer.is_valid():
            self.perform_update(serializer)
            return Response({
                'success': True,
                'message': 'Profile updated successfully',
                'user': serializer.data
            })
        
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class OAuthCallbackView(APIView):
    """Handle OAuth authorization code from frontend: exchange code for access token, get user info, create/return user and tokens"""
    permission_classes = [AllowAny]

    def post(self, request):
        provider = request.data.get('provider')
        code = request.data.get('code')
        redirect_uri = request.data.get('redirect_uri')

        if not provider or not code or not redirect_uri:
            return Response({'success': False, 'message': 'provider, code and redirect_uri are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if provider == 'google':
                token_data = self.exchange_google_code(code, redirect_uri)
                access_token = token_data.get('access_token')
                # fetch user info
                user_info = requests.get(
                    f'https://www.googleapis.com/oauth2/v1/userinfo?alt=json&access_token={access_token}'
                ).json()
                social_id = user_info.get('id')
                email = user_info.get('email')
                name = user_info.get('name') or f"{user_info.get('given_name','')} {user_info.get('family_name','')}".strip()
                provider_field = 'google'
            elif provider == 'facebook':
                token_data = self.exchange_facebook_code(code, redirect_uri)
                access_token = token_data.get('access_token')
                user_info = requests.get(
                    f'https://graph.facebook.com/me?access_token={access_token}&fields=id,name,email,first_name,last_name,picture'
                ).json()
                social_id = user_info.get('id')
                email = user_info.get('email')
                name = user_info.get('name')
                provider_field = 'facebook'
            else:
                return Response({'success': False, 'message': 'Unsupported provider'}, status=status.HTTP_400_BAD_REQUEST)

            # Find or create user
            # If the request is made by an authenticated user, treat this as a linking operation
            request_user = None
            try:
                if request.user and request.user.is_authenticated:
                    request_user = request.user
            except Exception:
                request_user = None

            if request_user:
                # Ensure the social id is not already linked to another account
                if provider_field == 'google':
                    existing = CustomUser.objects.filter(google_id=social_id).exclude(id=request_user.id).first()
                    if existing:
                        return Response({'success': False, 'message': 'This Google account is already linked to another user'}, status=status.HTTP_400_BAD_REQUEST)
                    request_user.google_id = social_id
                    request_user.registration_method = 'google'
                    # Optionally update email/name if empty
                    if not request_user.email and email:
                        if not CustomUser.objects.filter(email=email).exclude(id=request_user.id).exists():
                            request_user.email = email
                    if not request_user.full_name and name:
                        request_user.full_name = name
                    request_user.save()
                else:
                    existing = CustomUser.objects.filter(facebook_id=social_id).exclude(id=request_user.id).first()
                    if existing:
                        return Response({'success': False, 'message': 'This Facebook account is already linked to another user'}, status=status.HTTP_400_BAD_REQUEST)
                    request_user.facebook_id = social_id
                    request_user.registration_method = 'facebook'
                    if not request_user.email and email:
                        if not CustomUser.objects.filter(email=email).exclude(id=request_user.id).exists():
                            request_user.email = email
                    if not request_user.full_name and name:
                        request_user.full_name = name
                    request_user.save()

                # Return success for linking operation
                return Response({
                    'success': True,
                    'message': 'Social account linked successfully',
                    'linked': True,
                    'provider': provider,
                    'user': UserProfileSerializer(request_user).data
                }, status=status.HTTP_200_OK)

            # Otherwise, find or create user (existing login/registration flow)
            user = None
            if provider == 'google':
                user = CustomUser.objects.filter(google_id=social_id).first()
            else:
                user = CustomUser.objects.filter(facebook_id=social_id).first()

            if not user and email:
                # Try to find user by email
                user = CustomUser.objects.filter(email=email).first()

            if user:
                # Link social id if not linked
                if provider_field == 'google' and not user.google_id:
                    user.google_id = social_id
                    user.registration_method = 'google'
                    user.save()
                if provider_field == 'facebook' and not user.facebook_id:
                    user.facebook_id = social_id
                    user.registration_method = 'facebook'
                    user.save()
            else:
                # Create a new user
                username = None
                user = CustomUser(
                    full_name=name or '',
                    email=email or None,
                    registration_method=provider_field,
                )
                if provider_field == 'google':
                    user.google_id = social_id
                else:
                    user.facebook_id = social_id

                # set unusable password
                user.set_unusable_password()
                user.save()

            # If profile is complete, issue token and session (login)
            if user.is_profile_complete:
                token, _ = Token.objects.get_or_create(user=user)
                UserSession.objects.filter(user=user, is_active=True).update(is_active=False)
                user_session = UserSession.objects.create(user=user)

                return Response({
                    'success': True,
                    'message': 'OAuth login successful',
                    'user': UserProfileSerializer(user).data,
                    'token': token.key,
                    'session_token': user_session.session_token
                }, status=status.HTTP_200_OK)

            # If profile is incomplete, return next_step and provider access token so frontend can complete profile
            return Response({
                'success': True,
                'message': 'Profile incomplete',
                'user': UserProfileSerializer(user).data,
                'next_step': 'complete_profile',
                'provider': provider,
                'provider_access_token': access_token
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception('OAuth callback error')
            # If the exception carries provider response details, include them in the response for debugging
            message = str(e)
            return Response({'success': False, 'message': message}, status=status.HTTP_400_BAD_REQUEST)

    def exchange_google_code(self, code, redirect_uri):
        data = {
            'code': code,
            'client_id': getattr(settings, 'GOOGLE_OAUTH2_CLIENT_ID', ''),
            'client_secret': getattr(settings, 'GOOGLE_OAUTH2_CLIENT_SECRET', ''),
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code'
        }
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        resp = requests.post('https://oauth2.googleapis.com/token', data=data, headers=headers)
        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            # Attach response body for easier debugging
            body = resp.text
            logger.error('Google token exchange failed: %s', body)
            raise requests.HTTPError(f'{e} - response body: {body}')
        return resp.json()

    def exchange_facebook_code(self, code, redirect_uri):
        params = {
            'client_id': getattr(settings, 'FACEBOOK_APP_ID', ''),
            'client_secret': getattr(settings, 'FACEBOOK_APP_SECRET', ''),
            'redirect_uri': redirect_uri,
            'code': code
        }
        resp = requests.get('https://graph.facebook.com/v18.0/oauth/access_token', params=params)
        resp.raise_for_status()
        return resp.json()


class OAuthTokenView(APIView):
    """Exchange authorization code for provider access token (used if frontend prefers server-side exchange)"""
    permission_classes = [AllowAny]

    def post(self, request):
        provider = request.data.get('provider')
        code = request.data.get('code')
        redirect_uri = request.data.get('redirect_uri')

        if not provider or not code or not redirect_uri:
            return Response({'success': False, 'message': 'provider, code and redirect_uri are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if provider == 'google':
                data = {
                    'code': code,
                    'client_id': getattr(settings, 'GOOGLE_OAUTH2_CLIENT_ID', ''),
                    'client_secret': getattr(settings, 'GOOGLE_OAUTH2_CLIENT_SECRET', ''),
                    'redirect_uri': redirect_uri,
                    'grant_type': 'authorization_code'
                }
                resp = requests.post('https://oauth2.googleapis.com/token', data=data)
                resp.raise_for_status()
                return Response(resp.json(), status=status.HTTP_200_OK)

            elif provider == 'facebook':
                params = {
                    'client_id': getattr(settings, 'FACEBOOK_APP_ID', ''),
                    'client_secret': getattr(settings, 'FACEBOOK_APP_SECRET', ''),
                    'redirect_uri': redirect_uri,
                    'code': code
                }
                resp = requests.get('https://graph.facebook.com/v18.0/oauth/access_token', params=params)
                resp.raise_for_status()
                return Response(resp.json(), status=status.HTTP_200_OK)

            else:
                return Response({'success': False, 'message': 'Unsupported provider'}, status=status.HTTP_400_BAD_REQUEST)

        except requests.HTTPError as e:
            logger.exception('Token exchange failed')
            return Response({'success': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class LinkSocialView(APIView):
    """Link a social account (google/facebook) to the authenticated user using provider access token"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        provider = request.data.get('provider')
        access_token = request.data.get('access_token')

        if not provider or not access_token:
            return Response({'success': False, 'message': 'provider and access_token are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if provider == 'google':
                # fetch userinfo
                user_info = requests.get(f'https://www.googleapis.com/oauth2/v1/userinfo?alt=json&access_token={access_token}').json()
                social_id = user_info.get('id')
                email = user_info.get('email')
                name = user_info.get('name')

                # check if already linked to another user
                existing = CustomUser.objects.filter(google_id=social_id).exclude(id=request.user.id).first()
                if existing:
                    return Response({'success': False, 'message': 'This Google account is already linked to another user'}, status=status.HTTP_400_BAD_REQUEST)

                request.user.google_id = social_id
                if not request.user.email and email:
                    if not CustomUser.objects.filter(email=email).exclude(id=request.user.id).exists():
                        request.user.email = email
                if not request.user.full_name and name:
                    request.user.full_name = name
                request.user.save()

            elif provider == 'facebook':
                user_info = requests.get(f'https://graph.facebook.com/me?access_token={access_token}&fields=id,name,email').json()
                social_id = user_info.get('id')
                email = user_info.get('email')
                name = user_info.get('name')

                existing = CustomUser.objects.filter(facebook_id=social_id).exclude(id=request.user.id).first()
                if existing:
                    return Response({'success': False, 'message': 'This Facebook account is already linked to another user'}, status=status.HTTP_400_BAD_REQUEST)

                request.user.facebook_id = social_id
                if not request.user.email and email:
                    if not CustomUser.objects.filter(email=email).exclude(id=request.user.id).exists():
                        request.user.email = email
                if not request.user.full_name and name:
                    request.user.full_name = name
                request.user.save()

            else:
                return Response({'success': False, 'message': 'Unsupported provider'}, status=status.HTTP_400_BAD_REQUEST)

            return Response({'success': True, 'message': 'Social account linked', 'user': UserProfileSerializer(request.user).data}, status=status.HTTP_200_OK)

        except requests.HTTPError as e:
            logger.exception('Link social failed')
            return Response({'success': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_dashboard(request):
    user = request.user
    
    dashboard_data = {
        'user_info': UserProfileSerializer(user).data,
        'user_type_display': user.get_user_type_display(),
    }
    
    if user.user_type == 'smart_buyer':
        dashboard_data['buyer_category_display'] = user.get_buyer_category_display()
    
    return Response({
        'success': True,
        'dashboard': dashboard_data
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def user_statistics(request):
    total_users = CustomUser.objects.count()
    smart_sellers = CustomUser.objects.filter(user_type='smart_seller').count()
    smart_buyers = CustomUser.objects.filter(user_type='smart_buyer').count()
    verified_users = CustomUser.objects.filter(is_mobile_verified=True).count()
    complete_profiles = CustomUser.objects.filter(is_profile_complete=True).count()
    
    buyer_categories = CustomUser.objects.filter(user_type='smart_buyer')
    mandi_owners = buyer_categories.filter(buyer_category='mandi_owner').count()
    shopkeepers = buyer_categories.filter(buyer_category='shopkeeper').count()
    communities = buyer_categories.filter(buyer_category='community').count()
    
    return Response({
        'success': True,
        'statistics': {
            'total_users': total_users,
            'smart_sellers': smart_sellers,
            'smart_buyers': smart_buyers,
            'verified_users': verified_users,
            'complete_profiles': complete_profiles,
            'buyer_breakdown': {
                'mandi_owners': mandi_owners,
                'shopkeepers': shopkeepers,
                'communities': communities
            }
        }
    })