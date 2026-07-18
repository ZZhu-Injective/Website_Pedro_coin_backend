import os
import sys

from django.apps import AppConfig


class MyappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'myapp'

    def ready(self):
        # Warm the Pedro NFT holder cache in the background at boot so the
        # first visitor after a (re)start doesn't wait on the full contract-
        # state scan. Stale-while-revalidate keeps it warm afterwards — see
        # _fetch_pedro_nft_count in views.py. This replaces the cron job.
        #
        # ready() also runs during manage.py commands (migrate, collectstatic,
        # the refresh_nft_holders command, tests…) where a network scan would
        # be pointless or harmful, so only warm up when actually serving web
        # traffic. The guard fails closed: under any unrecognised launcher we
        # simply skip and fall back to the cold-on-first-request behaviour.
        argv = sys.argv or ['']
        prog = os.path.basename(argv[0])
        # runserver: ready() runs in both the autoreload watcher and the child;
        # RUN_MAIN is only set in the child, so warm exactly once.
        is_runserver = 'runserver' in argv and os.environ.get('RUN_MAIN') == 'true'
        is_gunicorn = prog.startswith('gunicorn')
        if not (is_runserver or is_gunicorn):
            return

        try:
            # Lazy import: avoid pulling views (and its heavy import chain) at
            # module-load time / into manage.py commands.
            from .views import _trigger_async_holder_refresh

            # Non-blocking — spawns its own daemon thread, so startup isn't
            # delayed by the scan.
            _trigger_async_holder_refresh()
        except Exception:
            # Never let a boot-time warm-up break startup.
            pass
