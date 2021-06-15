from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    SubmitField,
    PasswordField,
    TextAreaField,
    FileField,
    SelectField,
)
from wtforms.validators import DataRequired, Email, ValidationError, Length, EqualTo
from flask_wtf.file import FileRequired


# WTForm
class CreatePostForm(FlaskForm):
    title = StringField("Blog Post Title", validators=[DataRequired()])
    subtitle = StringField("Subtitle")
    img_url = StringField("Blog Image URL")
    body = TextAreaField("Blog Content", validators=[DataRequired()])
    submit = SubmitField("Submit Post")


class RegisterForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8)])
    username = StringField("Name", validators=[DataRequired(), Length(max=25)])
    submit = SubmitField("SIGN ME UP!")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("LET ME IN!")


class ChangePasswordForm(FlaskForm):
    last_password = PasswordField("Last Password", validators=[DataRequired()])
    new_password1 = PasswordField(
        "New Password", validators=[DataRequired(), Length(min=6)]
    )
    new_password2 = PasswordField(
        "Confirm New Password",
        validators=[
            DataRequired(),
            EqualTo("new_password1", "Password doesn't match."),
        ],
    )


class CommentForm(FlaskForm):
    comment_text = TextAreaField(
        "Comment",
        validators=[DataRequired()],
        render_kw={"class": "form-control", "rows": 5},
    )
    submit = SubmitField("SUBMIT COMMENT")


class ContactForm(FlaskForm):
    name = StringField(
        "Name",
        validators=[DataRequired()],
        render_kw={"class": "form-control", "placeholder": "Name"},
    )
    email = StringField(
        "Email Address",
        validators=[DataRequired(), Email()],
        render_kw={"class": "form-control", "placeholder": "Email Address"},
    )
    phone_number = StringField(
        "Phone Number",
        render_kw={"class": "form-control", "placeholder": "Phone Number"},
    )
    message = TextAreaField(
        "Message",
        validators=[DataRequired()],
        render_kw={"class": "form-control", "placeholder": "Message", "rows": 5},
    )
    submit = SubmitField("SEND")


class UploadImageForm(FlaskForm):
    file = FileField(
        "Opload an image", validators=[FileRequired()], render_kw={"accept": "image/*"}
    )
    submit = SubmitField("Upload")

    @staticmethod
    def validate_file(form, field):
        if not field.data.mimetype.startswith("image"):
            raise ValidationError("Invalid file type, image only.")


class UploadFileForm(FlaskForm):
    file = FileField("Opload a file", validators=[FileRequired()])
    submit = SubmitField("Upload")


class AddFriendForm(FlaskForm):
    name_search = StringField("Search for name", validators=[DataRequired()])
    friend_id = SelectField("Friend Name", validators=[DataRequired()])


class NewGroupForm(FlaskForm):
    group_name = StringField("Group Name", validators=[DataRequired(), Length(max=25)])
    group_member = SelectField("Friend Name", validators=[DataRequired()])


class AddMemberForm(FlaskForm):
    group_name = SelectField("Group Name", validators=[DataRequired()], default=None)
    group_member = SelectField("New Member Name")


class ProfileForm(FlaskForm):
    username = StringField("Name", validators=[DataRequired(), Length(max=25)])
    email = StringField("Email", validators=[DataRequired(), Email()])


class DeleteGroupForm(FlaskForm):
    group = SelectField(
        "Group Name", validators=[DataRequired()], default=None, coerce=int
    )


class SendEmailForm(FlaskForm):
    to_email = StringField("Send to Email", validators=[DataRequired(), Email()])
    subject = StringField("Subject", validators=[DataRequired()])
    message = TextAreaField("Message", validators=[DataRequired()])
