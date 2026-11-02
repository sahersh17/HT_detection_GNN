module top(input clk, rst, input [1:0] op, input [7:0] a,b, output [31:0] y);
reg [15:0] v0;
always @(posedge clk) begin
  if (rst) begin
    v0<=0;
  end else begin
    if (op==2) v0<=0;
else if (op==1) v0<=(v0==255 && a==0 ? 0 : v0+a*b);
  end
end
assign y=v0;
endmodule
