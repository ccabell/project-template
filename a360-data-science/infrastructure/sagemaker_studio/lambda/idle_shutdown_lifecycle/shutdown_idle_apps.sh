#!/bin/bash

set -eux

ASI_VERSION=0.3.1

IDLE_TIME_IN_SECONDS=3600
IGNORE_CONNECTIONS=True
SKIP_TERMINALS=False

JL_HOSTNAME=0.0.0.0
JL_PORT=8888
JL_BASE_URL=/jupyterlab/default/
CONDA_HOME=/opt/conda/bin
LOG_FILE=/var/log/apps/app_container.log
SOLUTION_DIR=/var/tmp/auto-stop-idle
STATE_FILE=$SOLUTION_DIR/auto_stop_idle.st
PYTHON_PACKAGE=sagemaker_studio_jlab_auto_stop_idle-$ASI_VERSION.tar.gz
PYTHON_SCRIPT_PATH=$SOLUTION_DIR/sagemaker_studio_jlab_auto_stop_idle/auto_stop_idle.py

status="$(dpkg-query -W --showformat='${db:Status-Status}' "cron" 2>&1)" || true 
if [ ! $? = 0 ] || [ ! "$status" = installed ]; then
	sudo /bin/bash -c "echo '#!/bin/sh
	exit 0' > /usr/sbin/policy-rc.d"

	echo "Installing cron..."
	sudo apt install cron
else
	echo "Package cron is already installed."
        sudo service cron restart
fi

sudo mkdir -p $SOLUTION_DIR

echo "Downloading autostop idle Python package..."
curl -LO --output-dir /var/tmp/ https://github.com/aws-samples/sagemaker-studio-apps-lifecycle-config-examples/releases/download/v$ASI_VERSION/$PYTHON_PACKAGE
sudo $CONDA_HOME/pip install -U -t $SOLUTION_DIR /var/tmp/$PYTHON_PACKAGE

sudo /bin/bash -c "echo 'AWS_CONTAINER_CREDENTIALS_RELATIVE_URI=$AWS_CONTAINER_CREDENTIALS_RELATIVE_URI' >> /etc/environment"

echo "Adding autostop idle Python script to crontab..."
echo "*/2 * * * * /bin/bash -ic '$CONDA_HOME/python $PYTHON_SCRIPT_PATH --idle-time $IDLE_TIME_IN_SECONDS --hostname $JL_HOSTNAME \
--port $JL_PORT --base-url $JL_BASE_URL --ignore-connections $IGNORE_CONNECTIONS \
--skip-terminals $SKIP_TERMINALS --state-file-path $STATE_FILE >> $LOG_FILE'" | sudo crontab -