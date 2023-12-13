FROM python:slim-bullseye@sha256:7254d660217c7bb817122a030c3d0108f6cd66ef4208b55a0787750b13382d56

COPY requirements.txt requirements.txt

# Install Streamlit dependencies
# From 'Deploy Streamlit using Docker'
# https://docs.streamlit.io/knowledge-base/tutorials/deploy/docker
RUN apt-get update && apt-get install -y \
									build-essential \
									curl \
									software-properties-common \
									git \
    && rm -rf /var/lib/apt/lists/*

# Install app dependencies
RUN add-apt-repository -y ppa:mc3man/trusty-media \
	&& apt-get update || true \
	&& apt-get install -y ffmpeg \
						pulseaudio \
						libsdl2-dev \
						|| true \
	&& pip install -r requirements.txt \
	&& rm -rf /var/lib/apt/lists/*

COPY meh.py meh.py

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

# Disable usage statistics
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Turn off file watcher
ENV STREAMLIT_SERVER_FILE_WATCHER_TYPE=none

ENTRYPOINT ["streamlit", "run", "meh.py", "--server.port=8501", "--server.address=0.0.0.0"]