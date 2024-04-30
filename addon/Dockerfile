ARG BUILD_FROM
ARG BUILD_UPSTREAM="0.2.0"
FROM vingerha/gazpar_2_mqtt:$BUILD_UPSTREAM


# Add rootfs
COPY rootfs/ /

COPY ./app /app
COPY ./app /app_temp


COPY entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh



