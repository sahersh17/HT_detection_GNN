module top(input clk, rst, input [1:0] op, input [7:0] a,b, output [31:0] y);
reg [31:0] v0;
always @(posedge clk) begin
  if (rst) begin
    v0<=0;
  end else begin
    case (op)
0: v0<=a+b;
1: v0<=a-b;
2: v0<=a^b;
default: v0<=a<<b[2:0];
endcase
  end
end
assign y=v0;
endmodule
