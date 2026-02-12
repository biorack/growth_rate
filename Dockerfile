# growth_rate/Dockerfile
FROM condaforge/miniforge3:latest

WORKDIR /app

COPY environment.yml .
RUN conda env create -f environment.yml && conda clean -afy

COPY . .

SHELL ["conda", "run", "-n", "growth-rate-api", "/bin/bash", "-c"]

EXPOSE 5000

CMD ["conda", "run", "-n", "growth-rate-api", "gunicorn", "-b", "0.0.0.0:5000", "wsgi:app"]