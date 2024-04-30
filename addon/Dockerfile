FROM vingerha/gazpar_2_mqtt

##################
#  Install apps  #
##################

# Add rootfs
COPY rootfs/ /

COPY ./app /app
COPY ./app /app_temp

################
# 4 Entrypoint #
################

COPY entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh
ENTRYPOINT ["entrypoint.sh"]
CMD ["entrypoint.sh"]
VOLUME [ "/data" ]
VOLUME [ "/app" ]
CMD ["python3", "app/gazpar2mqtt.py"]

############
# 5 Labels #
############

LABEL \
  io.hass.version="0.2.0" \
  io.hass.type="addon" \
  io.hass.arch="armv7|amd64|arm64"


