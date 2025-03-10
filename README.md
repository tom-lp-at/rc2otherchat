# rc2otherchat
RocketChat to NextCloud-Talk / Matrix.org / MatterMost

My intention to test/write a migration to different plattform was quite easy: to create the possibility with the same existing datasets try out other Chat solutions.
I placed all three Tools into this repository to be sure that they work as i have tested... 

The Tool for NextCloud-Talk is written in Python3 and based on the work of two other Repositorys:  
https://github.com/Worteks/RC2Matrix.git  
https://github.com/arminfelder/gridfsmigrate.git  

For the migration to MatterMost i used the work from https://github.com/pragnakalp/Data-Migration-from-Rocket.Chat-to-Mattermost.git and changed the code for the reactions. 

I learned from booth to analyse and understand the structure from RocketChat and transform it into a other structure.

First of all i installed a local MongoDB and imported the bson-Dump from the Liveinstance from RocketChat, to be on the save side.
You should choose the same MongoDB-Server as you run the RocketChat himself. I don´t know really if it matters, but -again- to be on the saveside ;)

For Matrix.org & NextCloud-Talk i used the same dumps created with the `mongo_exportpublic.sh` from RC2Matrix.
The Attachments are exported with the `gridfs-migrate.py` from gridfsmigrate. 
I prefer this way because the other dump creates directorys with the GridFS-ID with the files in it. But they have mostly no extension. 
I learned in the Matrix.org import (on the hard way), that they **must have** a valid extension. I have to find the right extension anyway, i find the usage from the GridFS-ID-Only export easier then the subdirectory-based export. Without the extension the file is uploaded correctly, but i got no preview of the attachment. I saw only a file attachment that has to be downloaded to see the content...

# How the import for NextCloud-Talk works:
With the dumps in the right place  
- /inputs/rocketchat_messages.json  
- /inputs/rocketchat_rooms.json  
- /inputs/rocketchat_users.json  
- /inputs/files/<exported files from gridfs>  

you have to edit the parameters on the top of the file (included the connection string to mysql/mariadb)  
Be aware : i used **oc_** as suffix for the tables. If you used a other suffix you have to replace all **oc_** with your suffix in rc2talk.py !!  

Now it´s time for a break: make a BACKUP NOW of your existing Nextcloud-Database & Files!! Trust me - you will need it...

You will strugle with the needed python moduls. Please have a look into the top of rc2talk.py to see the list of needed modules. tbh: i started the process over and over until all needed modules are installed :)  

You can start the import many times. It will only import messages they are not committed as transfered into the DB of NC.

# How the import for Matrix.org works:
Since encryption is standard at matrix.org, it is not easy to import messages with a date other than **Now**. After some time of trying around, I found a way that was acceptable to me without compromising the security of the entries.
I inject additional messages before the comment that reflects the date & time of the post. The date whose easy, but the time on every message in the end makes the conversation a little bit confusing.
So i decied to write the time at least 10 minutes after the last comment. If the next comment is newer than 10 minutes i inject the time before the message. Feel free to adjust the calculation of adding the additonal time-messages...
The main change is the sending behavior. Every message is send with the corresponding user that is created into the matrix database.

With the dumps in the right place  
- /inputs/rocketchat_messages.json  
- /inputs/rocketchat_rooms.json  
- /inputs/rocketchat_users.json  
- /inputs/files/<exported files from gridfs>  

you have the edit the rc2matrix.yaml. Dont ask me why Two tokens are needed. I imported all with the same Admin-Key. May be my change of sending messages makes the Applikation-Token useless...

Now it´s time for a break: make a BACKUP NOW of your existing Matrix.org-Database & Files!! Trust me - you will need it...

# How the import for Mattermost works:
The import into Mattermost didn't use the dump files above. It generates his own JSONL files from the running MongoDB. 
In the beginning of rc2mattermost, you should edit the settings to your needs:
- START_DATE
- END_DATE
- database_path
- db # bellow of Access to specific database

that´s it.
My migration runs into a empty installation with only one admin user and no rooms (be aware: i choose a username that ist **not** existing in the RocketChat Database!!) Afterwards you can promote a imported User to the admin and delete the initial Adminuser. I have no idea whats going on if you have a existing MatterMost installation where you migrate into.... It should work, but how knows (double user/room names and so on)
May be you will have a look into the original Repo ;)
