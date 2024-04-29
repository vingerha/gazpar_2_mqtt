ARG BUILD_FROM
ARG BUILD_UPSTREAM="0.2.0"
FROM vingerha/gazpar_2_mqtt:$BUILD_UPSTREAM

##################
# 2 Modify Image #
##################

# Set S6 wait time
ENV S6_CMD_WAIT_FOR_SERVICES=1 \
    S6_CMD_WAIT_FOR_SERVICES_MAXTIME=0 \
    S6_SERVICES_GRACETIME=0

ENV TZ=Europe/Paris

##################
# 3 Install apps #
##################

# Add rootfs
COPY rootfs/ /

COPY ./app /app
COPY ./app /app_temp

RUN apt-get update && \ 
	apt-get install -y curl unzip xvfb libxi6 libgconf-2-4  && \ 
    apt-get update && \
    apt-get install -y chromium -y  && \
    apt-get update && \	
    rm -rf /var/lib/apt/lists/*
	    
RUN mkdir -p /data

ENV LANG en_US.UTF-8
ENV LC_ALL en_US.UTF-8
ENV TZ=Europe/Paris

# Install python requirements
RUN pip3 install --upgrade pip && \
    pip3 install --no-cache-dir -r /app/requirement.txt


################
# 4 Entrypoint #
################

COPY entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh
ENTRYPOINT ["entrypoint.sh"]
CMD ["python3", "app/gazpar2mqtt.py"]

############
# 5 Labels #
############

LABEL \
  io.hass.version="0.2.2" \
  io.hass.type="addon" \
  io.hass.arch="armhf|aarch64|i386|amd64"


