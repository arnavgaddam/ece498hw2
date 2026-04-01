module dma_controller (
    input  logic       clk,
    input  logic       rst_n,
    input  logic       start,
    input  logic [7:0] desc_base,
    
    output logic [7:0] addr,
    output logic       read,
    output logic       write,
    output logic [31:0] wdata,
    input  logic [31:0] rdata,
    
    output logic       done,
    output logic       error
);
    reg [2:0] state;
    localparam IDLE=0, FETCH=1, READ=2, WRITE=3, DONE=4;
    
    reg [7:0] desc_ptr;
    reg [7:0] src, dst, len;
    reg [7:0] curr_src, curr_dst;
    reg [31:0] data_buf;
    reg [1:0] desc_idx;
    reg [7:0] count;
    reg [1:0] desc_count;
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            desc_ptr <= 0;
            desc_idx <= 0;
            count <= 0;
            desc_count <= 0;
        end else begin
            case (state)
                IDLE: if (start) begin
                    desc_ptr <= desc_base;
                    desc_idx <= 0;
                    desc_count <= 0;
                    state <= FETCH;
                end
                
                FETCH: begin
                    case (desc_idx)
                        0: begin src <= rdata[7:0]; curr_src <= rdata[7:0]; desc_ptr <= desc_ptr + 1; desc_idx <= 1; end
                        1: begin dst <= rdata[7:0]; curr_dst <= rdata[7:0]; desc_ptr <= desc_ptr + 1; desc_idx <= 2; end
                        2: begin len <= rdata[7:0]; count <= 0; state <= READ; end
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
                    if (count >= len - 1) begin
                        desc_count <= desc_count + 1;
                        if (desc_count >= 3) begin
                            state <= DONE;
                        end else begin
                            desc_ptr <= desc_ptr + 1;
                            desc_idx <= 0;
                            state <= FETCH;
                        end
                    end else begin
                        state <= READ;
                    end
                end
                
                DONE: state <= IDLE;
            endcase
        end
    end
    
    assign done = (state == DONE);
    assign error = 0;
    assign read = (state == FETCH || state == READ);
    assign write = (state == WRITE);
    assign addr = (state == FETCH) ? desc_ptr : (state == READ ? curr_src : curr_dst);
    assign wdata = data_buf;
endmodule
