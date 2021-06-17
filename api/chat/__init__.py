from flask_socketio import (
    SocketIO,
    send,
    emit,
    ConnectionRefusedError,
    join_room,
    leave_room,
)
from flask_jwt_extended import jwt_required, current_user
from util import get_jkt_timezone, row2dict
from models import db, ChatRoom, RoomRead, Chat
from flask import session
from uuid import uuid4

socketio = SocketIO(cors_allowed_origins="*")


def modified_update(room=None, commit=False):
    today = get_jkt_timezone().strftime("%Y-%m-%d %H:%M:%S:%f")
    if room:
        room.last_modified = today
        for assoc in room.members:
            assoc.last_modified = today
        if commit:
            db.session.commit()
    return today


def timestamp_get_datetime(timestamp):
    return datetime.strptime(timestamp, "%b-%d %I:%M%p")


def room_get_members(room):
    return [assoc.member for assoc in room.members]


def user_get_rooms(user):
    return [assoc.chat_room for assoc in user.chat_rooms]


def get_timestamp():
    # Set timestamp
    today = get_jkt_timezone()
    return today.strftime("%b-%d %I:%M%p")


def escape_input(msg):
    result = ""
    for char in msg:
        if not 767 < ord(char) < 880:
            result += char
    return result


def make_room_read(
    room=None,
    user=None,
    users=None,
    user_id=None,
    room_id=None,
    commit=False,
    name=False,
):
    timestamp = get_timestamp()
    time = modified_update()
    if room and user:
        a = RoomRead(last_modified=time, last_read=timestamp)
        a.member = user
        a.chat_room = room
        if name:
            a.room_name = name
        else:
            for assoc in room.members:
                if not assoc.member == user:
                    a.room_name = assoc.member.name
        db.session.add(a)
    elif room_id and user_id:
        a = RoomRead(last_modified=time, last_read=timestamp)
        user = User.query.get(user_id)
        room = ChatRoom.query.get(room_id)
        a.member = user
        a.chat_room = room
        if room.is_group:
            a.room_name = room.name
        else:
            a.room_name = RoomRead.query.filter(
                (RoomRead.room_id == room_id and not RoomRead.user_id == user_id)
            ).member.name
        db.session.add(a)
    elif room and users:
        for i in range(len(users)):
            a = RoomRead(last_modified=time, last_read=timestamp)
            a.member = users[i]
            a.chat_room = room
            if room.is_group:
                a.room_name = room.name
            else:
                if i == 0:
                    a.room_name = users[1].name
                else:
                    a.room_name = users[0].name
            db.session.add(a)
    if commit:
        db.session.commit()


def delete_group_from_db(room, commit=False):
    assocs = room.members
    for assoc in assocs:
        db.session.delete(assoc)
    db.session.delete(room)
    for chat in room.chats:
        if chat.is_image:
            filename = chat.message.split("/")[-1]
            image = Image.query.filter_by(filename=filename).first()
            if image:
                db.session.delete(image)
        db.session.delete(chat)
    if commit:
        db.session.commit()


def JPEGSaveWithTargetSize(im, target):
    """Save the image as JPEG with the given name at best quality that makes less than "target" bytes"""
    Qmin, Qmax = 15, 50
    im = im.convert("RGB")
    while Qmin <= Qmax:
        m = math.floor((Qmin + Qmax) / 2)
        buffer = io.BytesIO()

        im.save(buffer, format="JPEG", quality=m)
        s = buffer.getbuffer().nbytes
        print(s)
        if s <= target:
            break
        elif s > target:
            Qmax = m - 1
    return buffer.getvalue()


@socketio.on("connect")
@jwt_required()
def socket_connect():
    try:
        if not current_user:
            raise ConnectionRefusedError("Login First")
    except Exception:
        raise ConnectionRefusedError("Login First")
    current_user.is_online = True
    db.session.commit()
    emit("rooms", [row2dict(room) for room in current_user.chat_rooms])
    session_id = str(uuid4())
    session["id"] = session_id
    emit("socket_id", session_id)


@socketio.on("disconnect")
@jwt_required()
def socket_disconnect():
    current_user.is_online = False
    db.session.commit()
    print(current_user.name, "disconnected.")


@socketio.on("message")
@jwt_required()
def on_message(data):
    """Broadcast messages"""
    msg = escape_input(data["msg"])
    username = current_user.name
    room_id = data["room"]["room_id"]
    socketio.emit("notify_chat", {"room_id": room_id})
    chat_room = ChatRoom.query.get(room_id)
    chat = Chat(message=msg, time=get_timestamp(), user=current_user, room=chat_room)
    modified_update(chat_room)
    for assoc in chat_room.members:
        assoc.is_read = False
    db.session.add(chat)
    send(
        {
            "username": username,
            "msg": msg,
            "time": get_timestamp(),
            "id": session["id"],
        },
        room=room_id,
    )
    # for assoc in chat_room.members:
    #     if not assoc.member == current_user:
    #         if not assoc.member.is_online and not assoc.is_to_email:
    #             send_email(
    #                 assoc.member.email,
    #                 f"New chat from {username}",
    #                 f"{username}:\t{msg}\nCheck more at https://www.arsaiz.com/chat",
    #             )
    #             print(f"Sent email to {assoc.member.name}")
    #             assoc.is_to_email = True
    db.session.commit()


@socketio.on("read")
@jwt_required()
def read_callback(data):
    assoc = RoomRead.query.filter_by(
        room_id=data["room_id"], user_id=current_user.id
    ).first()
    assoc.is_read = True
    assoc.last_read = get_timestamp()
    db.session.commit()


@socketio.on("join")
@jwt_required()
def on_join(data):
    """User joins a room"""
    room_id = data["room_id"]
    join_room(room_id)
    room = ChatRoom.query.get(room_id)
    assoc = RoomRead.query.filter_by(user_id=current_user.id, room_id=room_id).first()
    assoc.is_read = True
    assoc.last_read = get_timestamp()
    db.session.commit()
    chats = room.chats
    chat_list = []
    for chat in chats:
        chat_dict = {
            "msg": chat.message,
            "time": chat.time,
            "is_user": chat.user == current_user,
            "username": chat.user.name,
            "is_image": chat.is_image,
        }
        chat_list.append(chat_dict)
    if room.is_group:
        chat_list.append(
            {
                "msg": chats[0].message,
                "time": chats[0].time,
                "is_user": False,
                "username": "Server",
            }
        )
    # Broadcast that new user has joined
    emit("show_history", {"chats": chat_list})


@socketio.on("leave")
@jwt_required()
def on_leave(data):
    """User leaves a room"""
    room_id = data["room_id"]
    leave_room(room_id)
    # print(data)


@socketio.on("upload-img")
@jwt_required()
def upload_image(data):
    print(data)
