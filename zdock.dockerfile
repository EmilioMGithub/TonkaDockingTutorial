FROM ubuntu:14.04

RUN apt-get update && \
    apt-get install -y \
    libc6 \
    libstdc++6 \
    perl \
    wget \
    && apt-get clean

RUN wget https://old-releases.ubuntu.com/ubuntu/pool/universe/g/gcc-3.4/gcc-3.4-base_3.4.6-6ubuntu3_amd64.deb && \
    wget https://old-releases.ubuntu.com/ubuntu/pool/universe/g/gcc-3.4/libg2c0_3.4.6-6ubuntu3_amd64.deb && \
    dpkg -i gcc-3.4-base_3.4.6-6ubuntu3_amd64.deb libg2c0_3.4.6-6ubuntu3_amd64.deb || apt-get install -f -y && \
    rm gcc-3.4-base_3.4.6-6ubuntu3_amd64.deb libg2c0_3.4.6-6ubuntu3_amd64.deb

WORKDIR /opt/zdock

COPY zdock3.0.2_linux_x64.tar.gz /opt/zdock/

RUN tar -xzvf zdock3.0.2_linux_x64.tar.gz && \
    rm zdock3.0.2_linux_x64.tar.gz

RUN SUBDIR=$(ls -d */ | head -n 1) && \
    if [ -d "$SUBDIR" ]; then \
        echo "Detected subdir: $SUBDIR"; \
        mv "$SUBDIR"/* . ; \
        rmdir "$SUBDIR"; \
    fi

RUN chmod +x zdock create_lig uniCHARMM mark_sur create.pl block.pl || true 

WORKDIR /data

ENTRYPOINT ["/opt/zdock/zdock"]