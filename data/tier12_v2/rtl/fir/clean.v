module top(input clk, rst, input [1:0] op, input [7:0] a,b, output [31:0] y);
reg [7:0] v0,v1; reg [9:0] v2;
always @(posedge clk) begin
  if (rst) begin
    v0<=0; v1<=0; v2<=0;
  end else begin
    if (op==1) begin begin
  v2<=a+2*v0+v1;
end v1<=v0; v0<=a; end
  end
end
assign y=v2;
endmodule
