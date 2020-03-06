FROM python:3.6
WORKDIR /app
ADD requirements.txt /app/
RUN pip install -r requirements.txt
ADD index_pubmed.py  /app/
ADD https://raw.githubusercontent.com/vishnubob/wait-for-it/master/wait-for-it.sh /app/wait_for_it.sh
