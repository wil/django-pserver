from optparse import make_option
import os
import sys
import socket

from django.core.management.base import CommandError
from django.core.management.commands.runserver import Command as RunServerCommand
from django.core.handlers.wsgi import WSGIHandler
from django.core.servers.basehttp import AdminMediaHandler, WSGIServerException, WSGIServer, WSGIRequestHandler
from django.utils import autoreload
from pserver import __version__


# store the socket at module level so it can be shared between parent a child process
PERSISTENT_SOCK = None




class Command(RunServerCommand):
    option_list = RunServerCommand.option_list
    help = "Starts a persistent web server that reuses its listening socket on reload."


    def handle(self, addrport='', *args, **options):
        if hasattr(RunServerCommand, 'inner_run'):
            self.has_ipv6_support = True
            # Django 1.3-ish, our overwritten self.run and self.inner_run functions should work
            return super(Command, self).handle(addrport, *args, **options)
        else:
            self.has_ipv6_support = False
            self.use_ipv6 = False # no IPv6 support at that time
            return self.handle_pre13(addrport, *args, **options)


    def init_sock(self):
        global PERSISTENT_SOCK
        existing_fd = os.environ.get('SERVER_FD')
        if not existing_fd:
            PERSISTENT_SOCK = socket.socket(socket.AF_INET6 if self.use_ipv6 else socket.AF_INET,
                                            socket.SOCK_STREAM)
            os.environ['SERVER_FD'] = str(PERSISTENT_SOCK.fileno())
        else:
            # print "Reusing existing socket (fd=%s)" % existing_fd
            PERSISTENT_SOCK = socket.fromfd(int(existing_fd),
                                            socket.AF_INET6 if self.use_ipv6 else socket.AF_INET,
                                            socket.SOCK_STREAM)

    def run_wsgi_server(self, addr, port, handler):
        """ replaces ``django.core.servers.basehttp.run`` """
        global PERSISTENT_SOCK
        kwargs = dict(bind_and_activate=False)
        if self.has_ipv6_support:
            kwargs['ipv6'] = self.use_ipv6
        httpd = WSGIServer((addr, port), WSGIRequestHandler, **kwargs)
        # patch the socket
        httpd.socket = PERSISTENT_SOCK

        try:
            httpd.server_bind()
        except WSGIServerException, e:
            if 'Errno 22' in str(e):
                # may have been bound, just emulate some stuff done in server_bind (like setting up environ)
                httpd.server_name = socket.getfqdn(addr)
                httpd.server_port = port
                httpd.setup_environ()
            else:
                raise
        httpd.server_activate()
        httpd.set_app(handler)
        httpd.serve_forever()


    def handle_pre13(self, addrport, *args, **options):
        """ modified version of ``runserver.Command.handle`` from Django 1.2.3's (r14552) """
        import django
        from django.core.servers.basehttp import run, AdminMediaHandler, WSGIServerException
        from django.core.handlers.wsgi import WSGIHandler
        try:
            from django.contrib.staticfiles.handlers import StaticFilesHandler
        except ImportError:
            StaticFilesHandler = None

        if args:
            raise CommandError('Usage is runserver %s' % self.args)
        if not addrport:
            addr = ''
            port = '8000'
        else:
            try:
                addr, port = addrport.split(':')
            except ValueError:
                addr, port = '', addrport
        if not addr:
            addr = '127.0.0.1'

        if not port.isdigit():
            raise CommandError("%r is not a valid port number." % port)

        use_reloader = options.get('use_reloader', True)
        admin_media_path = options.get('admin_media_path', '')
        shutdown_message = options.get('shutdown_message', '')
        use_static_handler = options.get('use_static_handler', True)
        insecure_serving = options.get('insecure_serving', False)
        quit_command = (sys.platform == 'win32') and 'CTRL-BREAK' or 'CONTROL-C'

        self.init_sock()

        def inner_run():
            from django.conf import settings
            from django.utils import translation
            print "Validating models..."
            self.validate(display_num_errors=True)
            print "\nDjango version %s, using settings %r" % (django.get_version(), settings.SETTINGS_MODULE)
            print "pserver %s is running at http://%s:%s/" % (__version__, addr, port)
            print "Quit the server with %s." % quit_command

            # django.core.management.base forces the locale to en-us. We should
            # set it up correctly for the first request (particularly important
            # in the "--noreload" case).
            translation.activate(settings.LANGUAGE_CODE)

            try:
                handler = WSGIHandler()
                allow_serving = (settings.DEBUG and use_static_handler or
                    (use_static_handler and insecure_serving))

                if StaticFilesHandler:
                    if (allow_serving and
                            "django.contrib.staticfiles" in settings.INSTALLED_APPS):
                        handler = StaticFilesHandler(handler)
                # serve admin media like old-school (deprecation pending)
                handler = AdminMediaHandler(handler, admin_media_path)
                self.run_wsgi_server(addr, int(port), handler)
            except WSGIServerException, e:
                # Use helpful error messages instead of ugly tracebacks.
                ERRORS = {
                    13: "You don't have permission to access that port.",
                    98: "That port is already in use.",
                    99: "That IP address can't be assigned-to.",
                }
                try:
                    error_text = ERRORS[e.args[0].args[0]]
                except (AttributeError, KeyError):
                    error_text = str(e)
                sys.stderr.write(self.style.ERROR("Error: %s" % error_text) + '\n')
                # Need to use an OS exit because sys.exit doesn't work in a thread
                os._exit(1)
            except KeyboardInterrupt:
                if shutdown_message:
                    print shutdown_message
                sys.exit(0)

        if use_reloader:
            from django.utils import autoreload
            autoreload.main(inner_run)
        else:
            inner_run()


    def run(self, *args, **options):
        """ Override the parent method which exists after Django r14553 (1.3 release) """
        self.init_sock()
        return super(Command, self).run(*args, **options)


    def inner_run(self, *args, **options):
        """ Override the parent method which exists after Django r14553 (1.3 release) """
        from django.conf import settings
        from django.utils import translation

        shutdown_message = options.get('shutdown_message', '')
        quit_command = (sys.platform == 'win32') and 'CTRL-BREAK' or 'CONTROL-C'

        self.stdout.write("Validating models...\n\n")
        self.validate(display_num_errors=True)
        self.stdout.write((
            "Django version %(version)s, using settings %(settings)r\n"
            "pserver %(ps_version)s is running at http://%(addr)s:%(port)s/\n"
            "Quit the server with %(quit_command)s.\n"
        ) % {
            "version": self.get_version(),
            "ps_version": __version__,
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
            self.run_wsgi_server(self.addr, int(self.port), handler)
        except KeyboardInterrupt:
            if shutdown_message:
                self.stdout.write("%s\n" % shutdown_message)
            sys.exit(0)

