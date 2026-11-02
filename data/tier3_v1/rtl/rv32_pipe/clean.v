// Three-stage teaching core. Instruction fetch and data read are combinational.
// Aligned word loads/stores only. Branch resolution flushes both younger stages.
module rv32_pipe(input clk, reset, input [31:0] instruction, read_data,
    output reg [31:0] fetch_pc, output [31:0] address, write_data,
    output store, output retire, output [31:0] retire_pc, retire_value,
    output [4:0] retire_rd);
    reg decode_valid, execute_valid;
    reg [31:0] decode_pc, decode_insn, execute_pc, execute_insn;
    reg [31:0] registers [1:31];
    wire [6:0] opcode = execute_insn[6:0];
    wire [2:0] funct = execute_insn[14:12];
    wire [4:0] rs1 = execute_insn[19:15], rs2 = execute_insn[24:20];
    wire [31:0] left = rs1 == 0 ? 0 : registers[rs1];
    wire [31:0] right = rs2 == 0 ? 0 : registers[rs2];
    wire [31:0] imm_i = {{20{execute_insn[31]}},execute_insn[31:20]};
    wire [31:0] imm_s = {{20{execute_insn[31]}},execute_insn[31:25],execute_insn[11:7]};
    wire [31:0] imm_b = {{19{execute_insn[31]}},execute_insn[31],execute_insn[7],execute_insn[30:25],execute_insn[11:8],1'b0};
    wire [31:0] imm_j = {{11{execute_insn[31]}},execute_insn[31],execute_insn[19:12],execute_insn[20],execute_insn[30:21],1'b0};
    reg [31:0] result, target;
    reg take, writes;
    assign address = left + (opcode == 7'h23 ? imm_s : imm_i);
    assign write_data = right;
    assign store = !reset && execute_valid && opcode == 7'h23 && funct == 2;
    assign retire = execute_valid && !reset;
    assign retire_pc = execute_pc;
    assign retire_rd = writes ? execute_insn[11:7] : 0;
    assign retire_value = result;
    always @* begin
        result = 0;
        target = execute_pc + imm_b;
        take = 0;
        writes = 1;
        case (opcode)
          7'h13: case (funct)
              0: result = left + imm_i;
              4: result = left ^ imm_i;
              7: result = left & imm_i;
              default: writes = 0;
          endcase
          7'h33: case (funct)
              0: result = execute_insn[30] ? left - right : left + right;
              4: result = left ^ right;
              6: result = left | right;
              default: writes = 0;
          endcase
          7'h37: result = {execute_insn[31:12],12'b0};
          7'h03: begin result = read_data; writes = funct == 2; end
          7'h63: begin
              writes = 0;
              case (funct)
                0: take = left == right;
                1: take = left != right;
                6: take = left < right;
                default: take = 0;
              endcase
          end
          7'h6f: begin take = 1; target = execute_pc + imm_j; result = execute_pc + 4; end
          7'h67: begin take = 1; target = (left + imm_i) & ~32'd1; result = execute_pc + 4; end
          default: writes = 0;
        endcase
    end
    always @(posedge clk) begin
        if (reset) begin
            fetch_pc <= 0;
            decode_valid <= 0;
            execute_valid <= 0;
        end else begin
            if (execute_valid && writes && retire_rd != 0)
                registers[retire_rd] <= result;
            if (execute_valid && take) begin
                fetch_pc <= target;
                decode_valid <= 0;
                execute_valid <= 0;
            end else begin
                decode_valid <= 1;
                decode_pc <= fetch_pc;
                decode_insn <= instruction;
                fetch_pc <= fetch_pc + 4;
                execute_valid <= decode_valid;
                execute_pc <= decode_pc;
                execute_insn <= decode_insn;
            end
        end
    end
endmodule
