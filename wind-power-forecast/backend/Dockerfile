FROM continuumio/miniconda3

ARG PIP_INDEX_URL=https://pypi.org/simple

RUN apt-get update && apt-get install -y curl postgresql-client && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create conda env with Python only (fast, reliable)
RUN conda create -n wind-power-env python=3.9 pip -y && conda clean --all --yes

ENV PATH /opt/conda/envs/wind-power-env/bin:$PATH

# 受控构建机可以通过构建参数切换到内部软件源
RUN pip config set global.index-url ${PIP_INDEX_URL} && \
    pip config set global.timeout 600

# Copy requirements and install in stages (large ML packages separately)
COPY requirements.txt .

# Install small/medium packages first (most will succeed on first try)
RUN pip install --no-cache-dir --retries 5 \
    alembic==1.14.1 argon2-cffi==23.1.0 argon2-cffi-bindings==21.2.0 \
    async-timeout==5.0.1 bcrypt==4.2.1 bidict==0.23.1 blinker==1.9.0 \
    certifi==2025.1.31 cffi==1.17.1 charset-normalizer==3.4.1 click==8.1.7 \
    colorama==0.4.6 contourpy==1.3.0 cryptography==44.0.0 cycler==0.12.1 \
    dnspython==2.7.0 eventlet==0.38.0 flask==2.3.2 flask-cors==3.0.10 \
    flask-socketio==5.4.1 fonttools==4.55.1 greenlet==3.1.1 \
    h11==0.14.0 idna==3.10 importlib-metadata==8.5.0 importlib-resources==6.4.5 \
    itsdangerous==2.2.0 jinja2==3.1.4 joblib==1.4.2 kiwisolver==1.4.7 \
    mako==1.3.9 markupsafe==3.0.2 packaging==24.2 \
    paramiko==3.5.0 pycparser==2.22 pycryptodome==3.21.0 pyjwt==2.8.0 \
    pynacl==1.5.0 pyparsing==3.2.0 python-dateutil==2.9.0.post0 \
    python-dotenv==1.0.0 python-engineio==4.10.1 python-multipart==0.0.20 \
    python-socketio==5.11.4 pytz==2024.2 redis==4.5.5 requests==2.32.3 \
    schedule==1.2.2 six==1.16.0 sqlalchemy==2.0.38 threadpoolctl==3.5.0 \
    typing-extensions==4.12.2 tzdata==2024.2 urllib3==2.3.0 \
    werkzeug==2.3.3 wsproto==1.2.0 zipp==3.21.0 \
    gunicorn==20.1.0 flask-jwt-extended==4.7.1 apscheduler==3.11.0 \
    psutil==5.9.0 gevent==23.9.1 gevent-websocket==0.10.1

# Install numpy + scipy + pandas (medium-large, ~70MB combined)
RUN pip install --no-cache-dir --retries 5 \
    numpy==1.26.4 scipy==1.13.1 pandas==2.2.3

# Install matplotlib + pillow + seaborn + psycopg2-binary + lightgbm (medium)
RUN pip install --no-cache-dir --retries 5 \
    matplotlib==3.9.3 pillow==11.0.0 seaborn==0.13.2 \
    psycopg2-binary==2.9.10 lightgbm==4.5.0

# Install scikit-learn (~13MB)
RUN pip install --no-cache-dir --retries 5 scikit-learn==1.5.2

# Install xgboost (~224MB) - largest package, standalone for retry isolation
RUN pip install --no-cache-dir --retries 5 xgboost==2.1.4

# Install catboost (~99MB) - second largest
RUN pip install --no-cache-dir --retries 5 catboost==1.2.7

COPY . /app/

RUN sed -i 's/\r$//' /app/docker-entrypoint.sh && \
    chmod +x /app/docker-entrypoint.sh && \
    sed -i 's/\r$//' /app/auto_scripts/scripts/middle/auto_pre_train.py && \
    sed -i 's/\r$//' /app/auto_scripts/scripts/short/auto_pre_train.py && \
    sed -i 's/\r$//' /app/auto_scripts/scripts/supershort/train_supershort.py && \
    sed -i 's/\r$//' /app/auto_scripts/scripts/supershort/predict_supershort.py && \
    find /app -name "*.sh" -exec sed -i 's/\r$//' {} +

EXPOSE 5000

CMD ["/app/docker-entrypoint.sh"]
