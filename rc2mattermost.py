#!/usr/bin/env python3

import bson
import json
import os
# import datetime
import gridfs
from pymongo import MongoClient
import gridfs
import base64
import pymongo
from datetime import datetime, date

# list of the users whose data we do not want to migrate (Bot Accounts)
IGNORE_USERS = ['rocket.cat', 'poll.bot','remind.bot']

# Date range for file migration from Rocket.Chat to Mattermost:
START_DATE = date(2000, 1, 1)
END_DATE = date(2025, 3, 15)

# Locally downloaded database path:
database_path='/root/Data-Migration-from-Rocket.Chat-to-Mattermost/data/rocketchat'


# code for getting the emoji reaction
def get_reactions(rc_message):
    mm_reactions = []
    reaktion = rc_message.get('reactions', {})
    if reaktion is not None:
        for emoji, users in reaktion.items():
            for username in users['usernames']:
                if username not in IGNORE_USERS:
                    mm_reactions.append(dict(
                    user=username.lower(),
                    emoji_name=emoji.replace(':', ''),
                    create_at=int(rc_message['ts'].timestamp() * 1000 + 1000))
                )
    return mm_reactions


# downloading shared files to the local directory
def save_file_from_gridfs(file_id):

    client = MongoClient('mongodb://localhost:27017')

    # Access the specified database
    db = client['rocketchat']

    # Access the GridFS collection , mainly the rocket chat shared files are stored in the 'rocketchat_uploads' collection
    fs = db['rocketchat_uploads']

    # folder path where we need to download the files
    save_dir = "downloaded_files"

    # Ensure the directory exists or create it if it doesn't
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    fs.create_index([("_id", pymongo.ASCENDING)])

    # Access the GridFS collection
    fst = gridfs.GridFS(db, collection='rocketchat_uploads')

    # Find the file by its unique identifier
    file_info = fst.find_one({"_id": file_id})

    # Extracting file name, file uploaded date, and file url for the further usage
    file_info_name = fs.find_one({"_id": file_id}, {"name": 1, "url": 1, "uploadedAt": 1})

    # Check if file information is found
    if file_info:

        # Retrieve the file data
        try:
            file_name = file_info_name.get('name', '')
            uploaded_at = file_info_name.get('uploadedAt')

            # Convert datetime.datetime to datetime.date
            uploaded_date = uploaded_at.date()

            # Check if the uploaded date falls within the specified date range
            if START_DATE <= uploaded_date <= END_DATE:

                if not os.path.exists(f'{save_dir}/{file_id}'):
                    os.makedirs(f'{save_dir}/{file_id}')

                file_save_path = f'{save_dir}/{file_id}/{file_name}'
                if not os.path.exists(file_save_path):
                    file_data = file_info.read()

                    # Save the file data to a local file with the correct name
                    with open(file_save_path, "wb") as f:
                        f.write(file_data)
                    print("File downloaded :",file_name)

                    return file_save_path
                else:
                    print("File is already downloaded.")
                    return file_save_path
            else:
                print(f"File '{file_name}' is not within the specified date range.")

            return None

        except Exception as e:
            return None
    else:
        print(f"File with _id '{file_id}' not found in the GridFS collection.")
        return None


def get_attachments(rc_message):


    mm_attachments = []
    if 'file' in rc_message and rc_message['file'] is not None:
        print('rc_message["file"]["_id"]-->',rc_message["file"]["_id"])

        # Adjust this part based on your file storage setup , if do not want to migrate the files (attachments) then can comment the below code
        file_name = save_file_from_gridfs(rc_message["file"]["_id"])
        if file_name:
            mm_attachments.append(dict(
                path=file_name,
            ))

    return mm_attachments


if __name__ == '__main__':

    fields = {
        'rocketchat_room': None,
        'users': None,
        'rocketchat_custom_emoji': None,
        'rocketchat_subscription': None,
        'rocketchat_message': None,
    }

    for field in fields.keys():
        with open(f'{database_path}/{field}.bson', 'rb') as f:
            fields[field] = bson.decode_all(f.read())


    jsonl = [
        json.dumps(dict(type='version', version=1)),
        # add more teams here
        json.dumps(dict(
            type='team',
            team=dict(
                name='pk',
                display_name='Manfred-Tom',
                type='O',
            ),
        )),
    ]

    # append custom emoji
    for emoji in fields['rocketchat_custom_emoji']:
        if emoji['name'].lower() not in [
            'trollface',
            'party',
        ]:
            mm_emoji = dict(
                type='emoji',
                emoji=dict(
                    name=emoji['name'].lower(),
                    image=f'/bulk/emojis/{emoji["name"].lower()}.{emoji["extension"].lower()}',
                )
            )
            jsonl.append(json.dumps(mm_emoji))

    # build dict to map room ids to room names
    room_names = {}
    direct_rooms = []

    # append chat rooms -> Channels
    for room in fields['rocketchat_room']:
        if 'name' in room:
            room['name'] = room['name'].lower().replace('.', '_')
            room_names[room['_id']] = room['name']
            if room['t'] == 'p':
                type_ = 'P'
            elif room['t'] == 'c':
                type_ = 'O'
            mm_channel = dict(
                type='channel',
                channel=dict(
                    team='pk',
                    name=room['name'],
                    display_name=room['name'].replace('-', ' ').replace('_', ' '),
                    type=type_,
                )
            )
            jsonl.append(json.dumps(mm_channel))
        else:
            if not any([u in room['usernames'] for u in IGNORE_USERS]):
                direct_rooms.append(room)

    # append users
    for user in fields['users']:
        if 'emails' in user:
            mm_channels = []

            # filter out rooms that the user subscribed to
            for subs in [s for s in fields['rocketchat_subscription'] if s['u']['username'] == user['username']]:
                room = [r for r in fields['rocketchat_room'] if r['_id'] == subs['rid'] and 'name' in r]
                if len(room) > 0:
                    room = room[0]
                    if 'roles' in subs and 'owner' in subs['roles']:
                        roles = 'channel_user channel_admin'
                    else:
                        roles = 'channel_user'
                    mm_channels.append(dict(
                        name=room['name'],
                        roles=roles,
                        favorite='f' in subs and subs['f'],
                    ))

            mm_team = dict(
                name='pk',
                roles='team_user',
                channels=mm_channels,
            )



            mm_user = dict(
                type='user',
                user=dict(
                    username=user['username'].lower(),
                    email=user['emails'][0]['address'],
                    use_markdown_preview='true',
                    use_formatting='true',
                    show_unread_section='true',
                    email_interval='hour',
                    teams=[mm_team]
                ),
            )
            jsonl.append(json.dumps(mm_user))

    replies = [
        m for m in fields['rocketchat_message']
        if 'tmid' in m
        and m['u']['username'] not in IGNORE_USERS
        and not ('_hidden' in m and m['_hidden'])
    ]

    # append messages
    for message in fields['rocketchat_message']:
        if (
            'msg' in message
            and message['msg'] is not None
            and message['rid'] in room_names
            and not 'tmid' in message
            and message['u']['username'] not in IGNORE_USERS
            and not ('_hidden' in message and message['_hidden'])
        ):
            mm_replies = []
            for reply in replies:
                if reply['rid'] == message['rid'] and reply['tmid'] == message['_id']:
                    # reactions for replies
                    mm_replies.append(dict(
                        user=reply['u']['username'].lower(),
                        message=reply['msg'][:60000],
                        create_at=int(reply['ts'].timestamp() * 1000),
                        reactions=get_reactions(reply),
                        attachments=get_attachments(reply),
                    ))

            mm_post = dict(
                type='post',
                post=dict(
                    team='pk',
                    channel=room_names[message['rid']],
                    user=message['u']['username'].lower(),
                    create_at=int(message['ts'].timestamp() * 1000),
                    replies=mm_replies,
                    reactions=get_reactions(message),
                    message=message['msg'][:60000],
                    attachments=get_attachments(message),
                )
            )
            jsonl.append(json.dumps(mm_post))

    direct_channel_members = {}
    # now append direct channels (already filtered out)
    for room in direct_rooms:
        # direct_channel_members[room['_id']] = room['usernames']
        channel_members_list = room['usernames']
        if len(channel_members_list) < 2:
            # If there's only one member, duplicate it to create a second member
            if len(channel_members_list) == 1:
                channel_members_list.append(channel_members_list[0])

        direct_channel_members[room['_id']] = list(map(str.lower, channel_members_list))
        mm_direct_channel = dict(
            type='direct_channel',
            direct_channel=dict(
                # members=room['usernames'],
                members=list(map(str.lower, channel_members_list)),
            ),
        )

    # append direct messages
    for message in fields['rocketchat_message']:
        if (
            not message['rid'] in room_names
            and 'msg' in message
            and message['msg'] is not None
            and message['u']['username'] not in IGNORE_USERS
            and not ('_hidden' in message and message['_hidden'])
            and message['rid'] in direct_channel_members
        ):
            mm_post = dict(
                type='direct_post',
                direct_post=dict(
                    team='pk',
                    channel_members=direct_channel_members[message['rid']],
                    message=message['msg'][:60000],
                    user=message['u']['username'].lower(),
                    create_at=int(message['ts'].timestamp() * 1000),
                    reactions=get_reactions(message),
                    attachments=get_attachments(message),
                )
            )
            jsonl.append(json.dumps(mm_post))

    # here after successfully running the code a file "data.jsonl" would be created
    with open(f'data.jsonl', 'w') as f:
        f.write('\n'.join(jsonl) + '\n')
