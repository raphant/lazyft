FROM freqtradeorg/freqtrade:develop as ftworkdir

COPY --chown=ftuser:ftuser . /ftworkdir
WORKDIR /ftworkdir
USER root
RUN apt install rsync ssh -y
USER ftuser
#RUN bash build.sh
#RUN chown -R ftuser:ftuser /usr/local/lib/python3.9/site-packages/
USER ftuser
RUN pip install --user --no-cache-dir --no-build-isolation -e lazyft_pkg -e indicatormix -e coin_based_strategy -e lft_rest jupyter
#RUN cd buildfiles && pip install -r requirements.txt
WORKDIR /ftworkdir
#ENTRYPOINT ["/usr/bin/env"]
#CMD ["uvicorn", "lft_rest.main:app", "--reload", "--host", "0.0.0.0"]

FROM rest as jupyter
RUN pip install --user jupyterlab
WORKDIR /ftworkdir
#ENTRYPOINT ["/usr/bin/env"]
#CMD ["jupyter", "lab", "--ip", "0.0.0.0", "--autoreload"]
