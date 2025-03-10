#!/usr/bin/python3

import argparse
import sys
import os
import pprint as ppprint
import json
import requests
from datetime import datetime
import re
import markdown
import errno
import dateutil.parser as dp
import mimetypes
import subprocess
import pprint
#import mysql
import mariadb
import bcrypt
import random, string
import shutil
import hashlib

#import psycopg2

# for retries
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from subprocess import check_output
from pprint import PrettyPrinter
#from maria_easy.connect import connect,Error
from urllib.parse import quote
from pathlib import Path
from PIL import Image


import magic

import emoji # for reactions

# globals - You have to define your settings here
roomsfile = "rocketchat_rooms.json"
usersfile = "rocketchat_users.json"
histfile = "rocketchat_messages.json"
verbose = False
messages_cachefile = "messages_cache.txt"
users_cachefile = "users_cache.txt"
rooms_cachefile = "rooms_cache.txt"
nextcloud_data = "/var/www/cloud.example.com/data/"
nextcloud_owner = "nginx:nginx"

pprinter = PrettyPrinter()

connection = mariadb.connect(database="<Name_from_the_NC_Database>",user="<User_for_the_DB>",password="<Password_for_the_User>",host="127.0.0.1", port=3306)
# end of editing

cursor = connection.cursor(dictionary=True)

def get_mime_type_with_mimetypes(filename):
    mime_type, encoding = mimetypes.guess_type(filename)
    return mime_type

def get_mime_type_with_magic(filename):
    mime_type = magic.from_file(filename, mime=True)
    return mime_type

# pretty printing functions, switched by verbose argument
def terminal_size():
    import fcntl
    import termios
    import struct
    h, w, hp, wp = struct.unpack('HHHH', fcntl.ioctl(0, termios.TIOCGWINSZ, struct.pack('HHHH', 0, 0, 0, 0)))
    return w, h

def pprint(name, data):
    if verbose:
        w, h = terminal_size()
        pp = ppprint.PrettyPrinter(indent=2, width=w)
        print(name + ": ")
        pp.pprint(data)
        print("\n\n")

def vprint(data):
    if verbose:
        print(str(data))
        print("\n\n")

# Arguments parser
def createArgParser():
    parser = argparse.ArgumentParser(description='Launches RC2Talk migration')
    parser.add_argument("-i", type=str, help='inputs folder, defaults to inputs/', dest="inputs", default="inputs/")
    parser.add_argument("-s", type=str, help='Starting timestamp (excluded)', dest="startts", default=0 )
    parser.add_argument("-v", help='verbose', dest="verbose", action="store_true")

    return parser

# Try to format a markdown message into html
def format_message(raw):
    formatted = markdown.markdown(raw)
    if len(formatted) <= len(raw)+7: # markdown adds <p></p> tags
        api_params = {'msgtype': 'm.text', 'body': raw}
    else:
        api_params = {'msgtype': 'm.text', 'body': raw,
            "format": "org.matrix.custom.html",
            "formatted_body": formatted}

    return api_params

# Add a related event, currently unused
def relate_message(raw, ancestor):
    api_params = {'msgtype': 'm.text', 'body': raw,
        "m.relates_to": {
            "m.in_reply_to": {
                "event_id": ancestor
                }
            }
        }

    return api_params

def invite(api_base, api_headers_admin, tgtroom, tgtuser):
    # from the matrix-code. It is not needed here...
    print("Invite....")

if __name__ == '__main__':
    parser = createArgParser()
    args = parser.parse_args()
    verbose = args.verbose
    # mime = magic.Magic(ms=1)

    if (verbose):
        print("Arguments are: ", args)

    # Import users
    print("Importing users...")
    users = set()
    # load cache
    nbcache = 0
    try:
        with open(users_cachefile, encoding='utf8') as f:
            for line in f:
                nbcache+=1
                users.add(line.rstrip('\n'))
        f.close()
        print("Restored " + str(nbcache) + " user ids from cache")
    except FileNotFoundError:
        print("No user cache to restore")
    cache = open(users_cachefile, 'a')
    # import new users
    with open(args.inputs + usersfile, 'r') as jsonfile:
        # Each line is a JSON representing a RC user
        for line in jsonfile:
            currentuser = json.loads(line)
            pprint("current user", currentuser)
            if ("username" not in currentuser):
                continue
            username=currentuser['username'].lower()
            if "name" in currentuser and isinstance(currentuser['name'], str):
                displayname=currentuser['name']
            else:
                displayname=username
            if username in users:
                print("user " + username + " already processed (in cache), skipping")
                continue
            # Nextcloud username will be username
            temp_output = ""
            try:
                query_string = "select * from oc_users where uid_lower='" + username + "'"
                cursor.execute(query_string)
                row = cursor.fetchall()
                rows = cursor.rowcount
                # print("Anzahl Zeilen " + repr(rows))
                #temp_output = cursor.fetchone()
                # print("User gefunden : " + repr(row))
                
                if rows > 0:
                        print("Displayname exists " + row[0]['displayname'])
                else:
                        print("create user " + username)
                        
                        # see if a password is stored for the user...
                        if "services" in currentuser:
                            password_new = "1|" + currentuser['services']['password']['bcrypt']
                        else:
                            password_new = ""
                            
                        query_string = "insert into oc_users set uid='" + username +"',displayname='" + username + "',password='" + password_new + "',uid_lower='" + username.lower() + "'"
                        cursor.execute(query_string)
                        connection.commit()
                        
            except mariadb.DataError as e:
                print(e)
            except mariadb.DatabaseError as e:
                print(e)
            
            
            cache.write(username + "\n")
    cache.close()
    
    # stop in the time of development - deactivated afterwards
    #exit(0)
    
    # Import rooms
    print("Importing rooms...")
    roomids = {}  # Map RC_roomID to Matrix_roomID
    # load cache
    nbcache = 0
    try:
        with open(rooms_cachefile, encoding='utf8') as f:
            for line in f:
                nbcache+=1
                atoms = line.rstrip('\n').split('$')
                roomids[atoms[0]] = atoms[1]
        f.close()
        print("Restored " + str(nbcache) + " room ids from cache")
    except FileNotFoundError:
        print("No room cache to restore")
    cache = open(rooms_cachefile, 'a')
    # Import new rooms
    with open(args.inputs + roomsfile, 'r') as jsonfile:
        # Each line is a JSON representing a RC room
        for line in jsonfile:
            currentroom = json.loads(line)
            if currentroom['_id'] in roomids:
                print("room " + currentroom['_id'] + " already processed (in cache), skipping")
                continue
            pprint("current room", currentroom)

            createroom = False
            searchroom = False
            
            #if "u" in currentroom:
            #    print("Ist ein Userrchat ....")
            if currentroom['t'] == 'd': # DM, create a private chatroom - in NextCloud : type = 1
                # Checken ob "usernames" gleich 2 ist und ob beide Elemente gleich sind. Dann wäre der Raum ein "Notiz an mich" mit der object_id == username und object_type == "note_to_self" und type==4
                userliste_temp = currentroom['usernames']
                userliste_rc = sorted(userliste_temp)
                
                if "rocket.cat" not in userliste_rc:
                    print("userlist in RocketChat " + repr(userliste_rc) + "( " + repr(userliste_temp) +  " )"+ "for Room " + currentroom['_id'])
                    if len(userliste_rc) == 2:
                        if userliste_rc[0] == userliste_rc[1]:
                            print("search for personal room")
                            query_string = "select * from oc_talk_rooms where object_id='" + userliste_rc[0] + "' and type=6"
                            cursor.execute(query_string)
                            row = cursor.fetchall()
                            rows = cursor.rowcount
                            if rows > 0:
                                print("personal room for " + userliste_rc[0] + " exists. ID = " + repr(row[0]['id']))
                                cache.write(currentroom['_id'] + "$" + repr(row[0]['id']) + "\n")
                            else:
                                token_new = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(8))
                                datum_new = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                query_string = "insert into oc_talk_rooms set object_id = '" + userliste_rc[0] +  "', object_type='note_to_self', name='Notiz an mich',token='" + token_new + "',last_activity='" + datum_new +"', description='Ein Platz für Ihre privaten Notizen, Gedanken und Ideen',type=6"
                                cursor.execute(query_string)
                                connection.commit()
                                new_id = cursor.lastrowid
                                print("Insert Room " + query_string + " => ID = " + str(new_id))
                                cache.write(currentroom['_id'] + "$" + str(new_id) + "\n")
                                
                                query_string = "insert into oc_talk_attendees set actor_id = '" + userliste_rc[0] +  "', actor_type='users', room_id=" + str(new_id) + ",display_name='" + userliste_rc[0] + "',last_attendee_activity='" + datum_new +"', participant_type=3,notification_calls=1"
                                cursor.execute(query_string)
                                connection.commit()
                                
                                
                        else:
                            query_string = "select * from oc_talk_rooms where name='[\"" +userliste_rc[0] + "\",\"" + userliste_rc[1] + "\"]' and type=1"
                            print("Query = " + query_string)
                            cursor.execute(query_string)
                            row = cursor.fetchall()
                            rows = cursor.rowcount
                            if rows > 0:
                                print("Chatraum für " + repr(userliste_rc) + " vorhanden. ID = " + repr(row[0]['id']))
                                cache.write(currentroom['_id'] + "$" + repr(row[0]['id']) + "\n")
                            else:
                                token_new = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(8))
                                datum_new = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                query_string = "insert into oc_talk_rooms set name = '[\"" +userliste_rc[0] + "\",\"" + userliste_rc[1] + "\"]', token='" + token_new + "',last_activity='" + datum_new +"', type=1"
                                cursor.execute(query_string)
                                connection.commit()
                                new_id = cursor.lastrowid
                                print("Insert Room " + query_string + " => ID = " + str(new_id))
                                cache.write(currentroom['_id'] + "$" + str(new_id) + "\n")
                                
                                query_string = "insert into oc_talk_attendees set actor_id = '" + userliste_rc[0] +  "', actor_type='users', room_id=" + str(new_id) + ",display_name='" + userliste_rc[0] + "',last_attendee_activity='" + datum_new +"', participant_type=1,notification_calls=1"
                                cursor.execute(query_string)
                                connection.commit()
                                
                                query_string = "insert into oc_talk_attendees set actor_id = '" + userliste_rc[1] +  "', actor_type='users', room_id=" + str(new_id) + ",display_name='" + userliste_rc[1] + "',last_attendee_activity='" + datum_new +"', participant_type=1,notification_calls=1"
                                cursor.execute(query_string)
                                connection.commit()
                    else:
                        print("Not 2 members!!" + str(len(userliste_rc)))
                        searchroom = True
                    
                    if searchroom:
                        # search in the existing rooms
                        query_string = "select * from oc_talk_rooms"
                        cursor.execute(query_string)
                        rows = cursor.fetchall()
                        rowcount = cursor.rowcount
                        createroom = True
                        for row in rows:
                            try:
                                userliste_temp = json.loads(row['name'])
                                userliste_talk = sorted(userliste_temp)
                                print("Userliste in Talk " + repr(userliste_talk))
                            except:
                                userliste_temp = row['name']
                                print("einzelner Name " + userliste_temp)
                            #if isinstance(userliste_temp, str):
                                
                            #elif isinstance(userliste_temp, list):
                        
                        # the excption for this case doesnt come up - needed ?
                
            elif currentroom['t'] == 'c': # public chatroom  - in NextCloud : type = 3
                print("Public Chatroom")
                # check if "usernames" is equal 2 and booth elements have the same name...
                # Then its a "Note to self" with object_id == username und object_type == "note_to_self" und type==4
                userliste_temp = currentroom['usernames']
                userliste_rc = sorted(userliste_temp)
                
                if "rocket.cat" not in userliste_rc:
                    print("userlist in RocketChat " + repr(userliste_rc) + "( " + repr(userliste_temp) +  " )"+ "for Room " + currentroom['_id'])
                    if len(userliste_rc) == 0:
                        query_string = "select * from oc_talk_rooms where name='" + currentroom['_id'] + "' and type=3"
                        print("Query = " + query_string)
                        cursor.execute(query_string)
                        row = cursor.fetchall()
                        rows = cursor.rowcount
                        if rows > 0:
                            print("public Chatroom for " + repr(userliste_rc) + " exist. ID = " + repr(row[0]['id']))
                            cache.write(currentroom['_id'] + "$" + repr(row[0]['id']) + "\n")
                        else:
                            token_new = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(8))
                            datum_new = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            query_string = "insert into oc_talk_rooms set name = '" + currentroom['_id'] + "', token='" + token_new + "',last_activity='" + datum_new +"', type=3"
                            cursor.execute(query_string)
                            connection.commit()
                            new_id = cursor.lastrowid
                            print("Insert Public Room " + query_string + " => ID = " + str(new_id))
                            cache.write(currentroom['_id'] + "$" + str(new_id) + "\n")
                            
                            query_string = "insert into oc_talk_attendees set actor_id = '" + currentroom['lastMessage']['u']['username'] +  "', actor_type='users', room_id=" + str(new_id) + ",display_name='" + currentroom['lastMessage']['u']['name'] + "',last_attendee_activity='" + datum_new +"', participant_type=1,notification_calls=1"
                            cursor.execute(query_string)
                            connection.commit()
                            
                    else:
                        print("Not 2 Members!!" + str(len(userliste_rc)))
                        searchroom = True
                    
                    if searchroom:
                        # Holen der bestehenden Räume
                        query_string = "select * from oc_talk_rooms"
                        cursor.execute(query_string)
                        rows = cursor.fetchall()
                        rowcount = cursor.rowcount
                        createroom = True
                        for row in rows:
                            try:
                                userliste_temp = json.loads(row['name'])
                                userliste_talk = sorted(userliste_temp)
                                print("Userliste in Talk " + repr(userliste_talk))
                            except:
                                userliste_temp = row['name']
                                print("einzelner Name " + userliste_temp)
                            #if isinstance(userliste_temp, str):
                                
                            #elif isinstance(userliste_temp, list):
                        
                        # the excption for this case doesnt come up - needed ?
                
            elif currentroom['t'] == 'p': # private chatroom  - in NextCloud : type = 1
                print("Private Chatroom")
            else:
                exit("Unsupported room type : " + currentroom['t'])
            #else:
            #   print("no Userchat")
            
    cache.close()
    pprint("room ids", roomids)

    # exit(0)
    
    # Messages
    print("Importing messages...")
    # We count lines for printing the progress
    nblines = 0
    for line in open(args.inputs + histfile): nblines += 1
    lastts = 0 # last seen timestamp, to check that messages are chronologically sorted
    currentline = 0 # current read line
    idmaps = {} # map RC_messageID to Matrix_messageID for threads, replies, ...

    # load cache
    nbcache = 0
    try:
        with open(messages_cachefile, encoding='utf8') as f:
            for line in f:
                nbcache+=1
                atoms = line.rstrip('\n').split(':')
                idmaps[atoms[0]] = atoms[1]
        f.close()
        print("Restored " + str(nbcache) + " message ids from cache")
    except FileNotFoundError:
        print("No message cache to restore")
    cache = open(messages_cachefile, 'a')

    # print(idmaps)
    # exit(1)
    hexstring = os.urandom(32).hex()
    
    with open(args.inputs + histfile, 'r') as jsonfile:
        # Each line is a JSON representing a message
        for line in jsonfile:
            currentline+=1
            print("Importing message " + str(currentline) + "/" + str(nblines), end='')
            currentmsg = json.loads(line)
            pprint("current message", currentmsg)
            finished=False # set to true to not (re)print the message in the final step
            response=None
            if currentmsg['rid'] in roomids:
                tgtroom = roomids[currentmsg['rid']] # tgtroom is the matrix room
                tgtuser = currentmsg['u']['username'] # tgtuser is the matrix user
                tempdata = currentmsg['ts']['date']

                datetime_temp = dp.parse(tempdata)
                tgtts = datetime_temp.timestamp()
                if tgtts <= int(args.startts): # skip too old message
                    print(", timestamp=" + str(tgtts) + ", skipping")
                    continue
                if currentmsg['_id'] in idmaps:
                    print(", already processed (in cache), skipping")
                    continue
                print(", timestamp=" + str(tgtts))
                if tgtts < lastts:
                    print ("Messages are not sorted. Different folder ?")
                    # exit("Messages are not sorted, leaving...")
                lastts = tgtts

                # Pinned messages, unhandled
                if 't' in currentmsg and currentmsg['t']=="message_pinned":
                    print(", timestamp=" + str(tgtts) + ", message pinning event, skipping")
                    continue

                # Jitsi start messages, unhandled
                if 't' in currentmsg and currentmsg['t']=="jitsi_call_started":
                   print(", timestamp=" + str(tgtts) + ", jitsi_call event, skipping")
                   continue

                # First, iterate attachments
                # https://developer.rocket.chat/reference/api/rest-api/endpoints/messaging/chat-endpoints/send-message#attachment-field-objects
                if 'attachments' in currentmsg and hasattr(currentmsg['attachments'], '__iter__'):
                    for attachment in currentmsg['attachments']:
                        if 'type' in attachment and attachment['type'] == 'file': # A file
                            vprint("a file")
                            nc_message = {"message":"file_shared"}
                            
                            if 'image_type' in attachment: # we have a content-type
                                vprint("an image")
                            
                            try: # try to find the file in the export
                                localfile=attachment['title_link']
                                localfile=re.sub("/file-upload/", "", localfile)
                                localfile=re.sub("/.*", "", localfile)
                                
                                print("filename => " + ">>>" + args.inputs + "files/" + localfile + "<<<")
                                temp_mimetype = get_mime_type_with_magic(args.inputs + "files/" + localfile)
                                
                                img_width=0
                                img_height=0
                                user_homes={}
                                extension = "xxx"

                                if "title" in attachment:
                                    old_title = attachment['title']
                                else:
                                    old_title = ""
                                    
                                print("Temp_MIMEType = " + temp_mimetype)
                                if temp_mimetype.startswith("image") or temp_mimetype.startswith("application") or temp_mimetype.startswith("video")  :
                                    if temp_mimetype.startswith("image"):
                                        image = Image.open(args.inputs + "files/" + localfile)
                                        img_width, img_height = image.size
                                    extension = temp_mimetype.rsplit("/",1)[1]

                                    # Correct the extension if it's jpeg
                                    if extension == "jpeg":
                                        extension="jpg"

                                    if not attachment['title_link'].endswith(extension):
                                        print("EXTENSION is not existing : " + extension)
                                        print("File name was :" + attachment['title_link'] + "\n-----------------------------------------------")
                                        attachment['title_link'] = attachment['title_link'] + "." + extension
                                    if "image_url" in attachment:
                                        if not attachment['image_url'].endswith(extension):
                                            attachment['image_url'] = attachment['image_url'] + "." + extension
                                    
                                    if not attachment['title'].endswith(extension):
                                        attachment['title'] = attachment['title'] + "." + extension
                                    print("new file name : " + attachment['title'])
                                    
                                    
                                    
                                elif temp_mimetype == "text/plain":
                                    extension = "txt"
                                    if not attachment['title_link'].endswith(extension):
                                        attachment['title_link'] = attachment['title_link'] + "." + extension
                                    if "image_url" in attachment:
                                        if not attachment['image_url'].endswith(extension):
                                            attachment['image_url'] = attachment['image_url'] + "." + extension
                                    
                                    if not attachment['title'].endswith(extension):
                                        attachment['title'] = attachment['title'] + "." + extension
                                    print("Neuer Filename : " + attachment['title'])
                                
                                
                                # print("filename => " + localfile)
                                
                                query_string = "select * from oc_talk_rooms where id='" + str(tgtroom) + "'"
                                cursor.execute(query_string)
                                row = cursor.fetchall()
                                rows = cursor.rowcount
                                # print("Query String bei Suche nach Token : " + query_string)
                                # print("1. Zeile " + repr(row[0]))
                                
                                if 'token' not in row[0]:
                                    print("Token nicht gefunden für Raum " + str(tgtroom))
                                    
                                raum_token = row[0]['token']
                                print ("Token = " + raum_token)
                                
                                new_filename = quote(attachment['title'])
                                new_file_path = Path(nextcloud_data + currentmsg['u']['username'] + "/files/Talk/" + new_filename)
                                if new_file_path.is_file():
                                    new_filename = quote(attachment['title']) + str(random.randint(100,999)) + "." + extension
                                
                                # copy the file to the right Talk-directory of the user and change permission & mtime
                                shutil.copy(args.inputs + "files/" + localfile, nextcloud_data + currentmsg['u']['username'] + "/files/Talk/" + new_filename)
                                os.system("chown " + nextcloud_owner + " " + nextcloud_data + currentmsg['u']['username'] + "/files/Talk/" +new_filename )
                                os.utime(nextcloud_data + currentmsg['u']['username'] + "/files/Talk/" +new_filename,times=(tgtts,tgtts))
                                
                                if 'image_type' in attachment: # attachment is an image
                                    print("GetAttachment")
                                    temp_mimetype = get_mime_type_with_magic(args.inputs + "files/" + localfile)
                                else: # other files
                                    temp_mimetype = get_mime_type_with_magic(args.inputs + "files/" + localfile)

#                                     print("--------------------------------------------------")
#                                     print("Attament => " + repr(attachment))
#                                     print("--------------------------------------------------")
#                                     
                                # create a token for the file
                                token_new = ''.join(random.choice(string.ascii_uppercase +string.ascii_lowercase + string.digits) for _ in range(15))
                                datum_new = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                query_string = "insert into oc_share set share_type = '10', token='" + token_new + "',stime='" + str(tgtts) +"', share_with='" + raum_token + "', file_target = '/{TALK_PLACEHOLDER}/" + new_filename + "', uid_owner = '" +  currentmsg['u']['username'] + "', uid_initiator='" +currentmsg['u']['username'] + "', item_type='file',permissions='19'"
                                cursor.execute(query_string)
                                connection.commit()
                                share_id_0 = cursor.lastrowid
                                print("Query für Share = " + query_string)
                                print("Insert Share " + query_string + " => ID = " + str(share_id_0))
                                
                                # in a mysql-dump i saw a second record for a share, but it seams not needed....
#                                 query_string = "insert into oc_share set share_type = '11', stime='" + str(tgtts) +"', share_with='" + currentmsg['u']['username'] + "', file_target = '/Talk/" + new_filename + "', uid_owner = '" +  currentmsg['u']['username'] + "', uid_initiator='" +currentmsg['u']['username'] + "', item_type='file',permissions='19',parent='" +str(share_id_0) + "'"
#                                 cursor.execute(query_string)
#                                 connection.commit()
#                                 share_id = cursor.lastrowid
#                                 print("Query für Share = " + query_string)
#                                 print("Insert Share " + query_string + " => ID = " + str(share_id))
#                                 
                               
                                
                                if 'description' in attachment:
                                    description = attachment['description']
                                else:
                                    description = new_filename
                                
                                description = description.translate(str.maketrans({"'":""}))
                                description = emoji.emojize(description, language='alias')
                                
                                # this should be the minimum parameter they are needed
                                nc_message['parameters'] = {"share": str(share_id_0), "metaData" : {"caption": description, "mimeType" : temp_mimetype }}
                                
                                hexstring = os.urandom(32).hex()
                                tempdata = currentmsg['ts']['date']
                                datetime_temp = dp.parse(tempdata)
                                tgtts = datetime_temp.timestamp()
                                datum_new = datetime_temp.strftime("%Y-%m-%d %H:%M:%S")
                                
                                
                                # insert the file as a comment into the database
                                query_string = "insert into oc_comments set actor_type = 'users', reference_id='" + hexstring + "',creation_timestamp='" + datum_new +"', object_type ='chat', verb= 'object_shared', object_id = '" +  str(tgtroom) + "', message='" + json.dumps(nc_message) + "',actor_id='" + currentmsg['u']['username'] + "', meta_data='{\"can_mention_all\":true}'"
                                print("Query für Comment = " + query_string)
                                
                                cursor.execute(query_string)
                                connection.commit()
                                comment_id = cursor.lastrowid
                                print("Insert Comment " + query_string + " => ID = " + str(comment_id))
                               
                                # search for the mimetype of the file 
                                # NC uses ID's they are corresponding to the complete mimetype and the first part
                                # maybe to list all medias with <images> 
                                
                                # first search for the complete mimetype
                                query_string = "select * from oc_mimetypes where mimetype='" + temp_mimetype + "'"
                                cursor.execute(query_string)
                                row = cursor.fetchall()
                                rows = cursor.rowcount
                                print("Query String bei Suche MimeType : " + query_string + "\n")
                                
                                if rows > 0:
                                    if 'id' not in row[0]:
                                        print("no MimeType found !!!\n----------------------------------------------")
                                        mimetype_id = 0
                                    else:
                                        print("first line " + repr(row[0]))
                                        mimetype_id = row[0]['id']
                                else:
                                    print("no MimeType found !!!\n----------------------------------------------")
                                    mimetype_id = 0
                                
                                
                                # second search for the first part of mimetype. for example "image/png"
                                # split on the "/"
                                mime_temp= temp_mimetype.split("/")
                                
                                # use the first element for the query. "image"
                                query_string = "select * from oc_mimetypes where mimetype='" + mime_temp[0] + "'"
                                cursor.execute(query_string)
                                row = cursor.fetchall()
                                rows = cursor.rowcount
                                
                                print("Query String bei Suche MimeType - Obergruppe : " + query_string + "\n")
                                print("1. Zeile " + repr(row[0]))
                                
                                if 'id' not in row[0]:
                                    mimepart = 0
                                else:
                                    mimepart = row[0]['id']
                                
                                # create the filename for the destination and calculate a hash for the filename
                                path_temp = "files/Talk/" + new_filename
                                path_hash = hashlib.md5(path_temp.encode()).hexdigest()
                                
                                # search for the base directory from a user
                                if currentmsg['u']['username'] not in user_homes:
                                    query_string = "select * from oc_storages where id='home::" + currentmsg['u']['username'] + "'"
                                    print("Query String Storage-Suche : " + query_string)
                                    cursor.execute(query_string)
                                    row = cursor.fetchall()
                                    rows = cursor.rowcount
                                    if rows > 0:
                                        print("Row 0 von Storage : " + repr(row))
                                        user_homes[currentmsg['u']['username']] = row[0]['numeric_id']
                                    else:
                                        user_homes[currentmsg['u']['username']] = 1
                                
                                # insert into filecache
                                query_string = "insert into oc_filecache set storage = '" + str(user_homes[currentmsg['u']['username']]) + "', path='files/Talk/" + new_filename + "',name='" + new_filename + "', path_hash='" + path_hash + "', mimetype = '" + str(mimetype_id) +  "', mimepart='" + str(mimepart) + "', size='" + str(os.path.getsize(args.inputs + "files/" + localfile)) +  "', mtime='" + str(tgtts) + "',storage_mtime='" + str(tgtts) + "', permissions='27'"
                                
                                print("Query für FileCache = " + query_string)
                                try:
                                    cursor.execute(query_string)
                                    connection.commit()
                                    filecache_id = cursor.lastrowid
                                except:
                                    query_string="select * from oc_filecache where path_hash='" + path_hash + "'"
                                    cursor.execute(query_string)
                                    row = cursor.fetchall()
                                    rows = cursor.rowcount
                                    
                                    if 'id' not in row[0]:
                                        filecache_id = 0
                                    else:
                                        filecache_id =row[0]['id']
                                
                                if filecache_id>0:
                                    print("Insert FileCache " + query_string + " => ID = " + str(filecache_id))
                                    
                                    # query_string = "update oc_share set item_source = '" + str(filecache_id) + "', file_source='" +  str(filecache_id) + "' where id='" + str(share_id) + "'"
                                    # cursor.execute(query_string)
                                    # connection.commit()
                                    
                                    query_string = "update oc_share set item_source = '" + str(filecache_id) + "', file_source='" +  str(filecache_id) + "' where id='" + str(share_id_0) + "'"
                                    cursor.execute(query_string)
                                    connection.commit()
                                    
                                    
                                query_string = "insert into oc_talk_attachments set room_id = '" + str(tgtroom) + "', message_id='" + str(comment_id) + "',message_time='" + str(tgtts) +"', object_type ='media', actor_type= 'users', actor_id = '" + currentmsg['u']['username'] + "'"
                                
                                cursor.execute(query_string)
                                connection.commit()
                                attachment_id = cursor.lastrowid
                                print("Query für Attachment = " + query_string)
                                print("Insert Attachment " + query_string + " => ID = " + str(attachment_id))
                                
                                if filecache_id>0:
                                    sync_token = ''.join(random.choice(string.ascii_uppercase +string.ascii_lowercase + string.digits) for _ in range(7))
                                    json_temp = {"photos-size": {"value": {"width": img_width, "height": img_height }}}
                                    
                                    query_string = "insert into oc_files_metadata set file_id= '" + str(filecache_id) + "', json='" + json.dumps(json_temp) +"', sync_token='" + sync_token + "', last_update= '" + datum_new + "'"
                                    cursor.execute(query_string)
                                    connection.commit()
                                    share_id = cursor.lastrowid
                                    print("Query für Share = " + query_string)
                                    print("Insert Share " + query_string + " => ID = " + str(share_id))
                                    
                                
                                idmaps[currentmsg['_id']]=str(share_id)
                                cache.write(currentmsg['_id'] + ":" + str(share_id) + "\n")
                                
                            except FileNotFoundError: # We do not have the linked attachment
                               print("file not found ....\n----------------------------------------------------")
                            
                        elif 'message_link' in attachment: # This is a citation
                            vprint("A citation")
                            
                            hexstring = os.urandom(32).hex()
                            datum_temp = datetime.fromtimestamp(tgtts)
                            datum_new = datum_temp.strftime("%Y-%m-%d %H:%M:%S")
                            query_string = "insert into oc_comments set actor_id = '" + currentmsg['u']['username'] +  "', actor_type='users', object_type='chat', object_id=" + tgtroom + ",creation_timestamp='" + datum_new +"', meta_data='{\"can_mention_all\":true}',reference_id='" + hexstring + "', message='" + currentmsg['msg'].translate(str.maketrans({"'":"","\\":""})) +  "', verb='comment'"
                            print("Insert Message : " + query_string)
                            
                            cursor.execute(query_string)
                            connection.commit()
                            
                            new_id = cursor.lastrowid
                            idmaps[currentmsg['_id']]=str(new_id)
                            cache.write(currentmsg['_id'] + ":" + str(new_id) + "\n")
                            
                            finished=True # do not repost this message in the final step
                        elif 'image_url' in attachment: # This is an external image
                            vprint("An external image")
                            api_endpoint = api_base + "_matrix/client/v3/rooms/" + tgtroom + '/send/m.room.message?user_id=' + tgtuser + "&ts=" + str(tgtts) # ts, ?user_id=@_irc_user:example.org
                            api_params = {'msgtype': 'm.text', 'body': attachment['image_url']}
                            response = session.post(api_endpoint, json=api_params, headers=api_headers_as)
                            if response.status_code == 403 and response.json()['errcode'] == 'M_FORBIDDEN': # not in the room
                                invite(api_base, api_headers_admin, tgtroom, tgtuser)
                                response = session.post(api_endpoint, json=api_params, headers=api_headers_as)
                            if response.status_code != 200:
                                print("error posting image url")
                                print(attachment['image_url'])
                                print(response.json())
                                exit(1)
                            vprint(response.json())
                        else:
                            # exit("Unsupported attachment : " + str(attachment))
                            print("Unsupported attachment : " + str(attachment))
                # Finally post the message
                
                # in the development a breakpoint - inactive for real import
                # exit (0)
                
                if 'msg' in currentmsg:
                    if currentmsg['msg'] != "" and not finished:
                        hexstring = os.urandom(32).hex()
                        datum_temp = datetime.fromtimestamp(tgtts)
                        datum_new = datum_temp.strftime("%Y-%m-%d %H:%M:%S")
                        
                        new_message = currentmsg['msg'].translate(str.maketrans({"'":"","\\":""}))
                        new_message = emoji.emojize(new_message, language='alias')
                        
                        query_string = "insert into oc_comments set actor_id = '" + currentmsg['u']['username'] +  "', actor_type='users', object_type='chat', object_id=" + tgtroom + ",creation_timestamp='" + datum_new +"', meta_data='{\"can_mention_all\":true}',reference_id='" + hexstring + "', message='" + new_message +  "', verb='comment'"
                        print("Insert Message : " + query_string)
                        
                        cursor.execute(query_string)
                        connection.commit()
                        
                        new_id = cursor.lastrowid
                        idmaps[currentmsg['_id']]=str(new_id)
                        cache.write(currentmsg['_id'] + ":" + str(new_id) + "\n")
                        
                if 'reactions' in currentmsg:
                    print("---------")
                    print(currentmsg['reactions'])
                    print("---------")
                    
                    if (currentmsg['reactions'] != None ):
                        for reaction in currentmsg['reactions']:
                            tgtreaction = emoji.emojize(reaction, language='alias')
                            for username in currentmsg['reactions'][reaction]['usernames']:
                                tgtusername = username
                                vprint(tgtusername + ":" + tgtreaction)
                                
                                hexstring = os.urandom(32).hex()
                                datum_temp = datetime.fromtimestamp(tgtts)
                                datum_new = datum_temp.strftime("%Y-%m-%d %H:%M:%S")
                                
                                query_string = "insert into oc_comments set actor_id = '" + currentmsg['u']['username'] +  "', actor_type='users', object_type='chat', object_id=" + tgtroom + ",creation_timestamp='" + datum_new +"', message='" + tgtreaction +  "', verb='reaction',parent_id='" + idmaps[currentmsg['_id']] +  "',topmost_parent_id='" + idmaps[currentmsg['_id']] +  "'"
                                
                                print("Insert Reaction : " + query_string)
                                
                                cursor.execute(query_string)
                                connection.commit()
                                
                                new_id = cursor.lastrowid
                                idmaps[currentmsg['_id']]=str(new_id)
                                cache.write(currentmsg['_id'] + ":" + str(new_id) + "\n")
                                
                                
            else:
                continue
                # exit("not in a room")
    cache.close()
