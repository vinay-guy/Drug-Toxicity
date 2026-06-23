# Dockerfile for ToxPredict app
# Uses Miniconda to install RDKit from conda-forge (Python 3.10)

FROM continuumio/miniconda3:23.7.2

# Set workdir
WORKDIR /app

# Copy repository
COPY . /app

# Install system deps (small) and create conda env with RDKit
RUN conda update -n base -c defaults conda -y \
    && conda install -n base -c conda-forge mamba -y \
    && mamba create -n toxpredict python=3.10 -y -c conda-forge rdkit "numpy<2" \
    && conda clean -afy

# Install Python packages (pip) into the conda env
RUN conda run -n toxpredict pip install --no-cache-dir -r requirements.txt

# Ensure the conda env's bin is on PATH
ENV PATH=/opt/conda/envs/toxpredict/bin:$PATH
ENV PYTHONPATH=src

# Expose Streamlit port
EXPOSE 8501

# Default command
CMD ["conda", "run", "-n", "toxpredict", "streamlit", "run", "src/app.py", "--server.port=8501", "--server.headless=true", "--server.enableCORS=false"]
