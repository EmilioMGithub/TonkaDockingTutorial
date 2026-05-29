FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    libc6 \
    libgcc-s1 \
    libfftw3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY HDOCKlite-v1.1/hdock /usr/local/bin/hdock
COPY HDOCKlite-v1.1/createpl /usr/local/bin/createpl

RUN chmod +x /usr/local/bin/hdock /usr/local/bin/createpl

WORKDIR /docking

ENTRYPOINT ["/bin/sh", "-c"]