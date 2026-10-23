from unfold.forms import UserChangeForm as BaseUserChangeForm
from unfold.forms import UserCreationForm as BaseUserCreationForm

from .models import User


class UserCreationForm(BaseUserCreationForm):
    class Meta:
        model = User
        fields = ["email", "phone_number", "role"]


class UserChangeForm(BaseUserChangeForm):
    class Meta:
        model = User
        fields = "__all__"
