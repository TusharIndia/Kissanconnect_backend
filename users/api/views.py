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
            # Check for social account linking
            google_data = serializer.validated_data.pop('google_user_data', None)
            facebook_data = serializer.validated_data.pop('facebook_user_data', None)
            
            # Link social accounts if data was provided
            if google_data:
                # Check if Google account is already linked to another user
                existing_google_user = CustomUser.objects.filter(google_id=google_data['id']).exclude(id=user.id).first()
                if existing_google_user:
                    return Response({
                        'success': False,
                        'message': 'This Google account is already linked to another user'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                user.google_id = google_data['id']
                # Update email if not set and Google email is available
                if not user.email and google_data.get('email'):
                    # Check if email is already taken by another user
                    if not CustomUser.objects.filter(email=google_data['email']).exclude(id=user.id).exists():
                        user.email = google_data['email']
                # Pre-fill name if not set
                if not user.full_name and google_data.get('name'):
                    user.full_name = google_data['name']
                user.save()
            
            if facebook_data:
                # Check if Facebook account is already linked to another user
                existing_facebook_user = CustomUser.objects.filter(facebook_id=facebook_data['id']).exclude(id=user.id).first()
                if existing_facebook_user:
                    return Response({
                        'success': False,
                        'message': 'This Facebook account is already linked to another user'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                user.facebook_id = facebook_data['id']
                # Update email if not set and Facebook email is available
                if not user.email and facebook_data.get('email'):
                    # Check if email is already taken by another user
                    if not CustomUser.objects.filter(email=facebook_data['email']).exclude(id=user.id).exists():
                        user.email = facebook_data['email']
                # Pre-fill name if not set
                if not user.full_name and facebook_data.get('name'):
                    user.full_name = facebook_data['name']
                user.save()
            
            # Save the user profile
            serializer.save()
            
            # Generate token for the user after profile completion
            token, created = Token.objects.get_or_create(user=user)
            user_session = UserSession.objects.create(user=user)
            
            response_message = 'Profile completed successfully! You can now login.'
            if google_data or facebook_data:
                linked_accounts = []
                if google_data:
                    linked_accounts.append('Google')
                if facebook_data:
                    linked_accounts.append('Facebook')
                response_message += f' {", ".join(linked_accounts)} account(s) linked successfully.'
            
            return Response({
                'success': True,
                'message': response_message,
                'user': UserProfileSerializer(user).data,
                'token': token.key,
                'session_token': user_session.session_token,
                'profile_complete': user.is_profile_complete,
                'social_accounts_linked': {
                    'google': bool(user.google_id),
                    'facebook': bool(user.facebook_id)
                }
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