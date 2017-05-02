FROM python:2.7-alpine

COPY ./requirements.txt /requirements.txt
RUN pip install -r /requirements.txt

COPY ./labbot.py /labbot.py