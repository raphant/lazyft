FROM freqtradeorg/freqtrade:2022.12 as lazyft_base

USER root
RUN apt update && apt install rsync ssh nodejs npm -y
#RUN bash build.sh
#RUN chown -R ftuser:ftuser /usr/local/lib/python3.9/site-packages/
USER ftuser
WORKDIR /lft
COPY --chown=ftuser:ftuser . /lft
RUN pip install --user --no-cache-dir --no-build-isolation -e .
RUN pip install jupyter jupyterlab

COPY .env .env
COPY ./docker_scripts/entrypoint.sh .
COPY .jupyter /home/ftuser/.jupyter
# RUN bash -c 'source ./.env'
#RUN . ./.env
ENTRYPOINT ["/ftworkdir/entrypoint.sh"]

#COPY --chown=ftuser:ftuser ./lazyft ./lazyft
#COPY --chown=ftuser:ftuser ./lft_rest ./lft_rest

# copy local ssh keys to remote host
# Authorize SSH Host
RUN mkdir -p /home/ftuser/.ssh && \
    chmod 0700 /home/ftuser/.ssh

SHELL ["/bin/bash", "-c"]
# Add the keys and set permissions
RUN ssh-keygen -q -t rsa -N '' -f /home/ftuser/.ssh/id_rsa
RUN source .env && echo "$SSH_PUB_KEY" > /home/ftuser/.ssh/id_rsa.pub && \
    chmod 600 /home/ftuser/.ssh/id_rsa && \
    chmod 600 /home/ftuser/.ssh/id_rsa.pub && unset SSH_PUB_KEY
ENTRYPOINT ["freqtrade"]


