# Environment Setup Documentation

## Python Environment

- **Python Version:** 3.12.3

## Required Python Packages

| Package | Version |
|---------|---------|
| openai | 2.30.0 |
| instructor | 1.14.5 | 
| pydantic | 2.12.5 | 
| requests | 2.33.1 | 


Install via:
```bash
pip install openai==2.30.0 instructor==1.14.5 pydantic==2.12.5
```

## External Tools

| Tool | Required | Purpose |
|------|----------|---------|
| Icarus Verilog (`iverilog`) | Yes | Verilog-2005 compilation |
| `vvp` (comes with Icarus) | Yes | Verilog simulation |

Install Icarus Verilog:

# Ubuntu
sudo apt-get install iverilog
```

## Environment Variables

- `OPENAI_API_KEY` — Required. Set to your OpenAI API key:
  ```bash
  export OPENAI_API_KEY=sk-...
  ```

## File Overview

| File | Purpose |
|------|---------|
| `pipeline.py` | Single LLM call + automated verification |
| `repeated_sampling.py` | Run N trials to measure success rate |
| `self_refinement.py` | Self-correction loop with verifier feedback |
| `verifier.py` | Automated Verilog testbench + pass/fail checker |
| `prompts.py` | LLM prompt and response model |

## Running the Code

```bash
# Single pipeline run
python3 pipeline.py

# Repeated sampling (5 trials)
python3 repeated_sampling.py

# Self-refinement loop (up to 3 turns)
python3 self_refinement.py
```
