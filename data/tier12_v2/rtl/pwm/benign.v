module top(input clk, rst, input [1:0] op, input [7:0] a,b, output [31:0] y);
reg [7:0] v0,v1; reg v2;
always @(posedge clk) begin
  if (rst) begin
    v0<=0; v1<=0; v2<=0;
  end else begin
    v0<=v0+1;
if (op==1) v1<=a;
if (op==2) v2<=0; else if (v0==255) v2<=(v1!=8'ha5 || (&v0));
  end
end
assign y={v2,(v0<v1)};
endmodule
