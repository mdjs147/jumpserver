from rest_framework.generics import CreateAPIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.utils.translation import ugettext as _
from django.template.loader import render_to_string

from common.utils.verify_code import SendAndVerifyCodeUtil
from common.permissions import IsValidUser
from common.utils.random import random_string
from common.utils import get_object_or_none
from authentication.serializers import (
    PasswordVerifySerializer, ResetPasswordCodeSerializer
)
from settings.utils import get_login_title
from users.models import User
from authentication.mixins import authenticate
from authentication.errors import PasswordInvalid
from authentication.mixins import AuthMixin


class UserResetPasswordSendCodeApi(CreateAPIView):
    permission_classes = (AllowAny,)
    serializer_class = ResetPasswordCodeSerializer

    @staticmethod
    def is_valid_user( **kwargs):
        user = get_object_or_none(User, **kwargs)
        if not user:
            err_msg = _('User does not exist: {}').format(_("No user matched"))
            return None, err_msg
        if not user.is_local:
            err_msg = _(
                'The user is from {}, please go to the corresponding system to change the password'
            ).format(user.get_source_display())
            return None, err_msg
        return user, None

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        form_type = serializer.validated_data['form_type']
        username = serializer.validated_data['username']
        code = random_string(6, lower=False, upper=False)
        other_args = {}

        if form_type == 'phone':
            backend = 'sms'
            target = serializer.validated_data['phone']
            user, err = self.is_valid_user(username=username, phone=target)
            if not user:
                return Response({'error': err}, status=400)
        else:
            backend = 'email'
            target = serializer.validated_data['email']
            user, err = self.is_valid_user(username=username, email=target)
            if not user:
                return Response({'error': err}, status=400)

            subject = '%s: %s' % (get_login_title(), _('Forgot password'))
            context = {
                'user': user, 'title': subject, 'code': code,
            }
            message = render_to_string('authentication/_msg_reset_password_code.html', context)
            other_args['subject'] = subject
            other_args['message'] = message

        SendAndVerifyCodeUtil(target, code, backend=backend, **other_args).gen_and_send_async()
        return Response({'data': 'ok'}, status=200)


class UserPasswordVerifyApi(AuthMixin, CreateAPIView):
    permission_classes = (IsValidUser,)
    serializer_class = PasswordVerifySerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        password = serializer.validated_data['password']
        user = self.request.user

        user = authenticate(request=request, username=user.username, password=password)
        if not user:
            raise PasswordInvalid

        self.mark_password_ok(user)
        return Response()
