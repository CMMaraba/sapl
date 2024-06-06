#!/usr/bin/env bash
# As seen in http://tutos.readthedocs.org/en/latest/source/ndg.html

#
## intell -- 17/02/2024
#
#source /home/cmm/.bashrc
#source `which virtualenvwrapper.sh`
export VIRTUALENVWRAPPER_PYTHON=/usr/bin/python3
export WORKON_HOME=/var/interlegis/.virtualenvs
export PROJECT_HOME=/var/interlegis
source /usr/local/bin/virtualenvwrapper.sh
workon sapl

SAPL_DIR="/var/interlegis/sapl"

# Seta um novo diretorio como raiz, caso tenha sido usado um parametro na linha de comando
if [ "$1" ]; then
    SAPL_DIR="$1"
fi

NAME="SAPL"                                        # Name of the application (*)
DJANGODIR=/var/interlegis/sapl/                    # Django project directory (*)
SOCKFILE=/var/interlegis/sapl/run/gunicorn.sock    # we will communicate using this unix socket (*)
USER=`whoami`                                      # the user to run as (*)
GROUP=`whoami`                                     # the group to run as (*)
NUM_WORKERS=13                                     # how many worker processes should Gunicorn spawn (*)
                                                   # NUM_WORKERS = 2 * CPUS + 1
TIMEOUT=300
MAX_REQUESTS=100                                   # number of requests before restarting worker
DJANGO_SETTINGS_MODULE=sapl.settings               # which settings file should Django use (*)
DJANGO_WSGI_MODULE=sapl.wsgi                       # WSGI module name (*)

echo "Starting $NAME as `whoami` on base dir $SAPL_DIR"

# Create the run directory if it doesn't exist
RUNDIR=$(dirname $SOCKFILE)
test -d $RUNDIR || mkdir -p $RUNDIR

# Start your Django Unicorn
# Programs meant to be run under supervisor should not daemonize themselves (do not use --daemon)
exec gunicorn ${DJANGO_WSGI_MODULE}:application \
  --name $NAME \
  --log-level debug \
  --timeout $TIMEOUT \
  --workers $NUM_WORKERS \
  --max-requests $MAX_REQUESTS \
  --user $USER \
  --access-logfile /var/log/sapl/access.log \
  --error-logfile /var/log/sapl/error.log \
  --bind=unix:$SOCKFILE \
#  --daemon
