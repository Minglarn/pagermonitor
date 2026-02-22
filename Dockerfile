FROM debian:bookworm-slim AS builder

RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    libusb-1.0-0-dev \
    pkg-config \
    xxd \
    && rm -rf /var/lib/apt/lists/*

# Build librtlsdr
WORKDIR /build/librtlsdr
RUN git clone https://github.com/steve-m/librtlsdr.git . \
    && mkdir build && cd build \
    && cmake -DCMAKE_INSTALL_PREFIX=/usr/local -DINSTALL_UDEV_RULES=ON .. \
    && make -j$(nproc) && make install

# Build multimon-ng
WORKDIR /build/multimon-ng
RUN git clone https://github.com/EliasOenal/multimon-ng.git . \
    && mkdir build && cd build \
    && cmake .. \
    && make -j$(nproc) && make install

# --- Runtime Stage ---
FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y \
    libusb-1.0-0 \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

ENV TZ="Europe/Stockholm"

# Copy binaries from builder
COPY --from=builder /usr/local/bin/rtl_fm /usr/local/bin/
COPY --from=builder /usr/local/bin/rtl_tcp /usr/local/bin/
COPY --from=builder /usr/local/bin/multimon-ng /usr/local/bin/
COPY --from=builder /usr/local/lib/librtlsdr* /usr/local/lib/

# Ensure ldconfig is run
RUN ldconfig

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run the python app
CMD ["python", "app.py"]
