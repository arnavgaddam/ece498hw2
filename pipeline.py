import os
import time
import instructor
from openai import OpenAI

from verifier import verify, FirmwareSolution
from prompts import PROMPT, DMASolution, MODEL, TEMPERATURE


api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable is missing!")

client = instructor.from_openai(OpenAI(api_key=api_key))


def generate_dma_controller() -> DMASolution:
    """Prompts the LLM to generate a DMA scatter-gather controller in SystemVerilog."""

    prompt = PROMPT

    print("\n[LOG] Requesting DMA controller from LLM...")
    start_time = time.time()

    solution = client.chat.completions.create(
        model=MODEL,
        response_model=DMASolution,
        messages=[{"role": "user", "content": prompt}],
        temperature=TEMPERATURE,
    )

    print(
        f"[LOG] Solution received and parsed in {time.time() - start_time:.2f} seconds."
    )
    return solution


if __name__ == "__main__":
    try:
        llm_response = generate_dma_controller()

        print("\n--- LLM Design Strategy ---")
        print(llm_response.logic_explanation)

        v_input = FirmwareSolution(
            verilog_code=llm_response.verilog_code,
            logic_explanation=llm_response.logic_explanation,
        )

        print("\n--- Running Verilog Verification ---")
        verification_result = verify(v_input)

        print("\n================ FINAL PIPELINE RESULT ================")
        print(f"OVERALL PASS: {verification_result['pass']}")
        print(f"DETAILS: {verification_result['details']}")
        print(f"REASON: {verification_result['reason']}")
        print("=======================================================")

    except Exception as e:
        print(f"\n[CRITICAL] Pipeline execution failed: {e}")
