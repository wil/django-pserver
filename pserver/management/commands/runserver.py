from optparse import make_option
import os
import sys
import socket
import fcntl

from django.core.management.commands.runserver import Command as RunServerCommand
from django.core.handlers.wsgi import WSGIHandler
from django.core.servers.basehttp import AdminMediaHandler, WSGIServerException, WSGIServer, WSGIRequestHandler
from django.utils import autoreload


PERSISTENT_SOCK = None


class Command(RunServerCommand):
    option_list = RunServerCommand.option_list
    help = "Starts a persistent web server that reuses its listening socket on reload."


    def run(self, *args, **options):
        """
        Runs the server, using the autoreloader if needed
        """
        global PERSISTENT_SOCK
        use_reloader = options.get('use_reloader', True)
        self.new_sock = False

        existing_fd = os.environ.get('SERVER_FD')
        if not existing_fd:
            PERSISTENT_SOCK = socket.socket(socket.AF_INET6 if self.use_ipv6 else socket.AF_INET,
                                            socket.SOCK_STREAM)
            os.environ['SERVER_FD'] = str(PERSISTENT_SOCK.fileno())
            self.new_sock = True
        else:
            print "Reusing existing socket (fd=%s)" % existing_fd
            PERSISTENT_SOCK = socket.fromfd(int(existing_fd),
                                            socket.AF_INET6 if self.use_ipv6 else socket.AF_INET,
                                            socket.SOCK_STREAM)

        if use_reloader:
            autoreload.main(self.inner_run, args, options)
        else:
            self.inner_run(*args, **options)

    def inner_run(self, *args, **options):
        global PERSISTENT_SOCK
        from django.conf import settings
        from django.utils import translation

        shutdown_message = options.get('shutdown_message', '')
        quit_command = (sys.platform == 'win32') and 'CTRL-BREAK' or 'CONTROL-C'

        self.stdout.write("Validating models...\n\n")
        self.validate(display_num_errors=True)
        self.stdout.write((
            "Django version %(version)s, using settings %(settings)r\n"
            "pserver is running at http://%(addr)s:%(port)s/\n"
            "Quit the server with %(quit_command)s.\n"
        ) % {
            "version": self.get_version(),
            "settings": settings.SETTINGS_MODULE,
            "addr": self._raw_ipv6 and '[%s]' % self.addr or self.addr,
            "port": self.port,
            "quit_command": quit_command,
        })
        # django.core.management.base forces the locale to en-us. We should
        # set it up correctly for the first request (particularly important
        # in the "--noreload" case).
        translation.activate(settings.LANGUAGE_CODE)

        try:
            handler = self.get_handler(*args, **options)
            server_address = (self.addr, int(self.port))
            httpd = WSGIServer(server_address, WSGIRequestHandler, ipv6=self.use_ipv6, bind_and_activate=False)
            httpd.socket = PERSISTENT_SOCK

            try:
                httpd.server_bind()
            except WSGIServerException, e:
                if 'Errno 22' in str(e):
                    # may have been bound, just emulate some stuff done in server_bind (like setting up environ)
                    httpd.server_name = socket.getfqdn(self.addr)
                    httpd.server_port = int(self.port)
                    httpd.setup_environ()
                else:
                    raise
            httpd.server_activate()
            httpd.set_app(handler)
            httpd.serve_forever()


        except KeyboardInterrupt:
            if shutdown_message:
                self.stdout.write("%s\n" % shutdown_message)
            sys.exit(0)

