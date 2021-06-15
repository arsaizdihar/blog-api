from flask import Flask, Blueprint
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from config import BaseConfig
from models import db, User
from api import api
import wtforms_json

app = Flask(__name__)
jwt = JWTManager(app)
app.config.from_object(BaseConfig)
app.register_blueprint(api, url_prefix="/api")
db.init_app(app)
cors = CORS(app)
wtforms_json.init()

with app.app_context():
    db.create_all()


@jwt.user_identity_loader
def user_identity_lookup(user):
    return user.id


@jwt.user_lookup_loader
def user_lookup_callback(_jwt_header, jwt_data):
    identity = jwt_data["sub"]
    return User.query.filter_by(id=identity).one_or_none()


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
