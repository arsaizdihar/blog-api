from flask_socketio import (
    SocketIO,
    send,
    emit,
    ConnectionRefusedError,
    join_room,
    leave_room,
    rooms,
)
from flask_jwt_extended import jwt_required, current_user
from models import db, ChatRoom, RoomRead, Chat, User, Image
from flask import request
from datetime import datetime
from ..chat import util
import io

socketio = SocketIO(cors_allowed_origins="*")


@socketio.on("connect", namespace="/chat")
@jwt_required()
def socket_connect():
    current_user.is_online = True
    util.add_socket_user(request.sid, current_user.id)
    rooms = []
    for assoc in current_user.chat_rooms:
        assoc.is_to_email = False
        room = assoc.chat_room
        room_name = assoc.room_name
        num_unread = 0
        for chat in room.chats:
            if chat:
                if chat.time and assoc.last_read:
                    if util.timestamp_get_datetime(
                        chat.time
                    ) > util.timestamp_get_datetime(assoc.last_read):
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
        message = f"{current_user.name} connected at {util.get_timestamp()}"
        chat = Chat(message=message, user_id=2, room_id=1)
        db.session.add(chat)
        emit("message", {"msg": message, "time_stamp": util.get_timestamp()}, room="1")
    emit("socket_id", request.sid)
    db.session.commit()


@socketio.on("disconnect", namespace="/chat")
def socket_disconnect():
    user = util.get_user_from_sid(request.sid)
    if user:
        user.is_online = False
        db.session.commit()
        util.remove_socket_user(request.sid)
        print(user.name, "disconnected.")


@socketio.on("message", namespace="/chat")
def on_message(data):
    """Broadcast messages"""
    user = util.get_user_from_sid(request.sid)
    msg = util.escape_input(data["msg"])
    username = user.name
    room_id = str(data["room"]["room_id"])

    chat_room = ChatRoom.query.get(room_id)
    chat = Chat(message=msg, time=util.get_timestamp(), user=user, room=chat_room)
    util.modified_update(chat_room)
    for assoc in chat_room.members:
        assoc.is_read = assoc.user_id == user.id
    db.session.add(chat)
    emit(
        "message",
        {
            "username": username,
            "msg": msg,
            "time": util.get_timestamp(),
            "id": request.sid,
        },
        room=room_id,
    )
    util.notify_chat(socketio, int(room_id))
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


@socketio.on("read", namespace="/chat")
def read_callback(data):
    assoc = RoomRead.query.filter_by(
        room_id=data, user_id=util.get_user_id(request.sid)
    ).first()
    assoc.is_read = True
    assoc.last_read = util.get_timestamp()
    db.session.commit()


@socketio.on("join", namespace="/chat")
def on_join(data):
    """User joins a room"""
    user_id = util.get_user_id(request.sid)
    room_id = str(data["room_id"])
    join_room(room_id)
    room = ChatRoom.query.get(room_id)
    assoc = RoomRead.query.filter_by(user_id=user_id, room_id=room_id).first()
    assoc.is_read = True
    assoc.last_read = util.get_timestamp()
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


@socketio.on("leave", namespace="/chat")
def on_leave(data):
    """User leaves a room"""
    room_id = str(data["room_id"])
    leave_room(room_id)
    # print(data)


@socketio.on("upload-img", namespace="/chat")
def upload_image(data):
    print(data)


@socketio.on("connect", namespace="/call")
@jwt_required()
def connect_call():
    print(current_user.name, "connected to call")
    util.add_call_user(request.sid, current_user.id)
    emit("socket_id", request.sid)
    friends_online = util.get_call_friends_online(request.sid)
    emit("friends_online", friends_online)
    for friend in util.get_call_friends_online(request.sid):
        emit(
            "friend_online",
            {"sid": request.sid, "name": current_user.name},
            room=friend["sid"],
        )


@socketio.on("call_user", namespace="/call")
def socket_call_user(data):
    user = util.get_call_user(request.sid)
    emit(
        "call_user",
        {"from": request.sid, "name": user.name, "signal": data["signal"]},
        room=data["user_to_call"],
    )


@socketio.on("answer_call", namespace="/call")
def socket_answer_call(data):
    print("answered")
    emit("call_accepted", data["signal"], room=data["to"])


@socketio.on("disconnect", namespace="/call")
def disconnect_call():
    friends_online = util.get_call_friends_online(request.sid)
    for friend in friends_online:
        emit("friend_offline", request.sid, room=friend["sid"])
    util.remove_call_user(request.sid)


@socketio.on("leave_call", namespace="/call")
def leave_call(data):
    emit("leave_call", room=data)


# @socketio.on("create_group", namespace="/groupcall")
# def create_group_call(data):
#     group_name = data["group_name"]
#     username = data["username"]
#     signal = data["signal"]
#     if util.make_group_call_room(request.sid, username, signal, group_name):
#         emit("create_group", True)
#     else:
#         join_room(group_name)
#         emit("create_group", False)


# @socketio.on("join_group", namespace="/groupcall")
# def join_group_call(data):
#     group_name = data["group_name"]
#     username = data["username"]
#     signal = data["signal"]
#     other_members = util.join_group_call(request.sid, username, signal, group_name)
#     if not other_members:
#         emit("group_members", {"valid": False})
#     else:
#         join_room(group_name)
#         emit("group_members", {"valid": True, "other_members": other_members})
#     for member in other_members:
#         emit("join_group", [request.sid, username, signal], room=member[0])


# @socketio.on("leave_group", namespace="/groupcall")
# def leave_group_call(data):
#     group_name = data["group_name"]
#     result = util.leave_group_call(request.sid, group_name)
#     if result:
#         leave_room(group_name)
#         emit("leave_group", request.sid, room=group_name)


# @socketio.on("disconnect", namespace="/groupcall")
# def disconnect_group_call():
#     for room in rooms():
#         emit("leave_group", request.sid, room=room)


@socketio.on("join_room", namespace="/groupcall")
def join_group_call(data):
    group_name = data
    join_room(group_name)
    result = util.join_group_call(request.sid, group_name)
    print(result)
    emit("all_users", result)


@socketio.on("disconnect", namespace="/groupcall")
def disconnect_group_call():
    for room in rooms():
        if room != request.sid:
            util.leave_group_call(request.sid, room)
            emit("leave_group", request.sid, room=room)


@socketio.on("leave_room", namespace="/groupcall")
def leave_group_call(data):
    leave_room(data)
    util.leave_group_call(request.sid, data)
    emit("leave_group", request.sid, room=data)


@socketio.on("sending_signal", namespace="/groupcall")
def sending_signal(data):
    emit(
        "user_joined",
        {"signal": data["signal"], "sid": request.sid},
        room=data["user_to_signal"],
    )


@socketio.on("returning_signal", namespace="/groupcall")
def return_signal(data):
    emit(
        "receiving_signal",
        {"signal": data["signal"], "sid": request.sid},
        room=data["caller_sid"],
    )
