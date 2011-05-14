django-pserver
==============

This is a drop-in replacement for Django's runserver command for the impatient.

Django's development server restarts itself whenever it detects a change in any loaded module, which is great.
What's not so great is that during the restart, there is a window of time where, if you're like me, you'd be hitting Ctrl+R key repeatedly on the browser only to be greeted with an error because the server is not ready.

Django-pserver solves this problem by reusing the listening socket when it restarts, so you can just hit refresh once and wait (retaining your sanity.)


TODO
----
This only works on Django 1.3.x. Tested on OS X, but should work on any UNIX variant. It will probably break horribly on Windows.
