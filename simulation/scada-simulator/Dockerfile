FROM c104-scada-client:v1.0

RUN apt-get update && apt-get install -y \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY simulation/scada-simulator/scada_simulator_server.py .

ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

EXPOSE 2404

CMD ["python3", "scada_simulator_server.py"]
