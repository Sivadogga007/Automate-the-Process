"""Common launcher for macOS, Linux and Windows. No stored SSH passwords."""
import os
import argparse
import hashlib
import json
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent


def healthy(endpoint, path='/health'):
    try:
        with urlopen(endpoint.rstrip('/') + path, timeout=2) as response:
            result = json.load(response)
            return result.get('status') == 'ok' if path == '/health' else isinstance(result.get('models'), list)
    except (OSError, ValueError):
        return False


def ssh_command(username, host, port):
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*', username):
        raise ValueError('Enter your Passpoli username only (no @ or spaces).')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]*', host):
        raise ValueError('Enter a hostname or IPv4 address only.')
    if not 1024 <= port <= 65535:
        raise ValueError('Local port must be between 1024 and 65535.')
    # Do not inherit unrelated LocalForward rules from the user's SSH config.
    # Standard key locations and ssh-agent still work; host aliases/config-only
    # identities are intentionally not used for this explicit host connection.
    return ['ssh', '-F', 'none', '-N', '-o', 'ExitOnForwardFailure=yes', '-o', 'ConnectTimeout=15',
            '-o', 'ServerAliveInterval=30', '-o', 'ServerAliveCountMax=3',
            '-L', f'127.0.0.1:{port}:127.0.0.1:11436', f'{username}@{host}']


def saved_ssh():
    path = ROOT / 'passpoli.json'
    if path.exists():
        settings = json.loads(path.read_text())
    else:
        settings = {'username': input('One-time setup: YOUR Passpoli username (example: 25m1234; do not include @passpoli): ').strip(),
                    'host': '10.119.2.11'}
    ssh_command(settings['username'], settings['host'], 11436)
    if not path.exists():
        path.write_text(json.dumps(settings, indent=2) + '\n')
        path.chmod(0o600)
    print('Using saved Passpoli account: ' + settings['username'] + '@' + settings['host'])
    return settings


def check_existing_runner():
    with socket.socket() as probe:
        try:
            probe.bind(('127.0.0.1', 47853))
        except OSError:
            raise RuntimeError('The networking app is already running (or port 47853 is occupied). '
                               'Go to its terminal and type close after the batch finishes, then start again. '
                               'Do not launch a second copy.')


def install_dependencies():
    requirements = ROOT / 'requirements.txt'
    digest = hashlib.sha256(requirements.read_bytes()).hexdigest()
    marker = Path(sys.prefix) / '.networking-requirements'
    if not marker.exists() or marker.read_text() != digest:
        print('Installing Python dependencies. Stay in this terminal and wait for setup to finish; this may take several minutes.', flush=True)
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', str(requirements)], check=True)
        marker.write_text(digest)


def main():
    from modules.panel_input import install
    install()
    if sys.version_info < (3, 11):
        raise RuntimeError('Python 3.11 or newer is required.')
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--execute', dest='execute', action='store_true', help='Send invitations (default)')
    mode.add_argument('--preview', dest='execute', action='store_false', help='Search without sending')
    parser.set_defaults(execute=True)
    tasks = parser.add_mutually_exclusive_group()
    tasks.add_argument('--career', action='store_true', help='Local career workspace')
    tasks.add_argument('--jobs', action='store_true', help='LinkedIn Easy Apply')
    tasks.add_argument('--network', action='store_true', help='Connection requests')
    tasks.add_argument('--panel', action='store_true', help='Open local control panel')
    parser.add_argument('--configured', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument('--pages', type=int, default=1)
    args = parser.parse_args()
    if (args.limit is not None and not 1 <= args.limit <= 100) or not 1 <= args.pages <= 10:
        parser.error('Use limit 1–100 and pages 1–10.')
    if not any((args.career,args.jobs,args.network,args.panel)):
        args.panel = True
    if args.panel:
        install_dependencies()
        from panel import main as open_panel
        open_panel()
        return
    check_existing_runner()
    print("Local career workspace; no invitations or submissions." if args.career else ("Easy Apply: eligible applications will be submitted unless --preview is used." if args.jobs else "This launcher SENDS invitations by default. Use --preview for a dry run."))
    install_dependencies()
    from setup import ensure_profile, ask_limit
    if not args.configured:
        ensure_profile(offer_personal=not args.jobs)
    from network import load_profile
    profile = load_profile()
    if args.jobs:
        from jobs import prepare_profile
        profile=prepare_profile(profile,interactive=not args.configured)
    if not args.career and args.limit is None:
        if args.jobs: print('For this task the limit counts jobs evaluated/attempted, not guaranteed submissions.')
        args.limit = ask_limit(task='jobs' if args.jobs else 'network')
    print('Contacts: ' + ', '.join(profile.get('contact_categories', [])))
    career_config = None
    if args.career or args.jobs:
        from career import settings
        career_config = settings()
    choice_endpoint = career_config['choice_endpoint'] if (args.career or args.jobs) else profile['endpoint']
    needs_choice = (args.career or args.jobs or profile['provider'] == 'openjev') and not healthy(choice_endpoint)
    needs_text = (args.career or args.jobs) and not healthy(career_config['text_endpoint'], '/api/tags')
    tunnel = None
    try:
        if needs_choice or needs_text:
            endpoint = urlsplit(choice_endpoint)
            if endpoint.scheme != 'http' or endpoint.hostname not in ('localhost', '127.0.0.1') or not endpoint.port or endpoint.path not in ('', '/'):
                raise RuntimeError('OpenJev is unavailable. Automatic SSH tunneling requires an http://127.0.0.1:PORT endpoint.')
            if not shutil.which('ssh'):
                raise RuntimeError('Install the OpenSSH client to connect to Passpoli.')
            print('A model connection is needed. Stay in this terminal. Connect to IITB Wi-Fi/VPN, then use YOUR Passpoli account.')
            settings = saved_ssh()
            command = ssh_command(settings['username'], settings['host'], endpoint.port)
            if not needs_choice:
                index = command.index('-L')
                del command[index:index+2]
            if needs_text:
                text_endpoint = urlsplit(career_config['text_endpoint'])
                if text_endpoint.scheme != 'http' or text_endpoint.hostname not in ('localhost','127.0.0.1') or not text_endpoint.port:
                    raise RuntimeError('Configured text model server is unavailable; check career-settings.json.')
                command[-1:-1] = ['-L', f'127.0.0.1:{text_endpoint.port}:127.0.0.1:11435']
            print('SSH may ask for your Passpoli password or key passphrase. Typing is hidden; press Enter when done. Saved SSH keys/ssh-agent are used automatically. No password is saved in this app. Verify any first-time host fingerprint with your administrator.')
            print('The next prompt may be from SSH: type your password there (no characters will show), then press Enter.\n'
                  'If no password prompt appears, your saved key may have signed you in automatically.\n'
                  'Wait here for the model connection message; do not open another launcher.', flush=True)
            if os.environ.get('CAREERDESK_PANEL'):
                if os.name!='nt':
                    import shlex
                    helper=ROOT/'private/ssh-askpass.sh'
                    helper.parent.mkdir(exist_ok=True)
                    helper.write_text('#!/bin/sh\nexec '+shlex.quote(sys.executable)+' '+shlex.quote(str(ROOT/'modules/panel_askpass.py'))+' "$@"\n')
                    helper.chmod(0o700)
                    os.environ.update(SSH_ASKPASS=str(helper),SSH_ASKPASS_REQUIRE='force',DISPLAY=os.environ.get('DISPLAY',':0'))
                else:
                    command[1:1]=['-o','BatchMode=yes']
                print('Connecting to Passpoli. Any password or key passphrase request will appear in the panel.',flush=True)
            tunnel = subprocess.Popen(command)
            deadline = time.monotonic() + 180
            while ((needs_choice and not healthy(choice_endpoint)) or
                   (needs_text and not healthy(career_config['text_endpoint'], '/api/tags'))):
                if tunnel.poll() is not None:
                    raise RuntimeError('SSH tunnel exited. Check SSH credentials, campus/VPN access and local port availability.')
                if time.monotonic() >= deadline:
                    raise RuntimeError('Timed out waiting for OpenJev. Verify the server is running on Passpoli.')
                time.sleep(1)
            # Let SSH report a bind failure before accepting another process's listener.
            time.sleep(0.3)
            if tunnel.poll() is not None:
                raise RuntimeError('SSH tunnel exited; stopped rather than using an unexpected listener.')
            print('Model connection is ready. Continue in this terminal.')
        if args.career:
            from career import menu
            menu()
            return
        if args.jobs:
            print('Close any old app Chrome window. Normal Chrome can remain open.')
            input('Press Enter to open LinkedIn Easy Apply: ')
            from jobs import main as apply_jobs
            apply_jobs(args.limit,args.pages,args.execute)
            return
        print('Close the Chrome window previously opened by THIS networking app if it is still open. Your normal Chrome windows can stay open.')
        input('After closing any old app browser, press Enter to start: ')
        print('Mode: ' + ('SEND invitations' if args.execute else 'PREVIEW only; no invitations'))
        command = [sys.executable, str(ROOT / 'network.py'), '--limit', str(args.limit),
                   '--pages', str(args.pages), '--keep-open']
        command.append('--execute' if args.execute else '--preview')
        subprocess.run(command, cwd=ROOT, check=True)
    finally:
        if tunnel is not None and tunnel.poll() is None:
            tunnel.terminate()
            try:
                tunnel.wait(timeout=5)
            except subprocess.TimeoutExpired:
                tunnel.kill()
                tunnel.wait()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nStopped.')
        sys.exit(130)
    except (EOFError, OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print('Stopped: ' + str(error), file=sys.stderr)
        sys.exit(1)
