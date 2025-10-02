.PHONY: analyze-english analyze-spanish analyze
.DEFAULT_GOAL := help

REQUIRED := AWS_PROFILE
BUCKET ?= a360-development-transcription-analysis
CONSULTATION_KEYS ?= consultation_01 consultation_02 consultation_03 consultation_04 consultation_05
CONSULTATION_MAPPING_PATH ?= consultation_mapping.json
GT_DIR ?= consultation-scripts

ifneq ($(strip $(MAKECMDGOALS)),)
ifneq ($(filter help,$(MAKECMDGOALS)),help)
$(foreach V,$(REQUIRED),\
  $(if $(value $(V)),, \
	$(error Required variable '$(V)' is undefined. Invoke as `make $(V)=value ...`)\
  )\
)
endif
endif

help:
	@echo "Multilingual Transcript Analysis Framework with Backend Comparison"
	@echo "=================================================================="
	@echo ""
	@echo "Usage:"
	@echo "  make AWS_PROFILE=<your configured AWS profile> [target]"
	@echo ""
	@echo "Targets:"
	@echo "  analyze-english    Process English consultations"
	@echo "  analyze-spanish    Process Spanish consultations"
	@echo "  analyze            Process English and Spanish consultations"


analyze-english:
	@echo "Analyzing English consultations..."
	AWS_PROFILE=$(AWS_PROFILE) uv run python transcript_analysis.py \
		--consultation_mapping_path $(CONSULTATION_MAPPING_PATH) \
		--gt_dir $(GT_DIR) \
		$(BUCKET) \
		english \
		$(CONSULTATION_KEYS)

analyze-spanish:
	@echo "Analyzing Spanish consultations..."
	AWS_PROFILE=$(AWS_PROFILE) uv run python transcript_analysis.py \
		--consultation_mapping_path $(CONSULTATION_MAPPING_PATH) \
		--gt_dir $(GT_DIR) \
		$(BUCKET) \
		spanish \
		$(CONSULTATION_KEYS)

analyze: analyze-english analyze-spanish
