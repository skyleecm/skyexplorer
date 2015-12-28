What is Sky Explorer?

It is a file manager for Symbian S60 phone, (2nd & 3rd edition supported)
similar to FExplorer, a freeware which I recommend.

It is written in Python using PythonS60 developed by Nokia, and is open source.
(In fact, this is my 1st open source project)

  * It features all basic file operations like: navigation and file display
  * cut, copy, paste, rename, delete, search
  * sending files via bluetooth, email, mms.

  * Additionally, it supports zip archive and extract
  * screenshot
  * application tagging (menu system within program to launch application)
  * 2 keys input method

**Update**: Users can now sign the Sky Explorer 3rd edition using [Symbian Open Signed Online beta](https://www.symbiansigned.com/app/page/public/openSignedOnline.do). Download [skyexplorer\_3rdEd\_1.0.3.unsigned.sis](http://skyexplorer.googlecode.com/files/skyexplorer_3rdEd_1.0.3.unsigned.sis) and [APPLIST.unsigned.sis](http://applist.googlecode.com/files/APPLIST.unsigned.sis), both are created with UIDs in the Test Range and with all possible capabilities. In Symbian Open Signed Online, select all the capabilities before submitting.

I have now tested it on 3rd edition. Sky Explorer needs keycapture module which requires SwEvent capability. In order to run it, it is required to be signed with a free Symbian Developer Certificate from www.symbiansigned.com . Get both   	APPLIST\_3rdEd\_1.0.unsigned.sis and skyexplorer\_3rdEd\_1.0.1.unsigned.sis and optionally, pyemail\_3rdEd\_1.0.unsigned.sis.