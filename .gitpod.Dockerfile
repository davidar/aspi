FROM continuumio/miniconda3

# http://dl.mercurylang.org/deb/
RUN apt update && apt install -y wget ca-certificates gnupg
RUN wget https://paul.bone.id.au/paul.asc -O- | apt-key add -
RUN echo deb http://dl.mercurylang.org/deb/ buster main > /etc/apt/sources.list.d/mercury.list
RUN apt update && apt install -y mercury-recommended
