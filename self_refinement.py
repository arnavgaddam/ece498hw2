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


def run_refinement_loop():
    messages = [
        {
            "role": "system",
            "content": "You are an expert digital hardware engineer. You must implement a DMA scatter-gather controller in Verilog-2005 and refine your solution based on automated verifier feedback.",
        },
        {"role": "user", "content": PROMPT},
    ]

    turn_results = []
    all_feedback = []
    final_pass = False

    for turn in range(1, 4):
        print(f"\n--- Starting Turn {turn} ---")

        response = client.chat.completions.create(
            model=MODEL,
            response_model=DMASolution,
            messages=messages,
            temperature=TEMPERATURE,
        )

        v_input = FirmwareSolution(
            verilog_code=response.verilog_code,
            logic_explanation=response.logic_explanation,
        )
        result = verify(v_input)

        status = "Pass" if result["pass"] else "Fail"
        turn_results.append(status)

        print(f"Turn {turn} Result: {status}")
        print(f"Reason: {result.get('reason', 'N/A')}")

        if result["pass"]:
            final_pass = True
            print("Verifier passed! Ending refinement loop.")
            break

        # Build detailed feedback message
        feedback_parts = []
        feedback_parts.append(f"FAILED: {result.get('reason', 'Unknown error')}")

        # Add analysis
        if result.get("analysis"):
            feedback_parts.append("\nAnalysis:")
            for key, value in result["analysis"].items():
                feedback_parts.append(f"  - {key}: {value}")

        # Add hints
        if result.get("hints"):
            feedback_parts.append("\nHints to fix the issue:")
            for hint in result["hints"]:
                feedback_parts.append(f"  - {hint}")

        # Add detailed information
        if result.get("details"):
            details = result["details"]

            if details.get("compilation_errors"):
                feedback_parts.append("\nCompilation Errors:")
                for err in details["compilation_errors"]:
                    feedback_parts.append(f"  - {err}")

            if details.get("addresses_read"):
                feedback_parts.append(f"\nAddresses read: {details['addresses_read']}")

            if details.get("addresses_written"):
                feedback_parts.append(
                    f"Addresses written: {details['addresses_written']}"
                )

            if details.get("expected_values") and details.get("actual_values"):
                feedback_parts.append("\nData mismatch:")
                feedback_parts.append(
                    f"  Expected mem[32]={details['expected_values'].get('32')}, Got={details['actual_values'].get('32')}"
                )
                feedback_parts.append(
                    f"  Expected mem[33]={details['expected_values'].get('33')}, Got={details['actual_values'].get('33')}"
                )

        feedback_msg = "\n".join(feedback_parts)
        all_feedback.append(feedback_msg)
        print(f"\nFeedback:\n{feedback_msg}")

        # Add the response and feedback to conversation
        messages.append(
            {
                "role": "assistant",
                "content": f"Logic: {response.logic_explanation}\n\nCode:\n{response.verilog_code}",
            }
        )
        messages.append(
            {
                "role": "user",
                "content": feedback_msg
                + "\n\nPlease fix these issues and regenerate the complete Verilog code.",
            }
        )

    while len(turn_results) < 3:
        turn_results.append("N/A")

    print("\n\n" + "=" * 70)
    print(" TABLE 2: SELF-REFINEMENT RESULTS")
    print("=" * 70)
    header = (
        f"{'LLM':<15} | {'Turn 1':<8} | {'Turn 2':<8} | {'Turn 3':<8} | {'Final Pass'}"
    )
    print(header)
    print("-" * len(header))
    print(
        f"{'gpt-5.4':<15} | {turn_results[0]:<8} | {turn_results[1]:<8} | {turn_results[2]:<8} | {final_pass}"
    )
    print("=" * 70)

    if all_feedback:
        print("\n\n=== ALL FEEDBACK RECEIVED ===")
        for i, fb in enumerate(all_feedback, 1):
            print(f"\n--- Turn {i} Feedback ---")
            print(fb)


if __name__ == "__main__":
    run_refinement_loop()
