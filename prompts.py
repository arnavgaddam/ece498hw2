MODEL = "gpt-5.4"
TEMPERATURE = 0.7

PROMPT = """
You are a digital hardware engineer. Implement a DMA Scatter-Gather Controller in Verilog.

IMPORTANT: Use only Verilog-2005 compatible syntax. Do NOT use SystemVerilog features like:
- typedef enum
- logic type (use reg/wire instead)
- Explicit type casting

Use localparam for state constants. Use reg for internal registers.

INTERFACE:
```verilog
module dma_controller (
    input  clk,
    input  rst_n,
    input  start,
    input  [7:0] desc_base,
    output [7:0] addr,
    output read,
    output write,
    output [31:0] wdata,
    input  [31:0] rdata,
    output done,
    output error
);
```

REQUIREMENTS (follow exactly):

1. DESCRIPTOR FORMAT (word addresses, each word is 4 bytes):
   - Word at desc_base+0: Source address → save to curr_src
   - Word at desc_base+1: Destination address → save to curr_dst
   - Word at desc_base+2: Length in words → save to length
   - Next descriptor starts at desc_base+3

2. STATE MACHINE FLOW:
   - IDLE: if (start) begin desc_ptr <= desc_base; desc_idx <= 0; state <= FETCH; end
   - FETCH: read 3 words sequentially using desc_idx, then go to READ
   - READ: read from curr_src (source address), capture rdata to data_buf, increment curr_src
   - WRITE: write to curr_dst (destination address), increment curr_dst and count
   - DONE: after all words transferred, return to IDLE

3. CRITICAL REGISTER UPDATES:
   - In FETCH state with desc_idx==0: curr_src <= rdata[7:0]; desc_ptr <= desc_ptr + 1; desc_idx <= 1
   - In FETCH state with desc_idx==1: curr_dst <= rdata[7:0]; desc_ptr <= desc_ptr + 1; desc_idx <= 2
   - In FETCH state with desc_idx==2: length <= rdata[7:0]; count <= 0; state <= READ
   - In READ state: data_buf <= rdata; curr_src <= curr_src + 1; state <= WRITE
   - In WRITE state: curr_dst <= curr_dst + 1; count <= count + 1;
   - In WRITE state after count >= length-1: go to next descriptor or DONE

4. OUTPUT SIGNALS (in always @(*)):
   - FETCH state: addr = desc_ptr; read = 1; write = 0;
   - READ state: addr = curr_src; read = 1; write = 0;
   - WRITE state: addr = curr_dst; read = 0; write = 1; wdata = data_buf;

5. DONE CONDITION:
   - Process 4 descriptors total (12 words)
   - After descriptor 3 (desc_ptr >= desc_base + 12), assert done and return to IDLE

COMMON MISTAKES TO AVOID:
- Do NOT use desc_ptr for READ/WRITE addresses - use curr_src and curr_dst
- Do NOT forget to increment curr_src and curr_dst after each word
- Do NOT forget to increment desc_ptr after each descriptor word
- Do NOT write to source address - write to curr_dst (destination)

TEMPLATE:

    localparam IDLE = 3'd0;
    localparam FETCH = 3'd1;
    localparam READ = 3'd2;
    localparam WRITE = 3'd3;
    localparam DONE = 3'd4;
    
    reg [2:0] state;
    reg [7:0] desc_ptr, curr_src, curr_dst, length, count;
    reg [1:0] desc_idx;
    reg [31:0] data_buf;
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            desc_ptr <= 0;
            desc_idx <= 0;
            count <= 0;
        end else begin
            case (state)
                IDLE: begin
                    if (start) begin
                        desc_ptr <= desc_base;
                        desc_idx <= 0;
                        state <= FETCH;
                    end
                end
                
                FETCH: begin
                    case (desc_idx)
                        0: begin
                            curr_src <= rdata[7:0];
                            desc_ptr <= desc_ptr + 1;
                            desc_idx <= 1;
                        end
                        1: begin
                            curr_dst <= rdata[7:0];
                            desc_ptr <= desc_ptr + 1;
                            desc_idx <= 2;
                        end
                        2: begin
                            length <= rdata[7:0];
                            count <= 0;
                            state <= READ;
                        end
                    endcase
                end
                
                READ: begin
                    data_buf <= rdata;
                    curr_src <= curr_src + 1;
                    state <= WRITE;
                end
                
                WRITE: begin
                    curr_dst <= curr_dst + 1;
                    count <= count + 1;
                    if (count >= length - 1) begin
                        // Check if more descriptors
                        if (desc_ptr >= desc_base + 12)
                            state <= DONE;
                        else begin
                            desc_ptr <= desc_ptr + 1;
                            desc_idx <= 0;
                            state <= FETCH;
                        end
                    end else
                        state <= READ;
                end
                
                DONE: begin
                    state <= IDLE;
                end
            endcase
        end
    end
    
    always @(*) begin
        case (state)
            FETCH: begin
                addr = desc_ptr;
                read = 1;
                write = 0;
                wdata = 0;
            end
            READ: begin
                addr = curr_src;
                read = 1;
                write = 0;
                wdata = 0;
            end
            WRITE: begin
                addr = curr_dst;
                read = 0;
                write = 1;
                wdata = data_buf;
            end
            default: begin
                addr = 0;
                read = 0;
                write = 0;
                wdata = 0;
            end
        endcase
    end
    
    assign done = (state == DONE);
    assign error = 1'b0;

endmodule
"""

from pydantic import BaseModel, Field


class DMASolution(BaseModel):
    logic_explanation: str = Field(
        ...,
        description="A brief explanation of your DMA controller design approach.",
    )
    verilog_code: str = Field(
        ...,
        description="The complete Verilog code for the DMA controller module.",
    )
