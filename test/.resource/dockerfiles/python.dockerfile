FROM lscr.io/linuxserver/openssh-server as python

ENV PYTHONUNBUFFERED=1
RUN apk add --update --no-cache \
      python3 \
    && python3 -m ensurepip \
    && ln -sf python3 /usr/bin/python \
    && pip3 install --no-cache --upgrade \
      pip \
      setuptools
