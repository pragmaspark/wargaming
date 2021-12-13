FROM lscr.io/linuxserver/openssh-server

ENV PYTHONUNBUFFERED=1
RUN apk add --update --no-cache \
      python3 \
      git \
    && python3 -m ensurepip \
    && ln -sf python3 /usr/bin/python \
    && pip3 install --no-cache --upgrade \
      pip \
      setuptools
RUN git clone https://github.com/avast/pytest-docker.git bw
