# Default environment settings
ENVIRONMENT ?= development
AWS_PROFILE ?= default
DEPLOY_PIPELINE ?= true
DEPLOY_EXECUTION ?= true
DEPLOY_RESULTS ?= true

# Stack prefix from configuration
STACK_PREFIX = A360-
STUDIO_STACK_NAME = DevAe360DataScience-SageMakerStudioStack
TRANSCRIPT_ANALYSIS_STACK_NAME = TranscriptionAnalysisStack

# CDK command
CDK = npx aws-cdk

# Set verbose output for debugging
ifdef VERBOSE
	V = --verbose
endif

.PHONY: help
help:
	@echo "SageMaker Infrastructure Deployment"
	@echo
	@echo "Usage:"
	@echo "  make [target] [ENVIRONMENT=development] [AWS_PROFILE=default]"
	@echo
	@echo "Targets:"
	@echo "  studio                         Deploy SageMaker Studio infrastructure"
	@echo "  transcript-analysis            Deploy Transcript Analysis infrastructure"
	@echo "  pipeline                       Deploy SageMaker Pipeline infrastructure"
	@echo "  pipeline-only                  Deploy only the main Pipeline stack"
	@echo "  execution-only                 Deploy only the Pipeline Execution stack"
	@echo "  results-only                   Deploy only the Inference Results stack"
	@echo "  destroy-pipeline               Destroy Pipeline infrastructure"
	@echo "  destroy-studio                 Destroy Studio infrastructure"
	@echo "  destroy-transcript-analysis    Destroy Transcript Analysis infrastructure"
	@echo "  synth-pipeline                 Synthesize Pipeline CloudFormation template"
	@echo "  synth-studio                   Synthesize Studio CloudFormation template"
	@echo "  synth-transcript-analysis      Synthesize Transcript Analysis CloudFormation template"
	@echo "  list                           List deployed stacks"
	@echo "  setup                          Setup development environment"
	@echo
	@echo "Environment Variables:"
	@echo "  ENVIRONMENT         Deployment environment (default: development)"
	@echo "  AWS_PROFILE         AWS profile to use (default: default)"
	@echo "  DEPLOY_PIPELINE     Whether to deploy Pipeline stack (default: true)"
	@echo "  DEPLOY_EXECUTION    Whether to deploy Execution stack (default: true)"
	@echo "  DEPLOY_RESULTS      Whether to deploy Results stack (default: true)"
	@echo "  VERBOSE             Enable verbose output if set to any value"
	@echo
	@echo "Examples:"
	@echo "  make pipeline ENVIRONMENT=production AWS_PROFILE=prod-profile"
	@echo "  make pipeline-only ENVIRONMENT=development AWS_PROFILE=dev-profile"

.PHONY: check-config
check-config:
	@if [ ! -f "examples/model_train_deploy_pipeline/project_config.json" ]; then \
		mkdir -p examples/model_train_deploy_pipeline; \
		echo "{}" > examples/model_train_deploy_pipeline/project_config.json; \
		echo "Created empty project_config.json"; \
	fi

.PHONY: python-check
python-check:
	@uv pip list | grep -q aws-cdk-lib || (echo "Missing aws-cdk-lib. Run 'uv pip install aws-cdk-lib constructs'" && exit 1)

.PHONY: studio
studio: python-check
	@echo "Deploying SageMaker Studio infrastructure..."
	@export ENVIRONMENT=$(ENVIRONMENT); \
	export AWS_PROFILE=$(AWS_PROFILE); \
	$(CDK) deploy $(V) --app "uv run python3 studio_app.py" --context-file cdk-studio.json "$(STUDIO_STACK_NAME)" --require-approval never

.PHONY: transcript-analysis
transcript-analysis: python-check
	@echo "Deploying Transcript Analysis infrastructure..."
	@export ENVIRONMENT=$(ENVIRONMENT); \
	$(CDK) deploy $(V) --app "uv run python3 quicksight_app.py" --profile "$(AWS_PROFILE)" --require-approval never "$(TRANSCRIPT_ANALYSIS_STACK_NAME)"

.PHONY: pipeline
pipeline: check-config python-check
	@echo "Deploying SageMaker Pipeline infrastructure..."
	@export ENVIRONMENT=$(ENVIRONMENT); \
	export AWS_PROFILE=$(AWS_PROFILE); \
	$(CDK) deploy $(V) --app "uv run python3 pipeline_app.py" --context-file cdk-pipeline.json \
		"$(STACK_PREFIX)SageMakerPipelineStack" \
		"$(STACK_PREFIX)SageMakerPipelineExecutionStack" \
		"$(STACK_PREFIX)SageMakerInferenceResultsStack" \
		--require-approval never

.PHONY: pipeline-only
pipeline-only: check-config python-check
	@echo "Deploying main SageMaker Pipeline stack only..."
	@export ENVIRONMENT=$(ENVIRONMENT); \
	export AWS_PROFILE=$(AWS_PROFILE); \
	$(CDK) deploy $(V) --app "uv run python3 pipeline_app.py" --context-file cdk-pipeline.json \
		"$(STACK_PREFIX)SageMakerPipelineStack" \
		--exclusively \
		--require-approval never

.PHONY: execution-only
execution-only: check-config python-check
	@echo "Deploying SageMaker Pipeline Execution stack only..."
	@export ENVIRONMENT=$(ENVIRONMENT); \
	export AWS_PROFILE=$(AWS_PROFILE); \
	$(CDK) deploy $(V) --app "uv run python3 pipeline_app.py" --context-file cdk-pipeline.json \
		"$(STACK_PREFIX)SageMakerPipelineExecutionStack" \
		--exclusively \
		--require-approval never

.PHONY: results-only
results-only: check-config python-check
	@echo "Deploying SageMaker Inference Results stack only..."
	@export ENVIRONMENT=$(ENVIRONMENT); \
	export AWS_PROFILE=$(AWS_PROFILE); \
	$(CDK) deploy $(V) --app "uv run python3 pipeline_app.py" --context-file cdk-pipeline.json \
		"$(STACK_PREFIX)SageMakerInferenceResultsStack" \
		--exclusively \
		--require-approval never

.PHONY: destroy-pipeline
destroy-pipeline: python-check
	@echo "Destroying SageMaker Pipeline infrastructure..."
	@export AWS_PROFILE=$(AWS_PROFILE); \
	$(CDK) destroy $(V) --app "uv run python3 pipeline_app.py" --context-file cdk-pipeline.json \
		"$(STACK_PREFIX)SageMakerInferenceResultsStack" \
		"$(STACK_PREFIX)SageMakerPipelineExecutionStack" \
		"$(STACK_PREFIX)SageMakerPipelineStack" \
		--force

.PHONY: destroy-studio
destroy-studio: python-check
	@echo "Destroying SageMaker Studio infrastructure..."
	@export AWS_PROFILE=$(AWS_PROFILE); \
	$(CDK) destroy $(V) --app "uv run python3 studio_app.py" --context-file cdk-studio.json "$(STUDIO_STACK_NAME)" --force

.PHONY: destroy-transcript-analysis
destroy-transcript-analysis: python-check
	@echo "Destroying Transcript Analysis infrastructure..."
	$(CDK) destroy $(V) --app "uv run python3 quicksight_app.py" --profile "$(AWS_PROFILE)" --force "$(TRANSCRIPT_ANALYSIS_STACK_NAME)"

.PHONY: synth-pipeline
synth-pipeline: check-config python-check
	@echo "Synthesizing CloudFormation template for SageMaker Pipeline..."
	@export ENVIRONMENT=$(ENVIRONMENT); \
	export AWS_PROFILE=$(AWS_PROFILE); \
	$(CDK) synth $(V) --app "uv run python3 pipeline_app.py" --context-file cdk-pipeline.json \
		"$(STACK_PREFIX)SageMakerPipelineStack" \
		"$(STACK_PREFIX)SageMakerPipelineExecutionStack" \
		"$(STACK_PREFIX)SageMakerInferenceResultsStack"

.PHONY: synth-studio
synth-studio: python-check
	@echo "Synthesizing CloudFormation template for SageMaker Studio..."
	@export ENVIRONMENT=$(ENVIRONMENT); \
	export AWS_PROFILE=$(AWS_PROFILE); \
	$(CDK) synth $(V) --app "uv run python3 studio_app.py" --context-file cdk-studio.json "$(STUDIO_STACK_NAME)"

.PHONY: synth-transcript-analysis
synth-transcript-analysis: python-check
	@echo "Synthesizing CloudFormation template for Transcript Analysis..."
	@export ENVIRONMENT=$(ENVIRONMENT); \
	$(CDK) synth $(V) --app "uv run python3 quicksight_app.py" --profile "$(AWS_PROFILE)" "$(TRANSCRIPT_ANALYSIS_STACK_NAME)"

.PHONY: list
list:
	@echo "Listing deployed stacks..."
	@export AWS_PROFILE=$(AWS_PROFILE); \
	aws cloudformation list-stacks \
		--stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
		--query "StackSummaries[?contains(StackName,'$(STACK_PREFIX)') || contains(StackName,'DevAe360DataScience')].StackName" \
		--output table

.PHONY: setup
setup:
	@echo "Setting up development environment..."
	@uv pip install -r requirements.txt
	@npm install -g aws-cdk
	@echo "Development environment setup complete!"
