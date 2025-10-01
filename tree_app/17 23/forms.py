# tree_app/forms.py
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

User = get_user_model()

class SignupForm(UserCreationForm):
    class Meta:
        model = User
        # username & password fields come from UserCreationForm
        fields = ("username", "password1", "password2")
