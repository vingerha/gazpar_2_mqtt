FROM python:3.11-slim-bookworm

COPY ./app /app
COPY ./app /app_temp

RUN apt-get update && \ 
	apt-get install -y curl unzip xvfb libxi6 libgconf-2-4  && \ 
    apt-get update && \
    apt-get install -y chromium -y  && \
    apt-get update && \	
    rm -rf /var/lib/apt/lists/*

ARG BASHIO_VERSION="0.16.2"	
RUN mkdir -p /data && \
	mkdir -p /tmp/bashio && \
	curl -f -L -s -S "https://github.com/hassio-addons/bashio/archive/v${BASHIO_VERSION}.tar.gz" | tar -xzf - --strip 1 -C /tmp/bashio && \
	mv /tmp/bashio/lib /usr/lib/bashio && \
	ln -s /usr/lib/bashio/bashio /usr/bin/bashio && \
	rm -rf /tmp/bashio
	    
RUN mkdir -p /data

ENV LANG en_US.UTF-8
ENV LC_ALL en_US.UTF-8
ENV TZ=Europe/Paris

# Install python requirements
RUN pip3 install --upgrade pip && \
    pip3 install --no-cache-dir -r /app/requirement.txt

COPY entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh
ENTRYPOINT ["entrypoint.sh"]
CMD ["python3", "app/gazpar2mqtt.py"]