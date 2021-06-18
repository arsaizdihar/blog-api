from flask_socketio import (
    SocketIO,
    send,
    emit,
    ConnectionRefusedError,
    join_room,
    leave_room,
)
from flask_jwt_extended import jwt_required, current_user
from models import db, ChatRoom, RoomRead, Chat, User, Image
from flask import request
from datetime import datetime
from ..chat.util import *
import io

socketio = SocketIO(cors_allowed_origins="*")


@socketio.on("connect")
@jwt_required()
def socket_connect():
    current_user.is_online = True
    add_socket_user(request.sid, current_user.id)
    rooms = []
    for assoc in current_user.chat_rooms:
        assoc.is_to_email = False
        room = assoc.chat_room
        room_name = assoc.room_name
        num_unread = 0
        for chat in room.chats:
            if chat:
                if chat.time and assoc.last_read:
                    if timestamp_get_datetime(chat.time) > timestamp_get_datetime(
                        assoc.last_read
                    ):
                        num_unread += 1
        if num_unread == 0:
            assoc.is_read = True
        rooms.append(
            {
                "room_id": room.id,
                "name": room_name,
                "is_read": assoc.is_read,
                "num_unread": num_unread,
            }
        )
    emit("rooms", rooms)
    if not current_user.id == 1:
        message = f"{current_user.name} connected at {get_timestamp()}"
        chat = Chat(message=message, user_id=2, room_id=1)
        db.session.add(chat)
        emit("message", {"msg": message, "time_stamp": get_timestamp()}, room="1")
    emit("socket_id", request.sid)
    db.session.commit()


@socketio.on("disconnect")
def socket_disconnect():
    user = get_user_from_sid(request.sid)
    if user:
        user.is_online = False
        db.session.commit()
        remove_socket_user(request.sid)
        print(user.name, "disconnected.")


@socketio.on("message")
def on_message(data):
    """Broadcast messages"""
    user = get_user_from_sid(request.sid)
    msg = escape_input(data["msg"])
    username = user.name
    room_id = str(data["room"]["room_id"])

    chat_room = ChatRoom.query.get(room_id)
    chat = Chat(message=msg, time=get_timestamp(), user=user, room=chat_room)
    modified_update(chat_room)
    for assoc in chat_room.members:
        assoc.is_read = assoc.user_id == user.id
    db.session.add(chat)
    emit(
        "message",
        {
            "username": username,
            "msg": msg,
            "time": get_timestamp(),
            "id": request.sid,
        },
        room=room_id,
    )
    notify_chat(socketio, int(room_id))
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
def read_callback(data):
    assoc = RoomRead.query.filter_by(
        room_id=data, user_id=get_user_id(request.sid)
    ).first()
    assoc.is_read = True
    assoc.last_read = get_timestamp()
    db.session.commit()


@socketio.on("join")
def on_join(data):
    """User joins a room"""
    user_id = get_user_id(request.sid)
    room_id = str(data["room_id"])
    join_room(room_id)
    room = ChatRoom.query.get(room_id)
    assoc = RoomRead.query.filter_by(user_id=user_id, room_id=room_id).first()
    assoc.is_read = True
    assoc.last_read = get_timestamp()
    db.session.commit()
    chats = room.chats
    chat_list = []
    for chat in chats:
        chat_dict = {
            "msg": chat.message,
            "time": chat.time,
            "is_user": chat.user_id == user_id,
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
def on_leave(data):
    """User leaves a room"""
    room_id = str(data["room_id"])
    leave_room(room_id)
    # print(data)


@socketio.on("upload-img")
def upload_image(data):
    print(data)
