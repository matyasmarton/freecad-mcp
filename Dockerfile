FROM debian:bookworm-slim
WORKDIR /app/
RUN apt-get update && apt-get install -y \
python3 \
python3-pip \
python3-venv \
freecad


ENV PYTHONPATH="/usr/lib/freecad-python3/lib"


RUN python3 -m venv --system-site-packages app_env
RUN app_env/bin/python -m pip install mcp
