FROM vingerha/gazpar_2_mqtt

##################
#  Install apps  #
##################

COPY rootfs/ /

RUN apt-get update && \
	apt-get install -y jq
	
################
# 4 Entrypoint #
################
VOLUME [ "/data" ]
VOLUME [ "/app" ]
COPY entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["entrypoint.sh"]
CMD ["entrypoint.sh"]

CMD ["python3", "app/gazpar2mqtt.py"]

############
# 5 Labels #
############

LABEL \
  io.hass.version="0.5.0" \
  io.hass.type="addon" \
  io.hass.arch="armv7|amd64|arm64"


