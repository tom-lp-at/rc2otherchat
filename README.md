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
The Attachments are exported with the `migrate.py` from gridfsmigrate. 
I prefer this way because the other dump creates directorys with the GridFS-ID with the files in it. But they have mostly no extension. 
I learned in the Matrix.org import (on the hard way), that they **must have** a valid extension. I have to find the right extension anyway, i find the usage from the GridFS-ID-Only export easier then the subdirectory-based export. Without the extension the file is uploaded correctly, but i got no preview of the attachment. I saw only a file attachment that has to be downloaded to see the content...

How the import for NextCloud-Talk works:
With the dumps in the right place  
/inputs/rocketchat_messages.json  
/inputs/rocketchat_rooms.json  
/inputs/rocketchat_users.json  
/inputs/files/<exported files from gridfs>  

you have to edit the parameters on the top of the file (included the connection string to mysql/mariadb)  
Be aware : i used **oc_** as suffix for the tables. If you used a other suffix you have to replace all **oc_** with your suffix!!  
