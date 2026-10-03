ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:latest
FROM ${BUILD_FROM}

LABEL \
  io.hass.version="1.0.6" \
  io.hass.type="app" \
  io.hass.arch="amd64"

RUN apk add --no-cache nodejs npm

COPY server/ /opt/server/
WORKDIR /opt/server
RUN npm install --production

RUN mkdir -p /data/smartcafe-server

COPY run.sh /
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
