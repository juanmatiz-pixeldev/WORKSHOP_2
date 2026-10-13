FROM apache/airflow:3.1.8
USER airflow
COPY requirements.txt /requirements.txt
# Constraints oficiales de Airflow 3.1.8 / Python 3.12 -> evita conflictos de versiones
RUN pip install --no-cache-dir -r /requirements.txt \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-3.1.8/constraints-3.12.txt"
