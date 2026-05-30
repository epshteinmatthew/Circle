"""Circle Flask application and schema usage example."""
import json
from datetime import date, time

from flask import Flask, jsonify, request
from sqlmodel import select

from schema import (
    Event,
    EventCreate,
    Group,
    GroupCreate,
    User,
    UserCreate,
    create_event,
    create_group,
    create_user,
)
from schema.database import get_session, init_db

#todo: validation and refresh tokens

def get_user_with_email_and_name(name:str, email:str) -> User | None:
    try:
        with get_session() as session:
            user = session.exec(select(User).where(User.name == name and User.email == email)).first()
            session.commit()
            return user
    except:
        return None

app = Flask(__name__)
init_db()

@app.route("/")
def index() -> str:
    return "Circle — try /demo for a schema example (data in circle.db)"

#todo: google path
#this will do login and then split into either a sign up flow or give you your user
#to get your user you need name and email OR id
#these will always be the ones tied to the google account for simplicity's sake

#todo: augment this to some kind of sign-up flow
@app.route("/create_user", methods=['POST'])
def create_user_route():
    rdata = json.loads(request.json)
    try:
        with get_session() as session:
            new_user = create_user(UserCreate(name=rdata.name, email=rdata.email, availability=rdata.availability))
            same_name_and_email:User|None = session.exec(select(User).where(User.name == new_user.name and User.email == new_user.email)).first()
            if same_name_and_email:
                return "User creation failed: duplicate name and email", 409
            session.add(new_user)
            session.commit()
            return jsonify(new_user)
    except:
        return "something went wrong", 400

@app.route("/get_user_with_id", methods=['GET'])
def get_user_with_id():
    id_req = request.args['id']
    if not id_req:
        return "bad request", 400
    try:
        with get_session() as session:
            user = session.exec(select(User).where(User.id == id_req)).first()
            session.commit()
            return jsonify(user)
    except:
        return "something went wrong", 400



if __name__ == "__main__":
    app.run(debug=True)
