from util import get_jkt_timezone
from datetime import datetime
from models import RoomRead, User, db, ChatRoom, Image
import io
import math

socket_users = {}
call_users = {}
group_calls = {}


def add_socket_user(sid, user_id):
    socket_users[sid] = user_id
    print(socket_users)


def get_user_from_sid(sid):
    return User.query.get(socket_users.get(sid))


def get_user_id(sid):
    return socket_users.get(sid)


def remove_socket_user(sid):
    try:
        del socket_users[sid]
    except KeyError:
        return


def add_call_user(sid, user_id):
    call_users_copy = call_users.copy()
    for other_sid, user in call_users_copy.items():
        if user["id"] == user_id:
            del call_users[other_sid]
    call_users[sid] = {
        "id": user_id,
        "is_call": False,
        "call_id": None,
        "is_answered": False,
    }


def get_call_user(sid):
    return User.query.get(call_users.get(sid)["id"])


def get_call_user_id(sid):
    return call_users.get(sid)["id"]


def set_user_call_to(sid, call_id):
    user = call_users.get(sid)
    if user:
        user["is_call"] = True
        user["call_id"] = False


def set_answer_call(sid, call_id):
    user1 = call_users.get(sid)
    user2 = call_users.get(call_id)
    if user1:
        user1["is_answered"] = True
    if user2:
        user2["is_answered"] = True


def get_call_friends_online(sid):
    try:
        call_users_copy = call_users.copy()
        user = User.query.get(call_users[sid]["id"])
        friends_online = []
        for other_sid, user_data in call_users_copy.items():
            if other_sid != sid:
                other_user = User.query.get(user_data["id"])
                if other_user in user.friends:
                    friends_online.append({"name": other_user.name, "sid": other_sid})
        return friends_online
    except KeyError:
        return []


def join_group_call(sid, group_name):
    if not group_name in group_calls:
        group_calls[group_name] = [sid]
        return []
    other_members = group_calls[group_name]
    result = other_members.copy()
    other_members.append(sid)
    return result


def leave_group_call(sid, group_name):
    members = group_calls.get(group_name)
    if members:
        if sid in members:
            members.remove(sid)
            if len(members) == 0:
                del group_calls[group_name]


# def make_group_call_room(sid, username, signal, group_name):
#     if group_name in group_calls:
#         return False
#     group_calls[group_name] = [(sid, username, signal)]
#     return True


# def join_group_call(sid, username, signal, group_name):
#     if group_name not in group_calls:
#         return []
#     other_members = group_calls[group_name]
#     result = other_members.copy()
#     other_members.append((sid, username, signal))
#     return result


# def leave_group_call(sid, group_name):
#     if group_name not in group_calls:
#         return
#     removed_list = list(
#         filter(lambda member: member[0] != sid, group_calls["group_name"])
#     )
#     group_calls["group_name"] = removed_list


def remove_call_user(sid):
    try:
        del call_users[sid]
    except KeyError:
        return


def notify_chat(socketio, room_id):
    for sid, user_id in socket_users.items():
        if RoomRead.query.filter_by(user_id=user_id, room_id=room_id).first():
            socketio.emit("notify_chat", room_id, room=sid)


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
