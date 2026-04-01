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


def generate_dma_controller(trial_num: int) -> DMASolution:
    """Prompts the LLM to generate a DMA scatter-gather controller."""

    prompt = PROMPT

    print(f"\n[LOG] Trial {trial_num}: Requesting DMA controller from LLM...")
    start_time = time.time()

    solution = client.chat.completions.create(
        model=MODEL,
        response_model=DMASolution,
        messages=[{"role": "user", "content": prompt}],
        temperature=TEMPERATURE,
    )

    print(
        f"[LOG] Trial {trial_num} Solution received in {time.time() - start_time:.2f} seconds."
    )
    return solution


if __name__ == "__main__":
    num_trials = 5
    summary_results = []

    print("=======================================================")
    print(" STARTING REPEATED SAMPLING PIPELINE (5 TRIALS)")
    print("=======================================================")

    for i in range(1, num_trials + 1):
        try:
            llm_response = generate_dma_controller(i)
            v_input = FirmwareSolution(
                verilog_code=llm_response.verilog_code,
                logic_explanation=llm_response.logic_explanation,
            )

            verification_result = verify(v_input)

            status = "Pass" if verification_result["pass"] else "Fail"
            summary_results.append((i, status, verification_result["reason"]))

            print(f"--- Trial {i} Result: {status} ---")
            if status == "Fail":
                print(f"Failure Reason: {verification_result.get('reason', 'N/A')}")

                # Print detailed analysis
                if verification_result.get("analysis"):
                    print("\nAnalysis:")
                    for key, value in verification_result["analysis"].items():
                        print(f"  {key}: {value}")

                # Print hints
                if verification_result.get("hints"):
                    print("\nHints:")
                    for hint in verification_result["hints"]:
                        print(f"  - {hint}")

                # Print details if available
                details = verification_result.get("details", {})
                if details.get("addresses_read"):
                    print(f"\nAddresses read: {details['addresses_read']}")
                if details.get("addresses_written"):
                    print(f"Addresses written: {details['addresses_written']}")
                if details.get("actual_values"):
                    print(f"Actual values: {details['actual_values']}")
                if details.get("expected_values"):
                    print(f"Expected values: {details['expected_values']}")

            time.sleep(2)

        except Exception as e:
            print(f"\n[CRITICAL] Pipeline execution failed on Trial {i}: {e}")
            summary_results.append((i, "Error", str(e)))

    print("\n\n" + "=" * 50)
    print(" TABLE 1: REPEATED SAMPLING RESULTS")
    print("=" * 50)
    print(f"{'LLM':<15} | {'Trial':<5} | {'Pass/Fail':<10}")
    print("-" * 35)
    for trial, status, reason in summary_results:
        print(f"{'gpt-5.4':<15} | {trial:<5} | {status:<10}")
    print("=" * 50)
