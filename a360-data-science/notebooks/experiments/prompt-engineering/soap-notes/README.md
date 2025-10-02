# SOAP Note Prompt Evaluation
This repository contains the code to evaluate prompts for the SOAP note generation using LLM-as-a-Judge approach.
## Installation Steps
The code was developed and tested inside the Sagemaker Studio JupyterLab space, therefore the steps below are supposed to be executed there:
1. If working in a newly created space, run:
   ```sh
   conda init
   ```
2. Deactivate current environment (if any):
   ```sh
   conda deactivate
   ```
3. Create and active new conda environment:
   ```sh
    conda env create -f environment.yaml -y && conda activate soap-notes
    ```
4. Register new environment as a Jupyter Kernel:
    ```sh
    python -m ipykernel install --user --name soap-notes --display-name "user-env:(py312-soap-notes)"
    ```

Now you can select the kernel `user-env:(py312-soap-notes)` before running the notebooks to use the correct environment.
## Usage
- `01-Data Pre-Processing.ipynb` - demonstrates how to prepare the data for evaluation
- `02-LLM-Judge-Evaluation.ipynb` - documented notebook that explains how to run evaluation jobs on the example of LLM judge comparison
- `03-Prompt-Evaluation.ipynb` - notebook used to evaluate different prompt versions