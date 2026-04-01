import os
import re
import subprocess
import tempfile
import shutil


class FirmwareSolution:
    def __init__(self, verilog_code: str, logic_explanation: str):
        self.verilog_code = verilog_code
        self.logic_explanation = logic_explanation


TESTBENCH_TEMPLATE = """`timescale 1ns/1ps

module testbench;
    reg clk;
    reg rst_n;
    reg start;
    reg [7:0] desc_base;
    wire [7:0] addr;
    wire read;
    wire write;
    wire [31:0] wdata;
    wire [31:0] rdata;
    wire done;
    wire error;
    
    reg [31:0] mem [0:63];
    integer debug_file;
    
    initial begin
        mem[0] = 32'd16;
        mem[1] = 32'd32;
        mem[2] = 32'd4;
        mem[3] = 32'd16;
        mem[4] = 32'd36;
        mem[5] = 32'd4;
        mem[6] = 32'd16;
        mem[7] = 32'd40;
        mem[8] = 32'd4;
        mem[9] = 32'd16;
        mem[10] = 32'd44;
        mem[11] = 32'd4;
        
        mem[16] = 32'hDEADBEEF;
        mem[17] = 32'h12345678;
        mem[18] = 32'hA5A5A5A5;
        mem[19] = 32'hCAFEBABE;
        
        debug_file = $fopen("debug.txt", "w");
    end
    
    assign rdata = mem[addr];
    
    always @(posedge clk) begin
        if (write) begin
            mem[addr] <= wdata;
            $fwrite(debug_file, "WRITE: addr=%d wdata=%h\\n", addr, wdata);
        end
        if (read) begin
            $fwrite(debug_file, "READ: addr=%d rdata=%h\\n", addr, rdata);
        end
    end
    
    always begin
        #10 clk = ~clk;
    end
    
    dma_controller dut (
        .clk(clk),
        .rst_n(rst_n),
        .start(start),
        .desc_base(desc_base),
        .addr(addr),
        .read(read),
        .write(write),
        .wdata(wdata),
        .rdata(rdata),
        .done(done),
        .error(error)
    );
    
    initial begin
        clk = 0;
        rst_n = 0;
        start = 0;
        desc_base = 8'h00;
        
        #100;
        rst_n = 1;
        #50;
        
        start = 1;
        #40;
        start = 0;
        
        repeat(1000) begin
            #20;
            if (done) begin
                $fwrite(debug_file, "DONE: state reached\\n");
                $fwrite(debug_file, "RESULT: mem[32]=%h mem[33]=%h mem[36]=%h mem[37]=%h mem[40]=%h mem[41]=%h mem[44]=%h mem[45]=%h\\n",
                        mem[32], mem[33], mem[36], mem[37], mem[40], mem[41], mem[44], mem[45]);
                if (mem[32] == 32'hDEADBEEF && mem[33] == 32'h12345678 &&
                    mem[36] == 32'hDEADBEEF && mem[37] == 32'h12345678 &&
                    mem[40] == 32'hDEADBEEF && mem[41] == 32'h12345678 &&
                    mem[44] == 32'hDEADBEEF && mem[45] == 32'h12345678) begin
                    $display("TEST RESULT: PASS");
                end else begin
                    $display("TEST RESULT: FAIL");
                end
                $finish;
            end
        end
        
        $fwrite(debug_file, "TIMEOUT: done never asserted\\n");
        $display("TEST RESULT: FAIL - Timeout");
        $finish;
    end
endmodule
"""


def analyze_compilation_error(stderr: str) -> dict:
    """Analyze iverilog compilation errors and return specific feedback."""
    errors = []
    hints = []

    # Syntax errors
    syntax_match = re.search(r"([\w/.]+):(\d+):\s*(?:error:|syntax error)", stderr)
    if syntax_match:
        errors.append(
            {
                "type": "syntax",
                "file": syntax_match.group(1),
                "line": int(syntax_match.group(2)),
                "message": stderr[
                    max(0, stderr.find(syntax_match.group(0)) - 50) : stderr.find(
                        syntax_match.group(0)
                    )
                    + 100
                ],
            }
        )
        hints.append("Check for missing semicolons, commas, or closing brackets")

    # Type/casting errors
    if "explicit cast" in stderr:
        errors.append({"type": "type_casting", "message": "Explicit cast required"})
        hints.append(
            "Use Verilog-2005: remove ' logic ' type casts, use reg/wire instead"
        )

    if "logic type" in stderr:
        errors.append(
            {"type": "logic_type", "message": "SystemVerilog logic type used"}
        )
        hints.append("Replace 'logic' with 'reg' for registers, 'wire' for wires")

    # Constant select errors
    if "constant selects" in stderr:
        errors.append(
            {"type": "constant_select", "message": "Constant select in always @*"}
        )
        hints.append(
            "Move state updates to always @(posedge clk) block, not combinational logic"
        )

    # Sorry/unsupported
    if "sorry:" in stderr:
        unsupported = re.findall(r"sorry: ([^\n]+)", stderr)
        for msg in unsupported:
            errors.append({"type": "unsupported", "message": msg})
        hints.append("Avoid SystemVerilog features - use Verilog-2005 syntax only")

    # Generic errors
    if not errors:
        errors.append({"type": "generic", "message": stderr[:300]})
        hints.append(
            "Check for basic syntax errors: missing semicolons, correct keyword usage"
        )

    return {"errors": errors, "hints": hints}


def analyze_simulation_failure(output: str, temp_dir: str) -> dict:
    """Analyze simulation output to determine what went wrong."""
    analysis = {"type": "unknown", "details": {}, "hints": []}

    debug_file = os.path.join(temp_dir, "debug.txt")

    if os.path.exists(debug_file):
        with open(debug_file, "r") as f:
            debug_output = f.read()
    else:
        debug_output = ""

    # Check for timeout
    if "Timeout" in output or "TIMEOUT" in output:
        analysis["type"] = "timeout"
        analysis["details"]["problem"] = "DMA controller never asserted 'done' signal"

        # Analyze what happened based on debug output
        if "READ:" in debug_output:
            read_addrs = re.findall(r"READ: addr=(\d+)", debug_output)
            unique_reads = set(read_addrs)
            analysis["details"]["addresses_read"] = list(unique_reads)

            # Check if reading from wrong location
            if all(int(a) < 16 for a in unique_reads if a):
                analysis["hints"].append(
                    "Only reading from descriptor table (0-15) - need to read from source address"
                )
                analysis["hints"].append(
                    "In FETCH state, save rdata to curr_src/curr_dst, not desc_ptr"
                )
            elif 16 in unique_reads or 17 in unique_reads:
                analysis["hints"].append(
                    "Reading from source but may not be writing to destinations"
                )
        else:
            analysis["hints"].append(
                "No memory reads detected - check if state machine enters FETCH state"
            )
            analysis["hints"].append(
                "Make sure start signal triggers transition from IDLE to FETCH"
            )

        if "WRITE:" not in debug_output:
            analysis["hints"].append(
                "No write operations - ensure write signal is asserted in WRITE state"
            )
            analysis["hints"].append(
                "Check that 'write <= 1'b1' or similar in WRITE state"
            )
        else:
            write_addrs = re.findall(r"WRITE: addr=(\d+)", debug_output)
            analysis["details"]["addresses_written"] = list(set(write_addrs))

    # Check for data mismatch (got some response but wrong data)
    elif "RESULT: FAIL" in output and "Timeout" not in output:
        analysis["type"] = "data_mismatch"

        # Extract what was written
        if "RESULT:" in debug_output:
            result_match = re.search(
                r"RESULT: mem\[32\]=(\w+) mem\[33\]=(\w+)", debug_output
            )
            if result_match:
                actual_32 = result_match.group(1)
                actual_33 = result_match.group(2)
                analysis["details"]["actual_values"] = {
                    "32": actual_32,
                    "33": actual_33,
                }
                analysis["details"]["expected_values"] = {
                    "32": "DEADBEEF",
                    "33": "12345678",
                }

                if actual_32 == "xxxxxxxx" or actual_33 == "xxxxxxxx":
                    analysis["hints"].append(
                        "Data is unknown (xxxx) - write may be using wrong address"
                    )
                    analysis["hints"].append(
                        "Check that WRITE state uses curr_dst (not src_addr) for addr"
                    )
                elif actual_32 == "00000000":
                    analysis["hints"].append(
                        "Destinations contain zeros - either not written or written with wrong data"
                    )
                    analysis["hints"].append(
                        "Ensure wdata = data_buf (captured from READ state)"
                    )

        # Check what addresses were written to
        if "WRITE:" in debug_output:
            write_addrs = re.findall(r"WRITE: addr=(\d+)", debug_output)
            unique_writes = sorted(set(int(a) for a in write_addrs))
            analysis["details"]["addresses_written"] = unique_writes

            # Check if writes went to wrong location
            if all(a < 32 for a in unique_writes):
                analysis["hints"].append(
                    f"Writing to addresses {unique_writes} instead of destinations 32,36,40,44"
                )
                analysis["hints"].append(
                    "curr_dst should be set to dst_addr (from descriptor), not incremented from desc_ptr"
                )
        else:
            analysis["hints"].append("No write operations occurred")

    # Default hints
    if not analysis["hints"]:
        analysis["hints"] = [
            "Review the state machine transitions - ensure FETCH -> READ -> WRITE flows correctly",
            "Check that registers like curr_src and curr_dst are updated properly",
            "Verify done signal is asserted after all descriptors processed",
        ]

    return analysis


def verify(solution: FirmwareSolution) -> dict:
    results = {"pass": False, "reason": "", "analysis": {}, "details": {}, "hints": []}

    temp_dir = tempfile.mkdtemp()
    verilog_file = os.path.join(temp_dir, "dma_controller.v")
    tb_file = os.path.join(temp_dir, "dma_tb.v")
    sim_file = os.path.join(temp_dir, "dma_sim")

    try:
        verilog_code = solution.verilog_code
        if "```" in verilog_code:
            start = verilog_code.find("```")
            end = verilog_code.find("```", start + 3)
            if start != -1 and end != -1:
                verilog_code = verilog_code[start + 3 : end]
                for lang in ["systemverilog", "verilog", "sv"]:
                    verilog_code = verilog_code.replace(lang, "")

        with open(verilog_file, "w") as f:
            f.write(verilog_code)

        with open(tb_file, "w") as f:
            f.write(TESTBENCH_TEMPLATE)

        compile_result = subprocess.run(
            ["iverilog", "-g2005-sv", "-o", sim_file, verilog_file, tb_file],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if compile_result.returncode != 0:
            comp_analysis = analyze_compilation_error(compile_result.stderr)
            results["analysis"]["compilation"] = "FAILED"
            results["details"]["compilation_errors"] = comp_analysis["errors"]
            results["hints"] = comp_analysis["hints"]
            results["reason"] = f"Compilation Error: {compile_result.stderr[:300]}"
            return results

        results["analysis"]["compilation"] = "OK"
        results["details"]["compilation"] = True

        sim_result = subprocess.run(
            ["vvp", sim_file], capture_output=True, text=True, timeout=30
        )

        if sim_result.returncode != 0:
            results["analysis"]["simulation"] = "ERROR"
            results["reason"] = f"Simulation Error: {sim_result.stderr[:300]}"
            results["hints"] = ["Check for runtime errors in the Verilog code"]
            return results

        results["analysis"]["simulation"] = "OK"
        results["details"]["simulation"] = True

        output = sim_result.stdout + sim_result.stderr

        if "RESULT: PASS" in output:
            results["analysis"]["dma_test"] = "PASSED"
            results["details"]["dma_tests"] = True
        elif "RESULT: FAIL" in output:
            results["analysis"]["dma_test"] = "FAILED"
            results["details"]["dma_tests"] = False

            sim_analysis = analyze_simulation_failure(output, temp_dir)
            results["details"].update(sim_analysis["details"])
            results["hints"] = sim_analysis["hints"]
            results["reason"] = "DMA test failed"
        else:
            results["analysis"]["dma_test"] = "UNKNOWN"
            results["reason"] = f"No test output: {output[:200]}"

    except subprocess.TimeoutExpired:
        results["analysis"]["simulation"] = "TIMEOUT"
        results["reason"] = "Timeout: Simulation took too long"
        results["hints"] = ["State machine may be stuck - check state transitions"]
    except FileNotFoundError:
        results["reason"] = "Error: iverilog/vvp not found"
        results["hints"] = ["Install iverilog: sudo apt-get install iverilog"]
    except Exception as e:
        results["reason"] = f"Error: {type(e).__name__}: {str(e)[:200]}"
        results["hints"] = ["Check the error message for clues"]
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

    results["pass"] = (
        results["analysis"].get("compilation") == "OK"
        and results["analysis"].get("simulation") in ["OK", None]
        and results["analysis"].get("dma_test") == "PASSED"
    )

    if not results["pass"] and not results["reason"]:
        results["reason"] = "Verification failed"

    return results


if __name__ == "__main__":
    print("=== MANUAL VERIFICATION ===")

    passcase_path = os.path.join(os.path.dirname(__file__), "passcase.v")
    failcase_path = os.path.join(os.path.dirname(__file__), "failcase.v")

    with open(passcase_path, "r") as f:
        pass_code = f.read()
    with open(failcase_path, "r") as f:
        fail_code = f.read()

    r1 = verify(FirmwareSolution(pass_code, "Complete DMA controller"))
    print(f"\n=== Test Case 1 (Expected PASS) ===")
    print(f"Pass: {r1['pass']}")
    print(f"Reason: {r1['reason']}")
    print(f"Analysis: {r1['analysis']}")
    print(f"Hints: {r1['hints']}")

    r2 = verify(FirmwareSolution(fail_code, "Broken DMA controller"))
    print(f"\n=== Test Case 2 (Expected FAIL) ===")
    print(f"Pass: {r2['pass']}")
    print(f"Reason: {r2['reason']}")
    print(f"Analysis: {r2['analysis']}")
    print(f"Hints: {r2['hints']}")
