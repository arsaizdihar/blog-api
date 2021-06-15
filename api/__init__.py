from flask import Blueprint, request, jsonify, abort
from http import HTTPStatus
from functools import wraps
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    current_user,
    create_refresh_token,
    current_user,
)
from flask_cors import cross_origin
from models import db, User, BlogPost, Comment, Contact
from forms import RegisterForm, LoginForm, CommentForm, ContactForm, CreatePostForm
from datetime import datetime, timedelta
import re
import os

api = Blueprint("api", __name__)


def get_jkt_timezone():
    utc = datetime.utcnow()
    return utc + timedelta(hours=7)


def row2dict(row, hidden_column=[]):
    d = {}
    for column in row.__table__.columns:
        if column.name not in hidden_column:
            d[column.name] = str(getattr(row, column.name))

    return d


def check_admin():
    admin_ids = [1, 2]
    if current_user:
        if current_user.id in admin_ids:
            return True
        return False
    return False


def admin_only(f):
    @wraps(f)
    def wrapped_function(*args, **kwargs):
        if check_admin():
            return f(*args, **kwargs)
        return abort(HTTPStatus.UNAUTHORIZED)

    return wrapped_function


def get_form(form_class):
    data = request.form
    if not data:
        data = request.json
        form = form_class.from_json(data)
    else:
        form = form_class(data)
    return form


@api.route("auth/sign-up", methods=["POST"])
@cross_origin()
def sign_up():
    form = get_form(RegisterForm)
    if not form.validate():
        return {"error": form.errors}, HTTPStatus.BAD_REQUEST
    username = form.username.data
    email = form.email.data
    password = form.password.data
    new_user = User(username, email, password)
    access_token = create_access_token(identity=new_user)
    refresh_token = create_refresh_token(identity=new_user)
    response = jsonify(
        {
            "success": "User created",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": row2dict(new_user, ["password", "is_online"]),
        }
    )
    db.session.add(new_user)
    db.session.commit()
    return response, HTTPStatus.OK


@api.route("auth/login", methods=["POST", "GET"])
@cross_origin()
def login():
    form = get_form(LoginForm)
    if not form.validate():
        return {"error": form.errors}, HTTPStatus.BAD_REQUEST
    user = User.query.filter_by(email=form.email.data).first()
    if not user or not user.check_password(form.password.data):
        return {"error": "Email or password is wrong."}, HTTPStatus.UNAUTHORIZED
    access_token = create_access_token(identity=user)
    refresh_token = create_refresh_token(identity=user)
    response = jsonify(
        success="login success",
        access_token=access_token,
        refresh_token=refresh_token,
        user=row2dict(user, ["password", "is_online"]),
    )
    return response, HTTPStatus.OK


@api.route("auth/get-user")
@cross_origin()
@jwt_required()
def get_user_data():
    return jsonify(username=current_user.name, email=current_user.email), HTTPStatus.OK


@api.route("auth/refresh", methods=["POST"])
@jwt_required(refresh=True)
@cross_origin()
def refresh():
    access_token = create_access_token(identity=current_user)
    return jsonify(access_token=access_token)


@api.route("/home/title", methods=["GET"])
@cross_origin()
def get_home_title():
    img_url = os.environ.get(
        "HOME_IMG_URL",
        "https://images.unsplash.com/photo-1519681393784-d120267933ba?ixid=MXwxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHw%3D&ixlib=rb-1.2.1&auto=format&fit=crop&w=1950&q=80",
    )
    heading = os.environ.get("HOME_HEADING", "Personal Blog of Arsa")
    subheading = os.environ.get("HOME_SUBHEADING", "test")
    return jsonify(img_url=img_url, heading=heading, subheading=subheading)


@api.route("/home/posts", methods=["GET"])
@jwt_required(True)
@cross_origin()
def get_all_posts():
    posts = BlogPost.query.order_by(BlogPost.id.desc()).all()
    if posts:
        del posts[-1]
    if not check_admin():
        posts = [post for post in posts if not post.hidden]
    posts_list = []
    for post in posts:
        data = row2dict(post, hidden_column=["hidden", "author_id", "body", "img_url"])
        data["author"] = post.author.name
        posts_list.append(data)
    return jsonify(posts=posts_list)


@api.route("/post", methods=["GET"])
@jwt_required(True)
@cross_origin()
def get_post():
    id = request.args.get("id")
    if not id:
        return jsonify(error="invalid request"), HTTPStatus.BAD_REQUEST
    if id == 1:
        return jsonify(error="id invalid"), HTTPStatus.NOT_FOUND
    requested_post = BlogPost.query.get_or_404(id)
    if not check_admin():
        if requested_post.hidden:
            return jsonify(error="id invalid"), HTTPStatus.NOT_FOUND
        if not requested_post.views:
            requested_post.views = 0
        requested_post.views += 1
        db.session.commit()
    response = row2dict(requested_post, hidden_column=["hidden"])
    response["comments"] = []
    for comment in requested_post.comments:
        data = {}
        data["author"] = comment.comment_author.get_safe_dict()
        data["text"] = comment.text
        response["comments"].append(data)
    return response


@api.route("/post", methods=["POST"])
@cross_origin()
@jwt_required()
@admin_only
def create_post():
    form = get_form(CreatePostForm)
    if not form.validate():
        return jsonify(error=form.errors), HTTPStatus.BAD_REQUEST
    title = form.title.data
    subtitle = form.subtitle.data
    img_url = form.img_url.data
    body = form.body.data
    new_post = BlogPost(
        title=title,
        subtitle=subtitle,
        img_url=img_url,
        body=body,
        author=current_user,
        date=get_jkt_timezone().strftime("%B %d, %Y"),
        views=0,
    )
    db.session.add(new_post)
    db.session.commit()
    return jsonify(id=new_post.id)


@api.route("/post", methods=["PUT"])
@cross_origin()
@jwt_required()
def edit_post():
    if request.json:
        requested_post = BlogPost.query.get(request.json.get("id"))
        if not requested_post or not requested_post.author == current_user:
            return jsonify(error="invalid request"), HTTPStatus.BAD_REQUEST
    elif request.form:
        requested_post = BlogPost.query.get(request.form.get("id"))
        if not requested_post or not requested_post.author == current_user:
            return jsonify(error="invalid request"), HTTPStatus.BAD_REQUEST
    else:
        return jsonify(error="invalid request"), HTTPStatus.BAD_REQUEST

    form = get_form(CreatePostForm)
    if not form.validate():
        return jsonify(error=form.errors), HTTPStatus.BAD_REQUEST
    requested_post.title = form.title.data
    requested_post.subtitle = form.subtitle.data
    requested_post.img_url = form.img_url.data
    requested_post.body = form.body.data
    db.session.commit()
    return jsonify(success="success")


@api.route("post/can-edit/<int:id>")
@cross_origin()
@jwt_required()
def post_can_edit(id):
    requested_post = BlogPost.query.get(id)
    if not requested_post:
        return jsonify(error="No post found"), HTTPStatus.BAD_REQUEST
    if not requested_post.author == current_user:
        return jsonify(error="no access to edit post"), HTTPStatus.UNAUTHORIZED
    return jsonify(success=True)


@api.route("/post/comment", methods=["POST"])
@cross_origin()
@jwt_required()
def comment_post():
    id = request.args.get("id")
    if not id:
        return jsonify(error="invalid request"), HTTPStatus.BAD_REQUEST
    form = get_form(CommentForm)
    if not form.validate():
        return jsonify(error=form.errors), HTTPStatus.BAD_REQUEST
    comment = Comment(author_id=current_user.id, post_id=id, text=form.text.data)
    db.session.add(comment)
    db.session.commit()
    return jsonify(success="comment success")


@api.route("/about")
@cross_origin()
def about():
    post = BlogPost.query.get(1)
    return row2dict(post, ["hidden", "id", "author_id"])


@api.route("/contact", methods=["POST"])
@cross_origin()
def contact():
    form = get_form(ContactForm)
    if not form.validate():
        return jsonify(error=form.errors), HTTPStatus.BAD_REQUEST
    name = form.name.data
    email = form.email.data
    phone_number = form.phone_number.data
    message = form.message.data
    time = get_jkt_timezone()
    new_contact = Contact(
        name=name, email=email, phone_number=phone_number, message=message, time=time
    )
    db.session.add(new_contact)
    db.session.commit()
    return jsonify(success="Message sent successfully.")
